"""
DEPRECATED: PacingSmartDirector wurde konsolidiert.

Die kanonische Implementierung befindet sich in:
    pb_studio.ai.smart_director.SmartDirector

Diese Datei re-exportiert SmartDirector für Rückwärtskompatibilität.
Migration: Imports auf `from pb_studio.ai.smart_director import SmartDirector` umstellen.
"""

import warnings
from pb_studio.ai.smart_director import SmartDirector

warnings.warn(
    "pacing.smart_director ist veraltet. Nutze ai.smart_director.SmartDirector",
    DeprecationWarning,
    stacklevel=2,
)

# Re-Export für Rückwärtskompatibilität
PacingSmartDirector = SmartDirector

__all__ = ["PacingSmartDirector", "SmartDirector"]
