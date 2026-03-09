# Hardware Control Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "GPU", "VRAM", "Hardware", "Monitor", "Temperature", "FFmpeg Encoder"
- "LibreHardwareMonitor", "AMD", "Intel"
- Arbeit an Hardware-Detection, System-Monitoring, Encoder-Auswahl

## Cross-References
- → `ai-inference.md` (GPU Provider Selection)
- → `video-engineering.md` (FFmpeg Hardware Encoder)
- → `debugging.md` (Performance Monitoring)
- → `offline-engineering.md` (Lokale Hardware-Erkennung)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **AMD-Only** | Ausschließlich AMD GPU Support |
| **Monitoring** | GPU-Last/VRAM überwachen vor Crashes |
| **Graceful Degradation** | Bei Hardware-Problemen sanft auf CPU zurückfallen |

---

## 1. Hardware Detection (AMD)

```python
import subprocess
import platform
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class GPUVendor(Enum):
    AMD = "amd"
    INTEL = "intel"
    UNKNOWN = "unknown"

@dataclass
class GPUInfo:
    vendor: GPUVendor
    name: str
    vram_mb: int
    driver_version: str
    supports_directml: bool
    supports_amf: bool
    supports_qsv: bool

def detect_gpu() -> GPUInfo:
    """Erkennt AMD GPU und deren Capabilities."""
    
    # Windows: WMI Query
    if platform.system() == "Windows":
        return _detect_gpu_windows()
    else:
        return _detect_gpu_linux()

def _detect_gpu_windows() -> GPUInfo:
    """GPU-Erkennung unter Windows."""
    import wmi
    
    try:
        c = wmi.WMI()
        gpus = c.Win32_VideoController()
        
        if not gpus:
            return _unknown_gpu()
        
        gpu = gpus[0]  # Primäre GPU
        name = gpu.Name.lower()
        
        # Vendor Detection (AMD-fokussiert)
        if "amd" in name or "radeon" in name or "rx " in name:
            vendor = GPUVendor.AMD
        elif "intel" in name or "uhd" in name or "iris" in name:
            vendor = GPUVendor.INTEL
        else:
            vendor = GPUVendor.UNKNOWN
        
        # VRAM (AdapterRAM ist in Bytes)
        vram_mb = int(gpu.AdapterRAM or 0) // (1024 * 1024)
        
        # Capabilities basierend auf Vendor
        return GPUInfo(
            vendor=vendor,
            name=gpu.Name,
            vram_mb=vram_mb,
            driver_version=gpu.DriverVersion or "Unknown",
            supports_directml=(vendor in [GPUVendor.AMD, GPUVendor.INTEL]),
            supports_amf=(vendor == GPUVendor.AMD),
            supports_qsv=(vendor == GPUVendor.INTEL)
        )
        
    except Exception as e:
        logger.error(f"GPU Detection failed: {e}")
        return _unknown_gpu()

def _detect_gpu_linux() -> GPUInfo:
    """GPU-Erkennung unter Linux."""
    try:
        result = subprocess.run(
            ["lspci", "-v"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.lower()
        
        if "amd" in output or "radeon" in output:
            vendor = GPUVendor.AMD
        elif "intel" in output:
            vendor = GPUVendor.INTEL
        else:
            vendor = GPUVendor.UNKNOWN
        
        return GPUInfo(
            vendor=vendor,
            name="Detected via lspci",
            vram_mb=0,  # Schwer zu ermitteln unter Linux
            driver_version="Unknown",
            supports_directml=False,  # DirectML ist Windows-only
            supports_amf=(vendor == GPUVendor.AMD),
            supports_qsv=(vendor == GPUVendor.INTEL)
        )
    except Exception as e:
        logger.error(f"GPU Detection failed: {e}")
        return _unknown_gpu()

def _unknown_gpu() -> GPUInfo:
    """Fallback für unbekannte GPU."""
    return GPUInfo(
        vendor=GPUVendor.UNKNOWN,
        name="Unknown",
        vram_mb=0,
        driver_version="Unknown",
        supports_directml=False,
        supports_amf=False,
        supports_qsv=False
    )
```

---

## 2. LibreHardwareMonitor Integration

```python
import requests
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class HardwareMetrics:
    gpu_load_percent: float
    gpu_temp_celsius: float
    vram_used_mb: float
    vram_total_mb: float
    cpu_load_percent: float
    cpu_temp_celsius: float
    ram_used_mb: float
    ram_total_mb: float

class HardwareMonitor:
    """Integration mit LibreHardwareMonitor HTTP API."""
    
    DEFAULT_URL = "http://localhost:8085"
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or self.DEFAULT_URL
        self._available = None
    
    @property
    def is_available(self) -> bool:
        """Prüft ob LHM läuft."""
        if self._available is None:
            try:
                response = requests.get(
                    f"{self.base_url}/data.json",
                    timeout=2
                )
                self._available = response.status_code == 200
            except:
                self._available = False
        return self._available
    
    def get_metrics(self) -> Optional[HardwareMetrics]:
        """Holt aktuelle Hardware-Metriken."""
        if not self.is_available:
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/data.json",
                timeout=5
            )
            data = response.json()
            
            return self._parse_metrics(data)
            
        except Exception as e:
            logger.error(f"Failed to get hardware metrics: {e}")
            return None
    
    def _parse_metrics(self, data: dict) -> HardwareMetrics:
        """Parsed LHM JSON Response."""
        
        metrics = HardwareMetrics(
            gpu_load_percent=0,
            gpu_temp_celsius=0,
            vram_used_mb=0,
            vram_total_mb=0,
            cpu_load_percent=0,
            cpu_temp_celsius=0,
            ram_used_mb=0,
            ram_total_mb=0
        )
        
        def find_sensor(node, sensor_type: str, name_contains: str) -> Optional[float]:
            """Rekursive Sensor-Suche."""
            if isinstance(node, dict):
                if node.get("Type") == sensor_type and name_contains.lower() in node.get("Text", "").lower():
                    return float(node.get("Value", "0").replace(" ", "").rstrip("%°CMB"))
                
                for child in node.get("Children", []):
                    result = find_sensor(child, sensor_type, name_contains)
                    if result is not None:
                        return result
            return None
        
        # GPU Metriken (AMD Radeon)
        metrics.gpu_load_percent = find_sensor(data, "Load", "GPU Core") or 0
        metrics.gpu_temp_celsius = find_sensor(data, "Temperature", "GPU Core") or 0
        metrics.vram_used_mb = find_sensor(data, "SmallData", "GPU Memory Used") or 0
        metrics.vram_total_mb = find_sensor(data, "SmallData", "GPU Memory Total") or 0
        
        # CPU Metriken
        metrics.cpu_load_percent = find_sensor(data, "Load", "CPU Total") or 0
        metrics.cpu_temp_celsius = find_sensor(data, "Temperature", "CPU Package") or 0
        
        # RAM Metriken
        metrics.ram_used_mb = find_sensor(data, "Data", "Memory Used") or 0
        metrics.ram_total_mb = find_sensor(data, "Data", "Memory Available") or 0
        
        return metrics
    
    def should_throttle(self, metrics: HardwareMetrics = None) -> tuple[bool, str]:
        """Prüft ob System gedrosselt werden sollte."""
        
        if metrics is None:
            metrics = self.get_metrics()
        
        if metrics is None:
            return False, "Keine Metriken verfügbar"
        
        reasons = []
        
        # GPU überlastet
        if metrics.gpu_load_percent > 95:
            reasons.append(f"GPU Load: {metrics.gpu_load_percent:.0f}%")
        
        # GPU zu heiß
        if metrics.gpu_temp_celsius > 85:
            reasons.append(f"GPU Temp: {metrics.gpu_temp_celsius:.0f}°C")
        
        # VRAM fast voll
        if metrics.vram_total_mb > 0:
            vram_percent = (metrics.vram_used_mb / metrics.vram_total_mb) * 100
            if vram_percent > 90:
                reasons.append(f"VRAM: {vram_percent:.0f}%")
        
        # CPU überlastet
        if metrics.cpu_load_percent > 95:
            reasons.append(f"CPU Load: {metrics.cpu_load_percent:.0f}%")
        
        if reasons:
            return True, ", ".join(reasons)
        
        return False, "System OK"
```

---

## 3. FFmpeg Hardware Encoder Selection (AMD)

```python
from dataclasses import dataclass
from typing import Optional
import subprocess

@dataclass
class EncoderConfig:
    video_encoder: str
    video_decoder: str
    hwaccel: Optional[str]
    hwaccel_device: Optional[str]
    extra_params: list[str]

def detect_ffmpeg_encoders() -> dict[str, bool]:
    """Erkennt verfügbare FFmpeg Hardware-Encoder."""
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.lower()
        
        return {
            "h264_amf": "h264_amf" in output,          # AMD
            "hevc_amf": "hevc_amf" in output,          # AMD
            "h264_qsv": "h264_qsv" in output,          # Intel
            "hevc_qsv": "hevc_qsv" in output,          # Intel
            "libx264": "libx264" in output,            # Software
            "libx265": "libx265" in output,            # Software
        }
        
    except Exception as e:
        logger.error(f"FFmpeg encoder detection failed: {e}")
        return {
            "libx264": True,
            "libx265": True
        }

def get_optimal_encoder_config(gpu_info: GPUInfo = None) -> EncoderConfig:
    """Wählt optimalen Encoder basierend auf Hardware (AMD-priorisiert)."""
    
    if gpu_info is None:
        gpu_info = detect_gpu()
    
    available = detect_ffmpeg_encoders()
    
    # AMD - AMF (Priorität 1)
    if gpu_info.vendor == GPUVendor.AMD and available.get("h264_amf"):
        return EncoderConfig(
            video_encoder="h264_amf",
            video_decoder="h264",
            hwaccel="d3d11va",
            hwaccel_device=None,
            extra_params=[
                "-quality", "balanced",
                "-rc", "vbr_latency"
            ]
        )
    
    # Intel - QSV (Fallback für Intel iGPU)
    if gpu_info.vendor == GPUVendor.INTEL and available.get("h264_qsv"):
        return EncoderConfig(
            video_encoder="h264_qsv",
            video_decoder="h264_qsv",
            hwaccel="qsv",
            hwaccel_device=None,
            extra_params=[
                "-preset", "medium",
                "-global_quality", "23"
            ]
        )
    
    # Fallback - Software
    return EncoderConfig(
        video_encoder="libx264",
        video_decoder="h264",
        hwaccel=None,
        hwaccel_device=None,
        extra_params=[
            "-preset", "medium",
            "-crf", "23"
        ]
    )

def build_ffmpeg_cmd(
    input_path: str,
    output_path: str,
    encoder_config: EncoderConfig = None
) -> list[str]:
    """Baut FFmpeg Command mit Hardware-Acceleration."""
    
    if encoder_config is None:
        encoder_config = get_optimal_encoder_config()
    
    cmd = ["ffmpeg", "-y"]
    
    # Hardware Acceleration für Decoding
    if encoder_config.hwaccel:
        cmd.extend(["-hwaccel", encoder_config.hwaccel])
        if encoder_config.hwaccel_device:
            cmd.extend(["-hwaccel_device", encoder_config.hwaccel_device])
    
    # Input
    cmd.extend(["-i", input_path])
    
    # Video Encoder
    cmd.extend(["-c:v", encoder_config.video_encoder])
    cmd.extend(encoder_config.extra_params)
    
    # Audio (copy or re-encode)
    cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    
    # Output
    cmd.append(output_path)
    
    return cmd
```

---

## 4. Process Priority Management

```python
import psutil
import os
from enum import IntEnum

class ProcessPriority(IntEnum):
    IDLE = psutil.IDLE_PRIORITY_CLASS
    BELOW_NORMAL = psutil.BELOW_NORMAL_PRIORITY_CLASS
    NORMAL = psutil.NORMAL_PRIORITY_CLASS
    ABOVE_NORMAL = psutil.ABOVE_NORMAL_PRIORITY_CLASS
    HIGH = psutil.HIGH_PRIORITY_CLASS
    REALTIME = psutil.REALTIME_PRIORITY_CLASS

def set_process_priority(priority: ProcessPriority = ProcessPriority.BELOW_NORMAL):
    """Setzt Prozess-Priorität (Windows)."""
    try:
        p = psutil.Process(os.getpid())
        p.nice(priority)
        logger.info(f"Process priority set to {priority.name}")
    except Exception as e:
        logger.warning(f"Failed to set process priority: {e}")

def set_thread_priority_low():
    """Setzt Thread-Priorität niedrig für Background-Tasks."""
    import ctypes
    
    try:
        # Windows-specific
        THREAD_PRIORITY_BELOW_NORMAL = -1
        ctypes.windll.kernel32.SetThreadPriority(
            ctypes.windll.kernel32.GetCurrentThread(),
            THREAD_PRIORITY_BELOW_NORMAL
        )
    except:
        pass  # Nicht kritisch

class ResourceManager:
    """Verwaltet System-Ressourcen adaptiv."""
    
    def __init__(self, monitor: HardwareMonitor = None):
        self.monitor = monitor or HardwareMonitor()
        self.max_concurrent_ai_tasks = 2
        self._current_ai_tasks = 0
    
    def can_start_ai_task(self) -> tuple[bool, str]:
        """Prüft ob ein AI-Task gestartet werden kann."""
        
        # Concurrent Task Limit
        if self._current_ai_tasks >= self.max_concurrent_ai_tasks:
            return False, f"Max AI tasks reached ({self.max_concurrent_ai_tasks})"
        
        # Hardware Check
        if self.monitor.is_available:
            should_throttle, reason = self.monitor.should_throttle()
            if should_throttle:
                return False, f"System throttled: {reason}"
        
        return True, "OK"
    
    def start_ai_task(self) -> bool:
        """Registriert Start eines AI-Tasks."""
        can_start, reason = self.can_start_ai_task()
        if can_start:
            self._current_ai_tasks += 1
            return True
        logger.warning(f"AI task blocked: {reason}")
        return False
    
    def end_ai_task(self):
        """Registriert Ende eines AI-Tasks."""
        self._current_ai_tasks = max(0, self._current_ai_tasks - 1)
```

---

## 5. VRAM Management

```python
def estimate_model_vram(model_path: Path, precision: str = "fp16") -> int:
    """Schätzt VRAM-Bedarf eines ONNX Models."""
    
    file_size_mb = model_path.stat().st_size / (1024 * 1024)
    
    # Grobe Schätzung: Model + Aktivierungen + Overhead
    # FP16 ist halb so groß wie FP32
    multiplier = 1.0 if precision == "fp16" else 2.0
    
    # Model Weights + ~50% für Aktivierungen + 20% Overhead
    estimated_vram = file_size_mb * multiplier * 1.7
    
    return int(estimated_vram)

def can_load_model(
    model_path: Path,
    gpu_info: GPUInfo = None,
    monitor: HardwareMonitor = None,
    safety_margin_mb: int = 500
) -> tuple[bool, str]:
    """Prüft ob genug VRAM für Model verfügbar ist."""
    
    if gpu_info is None:
        gpu_info = detect_gpu()
    
    estimated_vram = estimate_model_vram(model_path)
    
    # Wenn kein VRAM-Monitoring verfügbar
    if gpu_info.vram_mb == 0:
        return True, "VRAM unknown, proceeding"
    
    # Mit Monitoring
    if monitor and monitor.is_available:
        metrics = monitor.get_metrics()
        if metrics and metrics.vram_total_mb > 0:
            available = metrics.vram_total_mb - metrics.vram_used_mb
            if available - safety_margin_mb < estimated_vram:
                return False, f"Not enough VRAM: {available:.0f}MB available, {estimated_vram}MB needed"
            return True, f"VRAM OK: {available:.0f}MB available"
    
    # Ohne Monitoring: Prüfe gegen Total VRAM
    if gpu_info.vram_mb < estimated_vram + safety_margin_mb:
        return False, f"Total VRAM too low: {gpu_info.vram_mb}MB, {estimated_vram}MB needed"
    
    return True, f"VRAM should be sufficient: {gpu_info.vram_mb}MB total"
```

---

## Checkliste: Hardware Control

### GPU Detection
- [ ] AMD GPU korrekt erkannt?
- [ ] VRAM-Größe ermittelt?
- [ ] AMF Encoder-Support geprüft?

### Monitoring
- [ ] LibreHardwareMonitor läuft?
- [ ] Metriken werden abgerufen?
- [ ] Throttling-Schwellen sinnvoll?

### FFmpeg
- [ ] h264_amf verfügbar (AMD)?
- [ ] Fallback zu Software-Encoder?
- [ ] Encoding-Qualität akzeptabel?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| GPU nicht erkannt | WMI fehlt / Treiber | `pip install wmi`, Treiber updaten |
| LHM nicht erreichbar | Service nicht gestartet | LHM mit Web Server starten |
| h264_amf nicht verfügbar | Alte Treiber | AMD Treiber aktualisieren |
| VRAM Überlauf | Zu viele Models geladen | `can_load_model()` vorher prüfen |
| Langsames Encoding | Software Fallback aktiv | AMD AMF Encoder installieren |
