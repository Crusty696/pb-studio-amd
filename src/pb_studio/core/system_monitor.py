import sys
import logging
import threading
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
            
            from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType
            
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
        """Reads current hardware stats."""
        stats = {
            "gpu_name": self.gpu_sensor.Name if self.gpu_sensor else "Unknown",
            "gpu_load": 0.0,
            "gpu_temp": 0.0,
            "gpu_memory_used": 0.0,
            "gpu_memory_total": 0.0,
            "cpu_load": 0.0,
        }

        if not self.computer: return stats

        # Update sensors
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

    def close(self):
        if self.computer:
            self.computer.Close()
