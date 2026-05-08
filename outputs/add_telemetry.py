"""Additiv Telemetrie-Erweiterungen in vram_budget_manager.py einfuegen."""
from pathlib import Path

PATH = Path("src/pb_studio/core/vram_budget_manager.py")
src = PATH.read_text(encoding="utf-8")

# ----- 1) Modul-Konstanten + Helpers + TelemetryEntry-Dataclass --------------
TELEMETRY_BLOCK = '''

# =============================================================================
# Telemetry --- Histogram-Buckets + TelemetryEntry-Aggregat
# =============================================================================

# Latenz-Buckets (ms): jeweils "<= upper" Inklusiv-Grenze; alles darueber -> "+infms"
DURATION_BUCKETS_MS = (50, 200, 500, 1000, 2500, 5000, 10000, 30000, 60000)

# VRAM-Peak-Buckets (MB): jeweils "<= upper" Inklusiv-Grenze; alles darueber -> "+infMB"
VRAM_BUCKETS_MB = (100, 250, 500, 1000, 2000, 4000, 6000, 8000)


def _duration_bucket_label(ms: float) -> str:
    """Bucket-Label fuer Dauer-Wert (ms). Inklusiv-Obergrenze."""
    for upper in DURATION_BUCKETS_MS:
        if ms <= float(upper):
            return f"<= {upper}ms"
    return "+infms"


def _vram_bucket_label(mb: float) -> str:
    """Bucket-Label fuer VRAM-Peak (MB). Inklusiv-Obergrenze."""
    for upper in VRAM_BUCKETS_MB:
        if mb <= float(upper):
            return f"<= {upper}MB"
    return "+infMB"


def _empty_duration_histogram() -> Dict[str, int]:
    h = {f"<= {u}ms": 0 for u in DURATION_BUCKETS_MS}
    h["+infms"] = 0
    return h


def _empty_vram_histogram() -> Dict[str, int]:
    h = {f"<= {u}MB": 0 for u in VRAM_BUCKETS_MB}
    h["+infMB"] = 0
    return h


@dataclass
class TelemetryEntry:
    """Aggregierte Telemetrie pro model_id."""
    model_id: str
    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duration_min_ms: Optional[float] = None
    duration_max_ms: Optional[float] = None
    duration_sum_ms: float = 0.0
    vram_min_mb: Optional[float] = None
    vram_max_mb: Optional[float] = None
    duration_histogram: Dict[str, int] = field(default_factory=_empty_duration_histogram)
    vram_histogram: Dict[str, int] = field(default_factory=_empty_vram_histogram)
    last_error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        avg = (self.duration_sum_ms / self.count) if self.count > 0 else None
        return {
            "model_id": self.model_id,
            "count": self.count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "duration_ms": {
                "min": self.duration_min_ms,
                "max": self.duration_max_ms,
                "avg": avg,
                "histogram": dict(self.duration_histogram),
            },
            "vram_peak_mb": {
                "min": self.vram_min_mb,
                "max": self.vram_max_mb,
                "histogram": dict(self.vram_histogram),
            },
            "last_error": self.last_error,
        }


'''

ANCHOR_1_OLD = '    # DirectML Session Overhead\n    "directml_overhead": 150,    # Base DirectML overhead per session\n}\n\n\nclass VRAMBudgetManager:'
ANCHOR_1_NEW = '    # DirectML Session Overhead\n    "directml_overhead": 150,    # Base DirectML overhead per session\n}\n' + TELEMETRY_BLOCK + '\nclass VRAMBudgetManager:'

assert src.count(ANCHOR_1_OLD) == 1, f"Anchor 1 nicht eindeutig: {src.count(ANCHOR_1_OLD)}"
src = src.replace(ANCHOR_1_OLD, ANCHOR_1_NEW)

# ----- 2) Telemetry-State im __init__ initialisieren -------------------------
ANCHOR_2_OLD = '        # Threading\n        self._registry_lock = threading.RLock()\n\n        self._initialized = True'
ANCHOR_2_NEW = '''        # Threading
        self._registry_lock = threading.RLock()

        # Telemetry --- pro model_id eine TelemetryEntry, separater Lock
        self._telemetry: Dict[str, TelemetryEntry] = {}
        self._telemetry_lock = threading.RLock()

        self._initialized = True'''

assert src.count(ANCHOR_2_OLD) == 1, f"Anchor 2 nicht eindeutig: {src.count(ANCHOR_2_OLD)}"
src = src.replace(ANCHOR_2_OLD, ANCHOR_2_NEW)

# ----- 3) Drei Methoden auf VRAMBudgetManager nach is_model_loaded -----------
METHODS_BLOCK = '''
    # =========================================================================
    # Telemetry --- Beobachtungen, Histogram, Snapshot, Reset
    # =========================================================================

    def record_task_observation(
        self,
        model_id: str,
        duration_ms: float,
        vram_peak_mb: float,
        success: bool = True,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Eine GPU-Task-Beobachtung in die Telemetrie eintragen."""
        try:
            mid = (model_id or "").strip() or "_unknown"
            d = max(0.0, float(duration_ms))
            v = max(0.0, float(vram_peak_mb))

            with self._telemetry_lock:
                entry = self._telemetry.get(mid)
                if entry is None:
                    entry = TelemetryEntry(model_id=mid)
                    self._telemetry[mid] = entry

                entry.count += 1
                if success:
                    entry.success_count += 1
                else:
                    entry.failure_count += 1
                    if error is not None:
                        entry.last_error = dict(error)

                # Min/Max/Sum fuer Dauer
                if entry.duration_min_ms is None or d < entry.duration_min_ms:
                    entry.duration_min_ms = d
                if entry.duration_max_ms is None or d > entry.duration_max_ms:
                    entry.duration_max_ms = d
                entry.duration_sum_ms += d

                # Min/Max fuer VRAM-Peak
                if entry.vram_min_mb is None or v < entry.vram_min_mb:
                    entry.vram_min_mb = v
                if entry.vram_max_mb is None or v > entry.vram_max_mb:
                    entry.vram_max_mb = v

                d_label = _duration_bucket_label(d)
                v_label = _vram_bucket_label(v)
                entry.duration_histogram[d_label] = entry.duration_histogram.get(d_label, 0) + 1
                entry.vram_histogram[v_label] = entry.vram_histogram.get(v_label, 0) + 1
        except Exception as exc:  # pragma: no cover --- Telemetrie darf Task nie kippen
            logger.warning(f"record_task_observation fehlgeschlagen: {exc}")

    def get_telemetry(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Snapshot der Telemetrie. None -> alle Modelle, sonst einzelner Eintrag."""
        with self._telemetry_lock:
            if model_id is not None:
                mid = (model_id or "").strip() or "_unknown"
                entry = self._telemetry.get(mid)
                if entry is None:
                    entry = TelemetryEntry(model_id=mid)
                return entry.to_dict()

            models_snap = {mid: e.to_dict() for mid, e in self._telemetry.items()}
            total_obs = sum(e.count for e in self._telemetry.values())
            return {
                "models": models_snap,
                "summary": {
                    "models_tracked": len(self._telemetry),
                    "observations": total_obs,
                    "duration_buckets_ms": list(DURATION_BUCKETS_MS),
                    "vram_buckets_mb": list(VRAM_BUCKETS_MB),
                },
            }

    def reset_telemetry(self, model_id: Optional[str] = None) -> None:
        """Telemetrie zuruecksetzen --- entweder nur ein Modell oder komplett."""
        with self._telemetry_lock:
            if model_id is None:
                self._telemetry.clear()
            else:
                mid = (model_id or "").strip() or "_unknown"
                self._telemetry.pop(mid, None)

'''

ANCHOR_3_OLD = '''    def is_model_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded (thread-safe, read budget.is_loaded under lock)."""
        with self._registry_lock:
            budget = self._models.get(model_id)
            if budget is None:
                return False
            return budget.is_loaded  # read while holding lock to avoid race with evict_all


# =========================================================================
# Context Manager for Safe Model Loading
# ========================================================================='''

ANCHOR_3_NEW = '''    def is_model_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded (thread-safe, read budget.is_loaded under lock)."""
        with self._registry_lock:
            budget = self._models.get(model_id)
            if budget is None:
                return False
            return budget.is_loaded  # read while holding lock to avoid race with evict_all
''' + METHODS_BLOCK + '''

# =========================================================================
# Context Manager for Safe Model Loading
# ========================================================================='''

assert src.count(ANCHOR_3_OLD) == 1, f"Anchor 3 nicht eindeutig: {src.count(ANCHOR_3_OLD)}"
src = src.replace(ANCHOR_3_OLD, ANCHOR_3_NEW)

PATH.write_text(src, encoding="utf-8")
print(f"OK: file rewritten, length now {len(src.splitlines())} lines")
