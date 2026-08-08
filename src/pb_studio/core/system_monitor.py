import hashlib
import hmac
import json
import logging
import os
import re
import stat
import threading
import time
from pathlib import Path

from pb_studio.core.directml_adapter import get_directml_adapter

logger = logging.getLogger(__name__)

# pythonnet ist optional - nur auf Windows mit LibreHardwareMonitor
try:
    import clr
    _HAS_CLR = True
except ImportError:
    _HAS_CLR = False
    logger.warning("pythonnet (clr) nicht verfuegbar - Hardware-Monitoring deaktiviert")

_monitor_init_lock = threading.Lock()
_SHA256_PATTERN = re.compile(r"[A-Fa-f0-9]{64}")
_ASSEMBLY_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
_LHM_MANIFEST_NAME = "pb-studio-lhm-manifest.json"


def _read_local_regular_file(path: Path) -> bytes:
    file_stat = path.lstat()
    file_attributes = getattr(file_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if file_attributes & reparse_flag:
        raise ValueError(f"Reparse-Point ist nicht erlaubt: {path.name}")
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"Regulaere Datei erforderlich: {path.name}")
    return path.read_bytes()


def _load_verified_lhm_bundle(
    main_assembly_path: Path,
) -> dict[str, tuple[str, bytes]]:
    manifest_path = main_assembly_path.parent / _LHM_MANIFEST_NAME
    manifest_expected_hash = os.environ.get(
        "PBSTUDIO_LHM_MANIFEST_SHA256",
        "",
    )
    main_expected_hash = os.environ.get("PBSTUDIO_LHM_SHA256", "")
    if not _SHA256_PATTERN.fullmatch(manifest_expected_hash):
        raise ValueError(
            "PBSTUDIO_LHM_MANIFEST_SHA256 fehlt oder ist ungueltig"
        )
    if not _SHA256_PATTERN.fullmatch(main_expected_hash):
        raise ValueError("PBSTUDIO_LHM_SHA256 fehlt oder ist ungueltig")

    manifest_bytes = _read_local_regular_file(manifest_path)
    manifest_actual_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if not hmac.compare_digest(
        manifest_actual_hash,
        manifest_expected_hash.lower(),
    ):
        raise ValueError("LHM-Manifest-Hash stimmt nicht")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("LHM-Manifest ist kein gueltiges UTF-8-JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("LHM-Manifest schema_version muss 1 sein")
    entries = manifest.get("assemblies")
    if not isinstance(entries, list) or not entries:
        raise ValueError("LHM-Manifest enthaelt keine Assemblies")

    bundle_root = main_assembly_path.parent.resolve(strict=True)
    if main_assembly_path.parent.resolve(strict=True) != bundle_root:
        raise ValueError("LHM-Hauptassembly liegt ausserhalb des Bundles")
    main_candidate = bundle_root / main_assembly_path.name
    verified: dict[str, tuple[str, bytes]] = {}
    main_verified = False
    seen_files: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Ungueltiger Assembly-Eintrag im LHM-Manifest")
        assembly_name = entry.get("name")
        file_name = entry.get("file")
        expected_hash = entry.get("sha256")
        if (
            not isinstance(assembly_name, str)
            or not _ASSEMBLY_NAME_PATTERN.fullmatch(assembly_name)
        ):
            raise ValueError("Ungueltiger Assembly-Name im LHM-Manifest")
        key = assembly_name.casefold()
        if key in verified:
            raise ValueError(
                f"Doppelter Assembly-Name im LHM-Manifest: {assembly_name}"
            )
        if (
            not isinstance(file_name, str)
            or Path(file_name).name != file_name
            or Path(file_name).suffix.casefold() != ".dll"
        ):
            raise ValueError(
                f"Ungueltiger DLL-Dateiname im LHM-Manifest: {file_name}"
            )
        file_key = file_name.casefold()
        if file_key in seen_files:
            raise ValueError(
                f"Doppelter DLL-Dateiname im LHM-Manifest: {file_name}"
            )
        seen_files.add(file_key)
        if (
            not isinstance(expected_hash, str)
            or not _SHA256_PATTERN.fullmatch(expected_hash)
        ):
            raise ValueError(f"Ungueltiger SHA-256 fuer {assembly_name}")

        assembly_path = bundle_root / file_name
        if assembly_path.parent != bundle_root:
            raise ValueError(
                f"LHM-Assembly verlaesst Bundle-Verzeichnis: {file_name}"
            )
        assembly_bytes = _read_local_regular_file(assembly_path)
        actual_hash = hashlib.sha256(assembly_bytes).hexdigest()
        if not hmac.compare_digest(actual_hash, expected_hash.lower()):
            raise ValueError(f"LHM-Assembly-Hash stimmt nicht: {file_name}")
        verified[key] = (assembly_name, assembly_bytes)
        if assembly_path == main_candidate:
            if assembly_name != "LibreHardwareMonitorLib":
                raise ValueError(
                    "LHM-Hauptassembly hat ungueltigen Assembly-Namen"
                )
            if not hmac.compare_digest(
                actual_hash,
                main_expected_hash.lower(),
            ):
                raise ValueError(
                    "LibreHardwareMonitorLib.dll stimmt nicht mit "
                    "PBSTUDIO_LHM_SHA256 ueberein"
                )
            main_verified = True
    if not main_verified:
        raise ValueError("LHM-Hauptassembly fehlt im freigegebenen Manifest")
    return verified

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
        self.selected_adapter = get_directml_adapter()
        self.selected_adapter_luid = self.selected_adapter.luid
        self.monitoring_status = "degraded"
        self.monitoring_error = "LibreHardwareMonitor not initialized"
        self.computer = None
        self.gpu_sensor = None
        self._gpu_count = 0
        # T3.4: 10s-Cache für PowerShell-Sensor-Fallbacks
        self._cached_stats: dict = {}
        self._cache_time: float = 0.0
        self._cache_lock = threading.Lock()
        self._lhm_lock = threading.Lock()
        self._lhm_assembly_resolver = None
        self._lhm_app_domain = None
        self._cache_ttl: float = 10.0  # Sekunden
        self._bg_refresh_running = False
        # Audit 2026-08-05 (M-4): Dedup-Flag fuer die VRAM-Ceiling-Warnung.
        # Bewusst hier im Konstruktor und nicht per hasattr-Kruecke am
        # Verwendungsort — genau so entstand der AttributeError auf
        # `_cached_y` in advanced_pacing_engine (Log 2026-07-29).
        self._vram_ceiling_warned: bool = False
        if _HAS_CLR:
            self._initialize_lhm()
        else:
            self.monitoring_error = "pythonnet (clr) is unavailable"
            logger.info("Hardware-Monitoring uebersprungen (pythonnet nicht verfuegbar)")

    def _initialize_lhm(self):
        lib_path = getattr(self.config, 'lhm_path', None)
        if not lib_path:
            self.monitoring_error = "LibreHardwareMonitorLib.dll path is missing"
            logger.error(f"LibreHardwareMonitorLib.dll not found at: {lib_path}")
            return

        try:
            main_path = Path(lib_path)
            verified_assemblies = _load_verified_lhm_bundle(main_path)
        except (OSError, ValueError) as exc:
            self.monitoring_error = str(exc)
            logger.error("LibreHardwareMonitor deaktiviert: %s", exc)
            return

        try:
            from System import AppDomain, Array, Byte
            from System.Reflection import Assembly, AssemblyName

            loaded_assemblies = {}

            def resolve_verified_assembly(_sender, args):
                requested_name = AssemblyName(args.Name).Name
                key = str(requested_name).casefold()
                if key not in verified_assemblies:
                    return None
                if key in loaded_assemblies:
                    return loaded_assemblies[key]
                declared_name, assembly_bytes = verified_assemblies[key]
                loaded = Assembly.Load(Array[Byte](assembly_bytes))
                if str(loaded.GetName().Name) != declared_name:
                    raise ValueError(
                        f"Assembly-Identitaet stimmt nicht: {declared_name}"
                    )
                loaded_assemblies[key] = loaded
                return loaded

            app_domain = AppDomain.CurrentDomain
            app_domain.AssemblyResolve += resolve_verified_assembly
            self._lhm_app_domain = app_domain
            self._lhm_assembly_resolver = resolve_verified_assembly

            load_order = sorted(
                key
                for key in verified_assemblies
                if key != "librehardwaremonitorlib"
            )
            load_order.append("librehardwaremonitorlib")
            for key in load_order:
                if key in loaded_assemblies:
                    continue
                declared_name, assembly_bytes = verified_assemblies[key]
                loaded = Assembly.Load(Array[Byte](assembly_bytes))
                if str(loaded.GetName().Name) != declared_name:
                    raise ValueError(
                        f"Assembly-Identitaet stimmt nicht: {declared_name}"
                    )
                loaded_assemblies[key] = loaded

            trusted_platform_names = {
                "microsoft.csharp",
                "microsoft.visualbasic",
                "microsoft.win32.primitives",
                "microsoft.win32.registry",
                "mscorlib",
                "netstandard",
                "system",
                "windowsbase",
            }
            for loaded in loaded_assemblies.values():
                for reference in loaded.GetReferencedAssemblies():
                    reference_name = str(reference.Name)
                    reference_key = reference_name.casefold()
                    if reference_key in verified_assemblies:
                        continue
                    public_key_token = reference.GetPublicKeyToken()
                    is_trusted_platform = (
                        reference_key in trusted_platform_names
                        or reference_key.startswith("system.")
                    ) and public_key_token is not None and len(public_key_token) > 0
                    if not is_trusted_platform:
                        raise ValueError(
                            "Nicht manifestgebundene LHM-Abhaengigkeit: "
                            f"{reference_name}"
                        )
            
            from LibreHardwareMonitor.Hardware import Computer
            
            self.computer = Computer()
            self.computer.IsCpuEnabled = True
            self.computer.IsGpuEnabled = True # Enables both AMD and Nvidia
            self.computer.IsMemoryEnabled = True
            self.computer.Open()
            
            logger.info("LibreHardwareMonitor initialized successfully.")
            self._find_gpu()

        except Exception as e:
            self.monitoring_status = "degraded"
            self.monitoring_error = str(e)
            if (
                self._lhm_app_domain is not None
                and self._lhm_assembly_resolver is not None
            ):
                self._lhm_app_domain.AssemblyResolve -= (
                    self._lhm_assembly_resolver
                )
                self._lhm_app_domain = None
                self._lhm_assembly_resolver = None
            logger.error(f"Failed to initialize Hardware Monitor: {e}")

    @staticmethod
    def _normalized_adapter_name(value: str) -> str:
        return " ".join((value or "").casefold().split())

    def _find_gpu(self):
        """Bind LHM only to the centrally selected DirectML adapter."""
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

        self._gpu_count = len(candidates)
        selected_name = self._normalized_adapter_name(self.selected_adapter.name)
        exact_matches = [
            item
            for item in candidates
            if self._normalized_adapter_name(str(item.Name)) == selected_name
        ]
        if len(exact_matches) == 1:
            self.gpu_sensor = exact_matches[0]
            self.monitoring_status = "ready"
            self.monitoring_error = None
            logger.info(
                "LHM bound to DirectML adapter index=%d luid=%s name=%s",
                self.selected_adapter.device_id,
                self.selected_adapter.luid,
                self.gpu_sensor.Name,
            )
        else:
            self.gpu_sensor = None
            self.monitoring_status = "degraded"
            self.monitoring_error = (
                "LHM adapter identity is ambiguous or does not match "
                f"DirectML adapter {self.selected_adapter.name!r}"
            )

        if self.gpu_sensor:
            self.gpu_sensor.Update()
            logger.info(f"Sensors for {self.gpu_sensor.Name}:")
            for s in self.gpu_sensor.Sensors:
                logger.info(f"  - {s.Name} [{s.SensorType}] = {s.Value}")
        else:
            logger.warning(self.monitoring_error)

    def get_stats(self, *, force_refresh: bool = False) -> dict:
        """Reads current hardware stats with 10s caching for PowerShell fallbacks.
        
        T3.4: PowerShell-Subprozesse (driver_version, VRAM-Total, VRAM-Used,
        GPU-Temp, GPU-Load) werden in einem Hintergrund-Thread ausgeführt und
        das Ergebnis für _cache_ttl Sekunden gecacht, damit der FastAPI-EventLoop
        nicht durch synchrone subprocess.run Aufrufe (5-8s Timeout) blockiert wird.
        """
        now = time.monotonic()
        
        if not force_refresh:
            with self._cache_lock:
                if self._cached_stats and (now - self._cache_time) < self._cache_ttl:
                    return self._cached_stats.copy()
        
        # Erstaufruf oder Cache abgelaufen → Ergebnis berechnen
        # LHM-Abfragen sind schnell (in-process, kein subprocess)
        stats = self._collect_lhm_stats()

        if force_refresh:
            # Allocation gates must never use stale used/load sensor values.
            # Total VRAM and driver version are static and may be retained, but
            # only when the cached sample belongs to the same selected adapter.
            with self._cache_lock:
                cached = self._cached_stats.copy()
            if cached.get("adapter_luid") == stats.get("adapter_luid"):
                if stats["gpu_memory_total"] <= 0:
                    stats["gpu_memory_total"] = cached.get("gpu_memory_total", 0.0)
                stats["driver_version"] = cached.get("driver_version", "Unknown")
            return stats
        
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
                merged["adapter_index"] = stats["adapter_index"]
                merged["adapter_luid"] = stats["adapter_luid"]
                merged["adapter_name"] = stats["adapter_name"]
                merged["dedicated_vram_total_mb"] = stats[
                    "dedicated_vram_total_mb"
                ]
                merged["monitoring_status"] = stats["monitoring_status"]
                merged["monitoring_error"] = stats["monitoring_error"]
                return merged
        
        return stats
    
    def _collect_lhm_stats(self) -> dict:
        """Sammelt nur die schnellen LHM In-Process Sensorwerte."""
        stats = {
            "gpu_name": self.selected_adapter.name,
            "adapter_index": self.selected_adapter.device_id,
            "adapter_luid": self.selected_adapter.luid,
            "adapter_name": self.selected_adapter.name,
            "dedicated_vram_total_mb": self.selected_adapter.dedicated_vram_mb,
            "monitoring_status": self.monitoring_status,
            "monitoring_error": self.monitoring_error,
            "gpu_load": 0.0,
            "gpu_temp": 0.0,
            "gpu_memory_used": 0.0,
            "gpu_memory_total": 0.0,
            "cpu_load": 0.0,
            "driver_version": "Unknown",
        }

        if not self.computer or not self.gpu_sensor:
            return stats
        
        with self._lhm_lock:
            stats["gpu_name"] = self.gpu_sensor.Name
            
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
                # Audit 2026-08-05 (H-5/T3.7): Der Filter unten behaelt genau
                # vier Werte (Load, Temperatur, VRAM used/total) und verwirft
                # alles andere — Luefterdrehzahl, Core- und Speichertakt,
                # Leistungsaufnahme, Spannung, Hot-Spot-Temperatur und die
                # Video-Encode-/Decode-Last. Die Daten liegen an: der Init-Code
                # loggt zwei Zeilen weiter jeden einzelnen Sensor mit Namen und
                # Wert. Ohne sie ist kein Luefterausfall, kein
                # Hot-Spot-Throttling und keine Encoder-Saettigung erkennbar.
                # Wir sammeln sie jetzt zusaetzlich nach SensorType gruppiert;
                # die vier bestehenden Felder bleiben unveraendert, damit kein
                # Konsument bricht.
                sensor_groups: dict[str, dict[str, float]] = {}
                for s in self.gpu_sensor.Sensors:
                    s_type = str(s.SensorType)
                    name = s.Name.lower()

                    if s.Value is not None:
                        sensor_groups.setdefault(s_type.lower(), {})[s.Name] = round(
                            float(s.Value), 2
                        )

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

                if sensor_groups:
                    stats["gpu_sensors"] = sensor_groups

            physical_total = float(self.selected_adapter.dedicated_vram_mb)
            if stats["gpu_memory_total"] > physical_total:
                # Audit 2026-08-05 (M-4): Diese Warnung stand 2983-mal in einer
                # einzigen Session im Log — alle 15 Sekunden identisch. Die
                # Abweichung ist kein Fehler: LHM meldet den physischen
                # Board-Speicher (16368 MB), DXGI den treiberseitig nutzbaren
                # Dedicated-Pool (16177 MB). 1,2 % Differenz ist fuer eine
                # RX 7800 XT normal. Nur noch einmal pro Prozess warnen, und
                # erst ab 5 % Abweichung — darunter ist es Rauschen.
                if (
                    not self._vram_ceiling_warned
                    and stats["gpu_memory_total"] > physical_total * 1.05
                ):
                    logger.warning(
                        "LHM VRAM total %.0fMB exceeds selected adapter physical "
                        "ceiling %.0fMB; clamped (weitere Meldungen unterdrueckt)",
                        stats["gpu_memory_total"],
                        physical_total,
                    )
                    self._vram_ceiling_warned = True
                stats["gpu_memory_total"] = physical_total
            if stats["gpu_memory_used"] > physical_total:
                stats["gpu_memory_used"] = physical_total

        return stats

    def _bg_refresh_ps_stats(self, base_stats: dict) -> None:
        """T3.4: Hintergrund-Thread für langsame PowerShell-Sensor-Fallbacks.
        
        Sammelt nur exakt adaptergebundene statische Fallbacks für Treiber und
        VRAM-Total. Aggregierte GPU-Counter und Fremd-GPU-Sensoren sind verboten.
        """
        try:
            stats = base_stats.copy()
            if self.monitoring_status != "ready":
                with self._cache_lock:
                    self._cached_stats = stats
                    self._cache_time = time.monotonic()
                return
            
            # BUG-080/BUG-100 FIX: Get Driver Version via PowerShell
            if stats["driver_version"] == "Unknown":
                stats["driver_version"] = self._query_driver_version(
                    stats["gpu_name"]
                )

            # BUG-205 Fix: VRAM-Total Fallback via Registry
            if stats["gpu_memory_total"] == 0.0:
                wmi_total = self._wmi_query_vram_total(stats["gpu_name"])
                if wmi_total > 0:
                    stats["gpu_memory_total"] = wmi_total

            # Cache atomic aktualisieren
            with self._cache_lock:
                self._cached_stats = stats
                self._cache_time = time.monotonic()
        except Exception as e:
            logger.warning("BG-Refresh PowerShell stats fehlgeschlagen: %s", e)
        finally:
            with self._cache_lock:
                self._bg_refresh_running = False

    def _query_driver_version(self, gpu_name_hint: str) -> str:
        """Read driver version for the selected adapter only."""
        if not gpu_name_hint or gpu_name_hint == "Unknown":
            return "Unknown"
        try:
            import subprocess
            ps_script = (
                "$name=$args[0]; "
                "(Get-CimInstance Win32_VideoController | "
                "Where-Object { $_.Name -eq $name } | "
                "Select-Object -First 1).DriverVersion"
            )
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                ps_script,
                gpu_name_hint,
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception as exc:
            logger.debug("Adapter-bound driver query failed: %s", exc)
        return "Unknown"

    def _wmi_query_vram_total(self, gpu_name_hint: str) -> float:
        """Fallback: query GPU-VRAM via Registry HardwareInformation.qwMemorySize.

        Win32_VideoController.AdapterRAM ist UInt32 (max 4GB-1) - bei modernen
        GPUs wie RX 7800 XT (16GB) liefert WMI 4095 MB statt 16370 MB.
        Registry-Pfad HKLM\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-...}\\NNNN
        hat REG_QWORD HardwareInformation.qwMemorySize mit 64-bit Wert (verifiziert
        per debug 2026-05-09: RX 7800 XT qwSize=17163091968 = 16370 MB).

        Filtert strikt auf den bereits von LHM gewählten Adapter.
        Returns MB. 0.0 bei Fehler.
        """
        try:
            import subprocess
            ps_script = (
                "$name=$args[0];"
                "$keys = Get-ChildItem "
                "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}' "
                "-ErrorAction SilentlyContinue;"
                "$result = $null;"
                "foreach ($k in $keys) {"
                "  if ($k.Name -match '\\\\\\d{4}$') {"
                "    $p = Get-ItemProperty -Path $k.PSPath -ErrorAction SilentlyContinue;"
                "    if ($p.DriverDesc -eq $name -and $p.'HardwareInformation.qwMemorySize') {"
                "      $obj = [PSCustomObject]@{ Name=$p.DriverDesc; Bytes=$p.'HardwareInformation.qwMemorySize' };"
                "      $result = $obj"
                "    }"
                "  }"
                "};"
                "if ($result) { Write-Output $result.Bytes }"
            )
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                ps_script,
                gpu_name_hint,
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                bytes_total = int(res.stdout.strip())
                mb_total = bytes_total / (1024 * 1024)
                logger.info(
                    "Registry VRAM-Total fallback fuer %r: %.0f MB (LHM lieferte 0 sensors)",
                    gpu_name_hint, mb_total,
                )
                return min(
                    mb_total,
                    float(self.selected_adapter.dedicated_vram_mb),
                )
        except Exception as e:
            logger.warning("Registry VRAM-Fallback fehlgeschlagen: %s", e)
        return 0.0

    def close(self):
        if self.computer:
            self.computer.Close()
        if (
            self._lhm_app_domain is not None
            and self._lhm_assembly_resolver is not None
        ):
            self._lhm_app_domain.AssemblyResolve -= (
                self._lhm_assembly_resolver
            )
            self._lhm_app_domain = None
            self._lhm_assembly_resolver = None
