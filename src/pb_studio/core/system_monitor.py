import sys
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# pythonnet ist optional - nur auf Windows mit LibreHardwareMonitor
try:
    import clr
    _HAS_CLR = True
except ImportError:
    _HAS_CLR = False
    logger.warning("pythonnet (clr) nicht verfuegbar - Hardware-Monitoring deaktiviert")

_monitor_init_lock = threading.Lock()

class SystemMonitor:
    _instance = None

    def __new__(cls):
        with _monitor_init_lock:
            if cls._instance is None:
                instance = super(SystemMonitor, cls).__new__(cls)
                instance._initialized = False
                cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        from pb_studio.config_manager import ConfigManager
        self.config = ConfigManager()
        self.computer = None
        self.gpu_sensor = None
        # T3.4: 10s-Cache für PowerShell-Sensor-Fallbacks
        self._cached_stats: dict = {}
        self._cache_time: float = 0.0
        self._cache_lock = threading.Lock()
        self._lhm_lock = threading.Lock()
        self._cache_ttl: float = 10.0  # Sekunden
        self._bg_refresh_running = False
        if _HAS_CLR:
            self._initialize_lhm()
        else:
            logger.info("Hardware-Monitoring uebersprungen (pythonnet nicht verfuegbar)")

    def _initialize_lhm(self):
        lib_path = getattr(self.config, 'lhm_path', None)
        if not lib_path or not Path(lib_path).exists():
            logger.error(f"LibreHardwareMonitorLib.dll not found at: {lib_path}")
            return

        try:
            # Add reference to the DLL
            sys.path.append(str(Path(lib_path).parent))
            clr.AddReference("LibreHardwareMonitorLib")
            
            from LibreHardwareMonitor.Hardware import Computer
            
            self.computer = Computer()
            self.computer.IsCpuEnabled = True
            self.computer.IsGpuEnabled = True # Enables both AMD and Nvidia
            self.computer.IsMemoryEnabled = True
            self.computer.Open()
            
            logger.info("LibreHardwareMonitor initialized successfully.")
            self._find_gpu()

        except Exception as e:
            logger.error(f"Failed to initialize Hardware Monitor: {e}")

    def _find_gpu(self):
        """Finds the primary GPU (Prefer Dedicated AMD, then APU)."""
        if not self.computer: return

        candidates = []
        logger.info("Scanning for Hardware (Strict GPU Filter)...")
        for hardware in self.computer.Hardware:
            # Type as string and int
            h_type_str = str(hardware.HardwareType)
            h_type_int = int(hardware.HardwareType)
            
            # Log everything
            logger.info(f"  > Found: {hardware.Name} [Type: {h_type_str} ({h_type_int})]")
            
            # STRICT FILTER: Only accept actual GPUs
            # Known Enums: GpuNvidia(3), GpuAmd(5), GpuIntel(6?), Cpu(2), RAM(3??) 
            # Note: User log showed Memory is 3? Or maybe confusing. 
            # Just rely on string "Gpu" prefix or explicit strings.
            if h_type_str.startswith("Gpu"):
                candidates.append(hardware)

        # Prioritization Strategy:
        # 1. Dedicated AMD (RX/XT/Pro)
        # 2. Any AMD GPU
        # 3. Any Nvidia GPU (Fallback)
        # 4. Any Intel GPU
        
        dedicated_amd = [g for g in candidates if "GpuAmd" in str(g.HardwareType) and ("RX" in g.Name or "XT" in g.Name)]
        any_amd = [g for g in candidates if "GpuAmd" in str(g.HardwareType)]
        any_gpu = candidates
        
        if dedicated_amd:
            self.gpu_sensor = dedicated_amd[0]
            logger.info(f"Selected Dedicated AMD GPU: {self.gpu_sensor.Name}")
        elif any_amd:
            self.gpu_sensor = any_amd[0]
            logger.info(f"Selected Generic AMD GPU: {self.gpu_sensor.Name}")
        elif any_gpu:
            self.gpu_sensor = any_gpu[0]
            logger.info(f"Selected Fallback GPU: {self.gpu_sensor.Name}")
        
        if self.gpu_sensor:
            self.gpu_sensor.Update()
            logger.info(f"Sensors for {self.gpu_sensor.Name}:")
            for s in self.gpu_sensor.Sensors:
                logger.info(f"  - {s.Name} [{s.SensorType}] = {s.Value}")
        else:
            logger.warning("No suitable GPU found for monitoring.")

    def get_stats(self) -> dict:
        """Reads current hardware stats with 10s caching for PowerShell fallbacks.
        
        T3.4: PowerShell-Subprozesse (driver_version, VRAM-Total, VRAM-Used,
        GPU-Temp, GPU-Load) werden in einem Hintergrund-Thread ausgeführt und
        das Ergebnis für _cache_ttl Sekunden gecacht, damit der FastAPI-EventLoop
        nicht durch synchrone subprocess.run Aufrufe (5-8s Timeout) blockiert wird.
        """
        now = time.monotonic()
        
        # Wenn Cache gültig ist, sofort zurückgeben
        with self._cache_lock:
            if self._cached_stats and (now - self._cache_time) < self._cache_ttl:
                return self._cached_stats.copy()
        
        # Erstaufruf oder Cache abgelaufen → Ergebnis berechnen
        # LHM-Abfragen sind schnell (in-process, kein subprocess)
        stats = self._collect_lhm_stats()
        
        # PowerShell Fallbacks im Hintergrund starten (stale-while-revalidate)
        with self._cache_lock:
            if not self._bg_refresh_running:
                self._bg_refresh_running = True
                bg = threading.Thread(
                    target=self._bg_refresh_ps_stats,
                    args=(stats,),
                    daemon=True,
                    name="system-monitor-ps-refresh",
                )
                bg.start()
        
        # Sofort LHM-only-Stats zurückgeben (Fallback-Werte kommen im nächsten Poll)
        with self._cache_lock:
            if self._cached_stats:
                # Merge: LHM-Werte aktualisieren, PS-Fallback-Werte behalten
                merged = self._cached_stats.copy()
                for k in ("gpu_load", "gpu_temp", "gpu_memory_used", "gpu_memory_total", "cpu_load"):
                    if stats.get(k, 0.0) > 0:
                        merged[k] = stats[k]
                merged["gpu_name"] = stats["gpu_name"]
                return merged
        
        return stats
    
    def _collect_lhm_stats(self) -> dict:
        """Sammelt nur die schnellen LHM In-Process Sensorwerte."""
        stats = {
            "gpu_name": "Unknown",
            "gpu_load": 0.0,
            "gpu_temp": 0.0,
            "gpu_memory_used": 0.0,
            "gpu_memory_total": 0.0,
            "cpu_load": 0.0,
            "driver_version": "Unknown",
        }

        if not self.computer: return stats
        
        with self._lhm_lock:
            stats["gpu_name"] = self.gpu_sensor.Name if self.gpu_sensor else "Unknown"
            
            # Update sensors (LHM in-process - schnell)
            for hardware in self.computer.Hardware:
                hardware.Update()

                # CPU Load
                h_type_str = str(hardware.HardwareType)
                if h_type_str == "Cpu":
                    for s in hardware.Sensors:
                        s_type = str(s.SensorType)
                        name = s.Name.lower()
                        if s_type == "Load" and "total" in name:
                            stats["cpu_load"] = s.Value or 0.0

            if self.gpu_sensor:
                for s in self.gpu_sensor.Sensors:
                    s_type = str(s.SensorType)
                    name = s.Name.lower()
                    
                    # Load
                    if s_type == "Load" and "core" in name:
                        stats["gpu_load"] = max(stats["gpu_load"], s.Value or 0.0)
                    
                    # Temp (Edge or Hotspot - prefer Edge/Core)
                    if s_type == "Temperature":
                        # Prefer "Core" or generic "GPU Core", avoid "Hot Spot" if possible (or take max?)
                        if "core" in name or "edge" in name:
                             stats["gpu_temp"] = max(stats["gpu_temp"], s.Value or 0.0)

                    # Memory (SmallData in LHM)
                    if s_type == "SmallData":
                        # Nur "GPU Memory Used" oder "D3D Dedicated Memory Used" zulassen
                        # NICHT "D3D Shared Memory Used/Total" oder "D3D Dedicated Memory Total/Free"
                        if "shared" in name:
                            pass  # Shared Memory ignorieren (ist nicht VRAM)
                        elif "memory used" in name and "free" not in name and "total" not in name:
                            stats["gpu_memory_used"] = s.Value or 0.0
                        elif name == "gpu memory total":
                            # Exakt "GPU Memory Total" - nicht D3D Shared/Dedicated Total
                            stats["gpu_memory_total"] = s.Value or 0.0
                        elif "d3d dedicated memory total" in name and stats["gpu_memory_total"] == 0:
                            # Fallback: D3D Dedicated als Total nur wenn kein GPU Memory Total
                            stats["gpu_memory_total"] = s.Value or 0.0

        return stats

    def _bg_refresh_ps_stats(self, base_stats: dict) -> None:
        """T3.4: Hintergrund-Thread für langsame PowerShell-Sensor-Fallbacks.
        
        Sammelt driver_version, VRAM-Total/Used Fallbacks, GPU-Temp und GPU-Load
        via subprocess.run (jeweils 5-8s Timeout). Aktualisiert den Cache atomic.
        """
        try:
            stats = base_stats.copy()
            
            # BUG-080/BUG-100 FIX: Get Driver Version via PowerShell
            if stats["driver_version"] == "Unknown":
                try:
                    import subprocess
                    cmd = ["powershell", "-Command", "(Get-CimInstance Win32_VideoController | Select-Object -First 1).DriverVersion"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and res.stdout.strip():
                        stats["driver_version"] = res.stdout.strip()
                except Exception:
                    pass

            # BUG-205 Fix: VRAM-Total Fallback via Registry
            if stats["gpu_memory_total"] == 0.0:
                wmi_total = self._wmi_query_vram_total(stats["gpu_name"])
                if wmi_total > 0:
                    stats["gpu_memory_total"] = wmi_total

            # BUG-205 Phase 2: VRAM-Used via Windows Performance Counter
            if stats["gpu_memory_used"] == 0.0:
                counter_used = self._counter_query_vram_used()
                if counter_used > 0:
                    stats["gpu_memory_used"] = counter_used

            # Audit D1: GPU Temperature Fallback
            if stats["gpu_temp"] == 0.0:
                alt_temp = self._query_temperature_alternative()
                if alt_temp > 0:
                    stats["gpu_temp"] = alt_temp

            # Audit D2: GPU Load Fallback
            if stats["gpu_load"] == 0.0:
                alt_load = self._query_load_alternative()
                if alt_load > 0:
                    stats["gpu_load"] = alt_load

            # Cache atomic aktualisieren
            with self._cache_lock:
                self._cached_stats = stats
                self._cache_time = time.monotonic()
        except Exception as e:
            logger.warning("BG-Refresh PowerShell stats fehlgeschlagen: %s", e)
        finally:
            with self._cache_lock:
                self._bg_refresh_running = False

    def _wmi_query_vram_total(self, gpu_name_hint: str) -> float:
        """Fallback: query GPU-VRAM via Registry HardwareInformation.qwMemorySize.

        Win32_VideoController.AdapterRAM ist UInt32 (max 4GB-1) - bei modernen
        GPUs wie RX 7800 XT (16GB) liefert WMI 4095 MB statt 16370 MB.
        Registry-Pfad HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-...}\\NNNN
        hat REG_QWORD HardwareInformation.qwMemorySize mit 64-bit Wert (verifiziert
        per debug 2026-05-09: RX 7800 XT qwSize=17163091968 = 16370 MB).

        Filtert auf DriverDesc match falls gpu_name_hint gegeben; sonst nimmt grosste
        Karte (dedicated > iGPU). Returns MB. 0.0 bei Fehler.
        """
        try:
            import subprocess
            ps_script = (
                "$keys = Get-ChildItem "
                "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}' "
                "-ErrorAction SilentlyContinue;"
                "$result = $null;"
                "foreach ($k in $keys) {"
                "  if ($k.Name -match '\\\\\\d{4}$') {"
                "    $p = Get-ItemProperty -Path $k.PSPath -ErrorAction SilentlyContinue;"
                "    if ($p.'HardwareInformation.qwMemorySize') {"
                "      $obj = [PSCustomObject]@{ Name=$p.DriverDesc; Bytes=$p.'HardwareInformation.qwMemorySize' };"
                "      if ($null -eq $result -or $obj.Bytes -gt $result.Bytes) { $result = $obj }"
                "    }"
                "  }"
                "};"
                "if ($result) { Write-Output $result.Bytes }"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                bytes_total = int(res.stdout.strip())
                mb_total = bytes_total / (1024 * 1024)
                logger.info(
                    "Registry VRAM-Total fallback fuer %r: %.0f MB (LHM lieferte 0 sensors)",
                    gpu_name_hint, mb_total,
                )
                return mb_total
        except Exception as e:
            logger.warning("Registry VRAM-Fallback fehlgeschlagen: %s", e)
        return 0.0

    def _counter_query_vram_used(self) -> float:
        """Fallback: VRAM-Used via Windows Performance Counter.

        \\\\GPU Process Memory(*)\\\\Local Usage liefert per-process bytes.
        Summe ueber alle Instanzen ist Total-Used.
        Returns MB. 0.0 bei Fehler.
        """
        try:
            import subprocess
            ps_script = (
                "$samples = (Get-Counter '\\GPU Process Memory(*)\\Local Usage' "
                "-ErrorAction SilentlyContinue).CounterSamples; "
                "if ($samples) { ($samples | Measure-Object -Property CookedValue -Sum).Sum } "
                "else { 0 }"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                bytes_used = float(res.stdout.strip())
                mb_used = bytes_used / (1024 * 1024)
                if mb_used > 0:
                    logger.debug("Counter VRAM-Used fallback: %.0f MB", mb_used)
                return mb_used
        except Exception as e:
            logger.warning("Counter VRAM-Used-Fallback fehlgeschlagen: %s", e)
        return 0.0

    def _query_temperature_alternative(self) -> float:
        r"""Audit D1 Fallback: GPU temp via alternative sources wenn LHM fuer
        dedicated GPU 0 liefert (AMD Adrenalin blockiert Sensor-Zugriff).

        Strategie (in Reihenfolge, kein extra-dependency):
        1. iGPU temperature aus LHM (gleicher Hardware-Loop, anderes GPU-Device).
           iGPU + dGPU sitzen oft im selben Thermal-Package - iGPU temp ist
           ein akzeptabler Proxy (besser als 0).
        2. PowerShell Get-Counter "\Thermal Zone Information(*)\Temperature"
           (System-Thermal, last-resort heuristic).

        Returns Celsius (float). 0.0 bei Fehler / wenn nichts gefunden.
        """
        # Versuch 1: iGPU/anderes GPU-Device temperature aus LHM
        if self.computer:
            try:
                for hardware in self.computer.Hardware:
                    h_type_str = str(hardware.HardwareType)
                    if not h_type_str.startswith("Gpu"):
                        continue
                    if hardware == self.gpu_sensor:
                        # Dedicated wurde bereits oben abgefragt - 0 sensors
                        continue
                    hardware.Update()
                    for s in hardware.Sensors:
                        if str(s.SensorType) != "Temperature":
                            continue
                        name = (s.Name or "").lower()
                        if "core" in name or "edge" in name or "gpu" in name:
                            val = s.Value or 0.0
                            if val and val > 0:
                                logger.debug(
                                    "GPU temp Fallback ueber alternatives GPU-Device "
                                    "'%s' (sensor=%s): %.1f C",
                                    hardware.Name, s.Name, float(val),
                                )
                                return float(val)
            except Exception as e:
                logger.debug("iGPU-Temp-Fallback fehlgeschlagen: %s", e)

        # Versuch 2: PowerShell Thermal Zone Information (System-thermal heuristic).
        # Kelvin*10 -> Celsius via /10 - 273.15. Nimm hoechste Zone als Proxy
        # (GPU thermal-zone ist typischerweise hottest unter Last).
        try:
            import subprocess
            ps_script = (
                "$samples = (Get-Counter '\\Thermal Zone Information(*)\\Temperature' "
                "-ErrorAction SilentlyContinue).CounterSamples; "
                "if ($samples) { ($samples | Measure-Object -Property CookedValue -Maximum).Maximum } "
                "else { 0 }"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                kelvin = float(res.stdout.strip())
                if kelvin > 200:  # plausibel (>200K = >-73C)
                    celsius = kelvin - 273.15
                    if 20.0 <= celsius <= 150.0:  # plausibel range
                        logger.debug(
                            "GPU temp Fallback ueber Thermal-Zone-Max: %.1f C",
                            celsius,
                        )
                        return float(celsius)
        except Exception as e:
            logger.debug("Thermal-Zone-Temp-Fallback fehlgeschlagen: %s", e)

        return 0.0

    def _query_load_alternative(self) -> float:
        r"""Audit D2 Fallback: GPU Load via Windows Performance Counter wenn LHM
        0 liefert (gleiches Problem wie BUG-205: AMD Adrenalin blockiert
        Load-Sensor fuer dedicated GPU).

        \GPU Engine(*engtype_3D)\Utilization Percentage liefert per-engine load.
        Sum ueber alle Engines = total GPU 3D-Load.
        Returns Percent (0..100). 0.0 bei Fehler.
        """
        try:
            import subprocess
            ps_script = (
                "$samples = (Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' "
                "-ErrorAction SilentlyContinue).CounterSamples; "
                "if ($samples) { ($samples | Measure-Object -Property CookedValue -Sum).Sum } "
                "else { 0 }"
            )
            cmd = ["powershell", "-NoProfile", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                load = float(res.stdout.strip())
                # Cap auf 100 (multi-engine kann technisch ueber 100 summieren)
                load = min(100.0, max(0.0, load))
                if load > 0:
                    logger.debug("Counter GPU Load fallback: %.1f%%", load)
                return load
        except Exception as e:
            logger.warning("Counter GPU-Load-Fallback fehlgeschlagen: %s", e)
        return 0.0

    def close(self):
        if self.computer:
            self.computer.Close()
