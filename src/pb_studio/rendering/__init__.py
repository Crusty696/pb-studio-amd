"""Rendering & Export Module for PB_studio AMD.

Stellt folgende Klassen bereit:
- RenderEngine + RenderConfig: GPU-Rendering mit AMD AMF
- PreviewGenerator: Schnelle 90s-Vorschau
- BatchRenderer: Chunk-basierter Export
- RenderService: Timeline-Rendering mit Normalisierung
- ProxyService: Optimierte Proxy-Videos
"""

try:
    from .render_engine import RenderEngine, RenderConfig
except ImportError:
    RenderEngine = None
    RenderConfig = None

try:
    from .preview_renderer import PreviewGenerator, TimelineEntry
except ImportError:
    PreviewGenerator = None
    TimelineEntry = None

try:
    from .final_renderer import BatchRenderer
except ImportError:
    BatchRenderer = None

try:
    from .render_service import RenderService
except ImportError:
    RenderService = None

try:
    from .proxy_service import ProxyService
except ImportError:
    ProxyService = None

__all__ = [
    "RenderEngine", "RenderConfig",
    "PreviewGenerator", "TimelineEntry",
    "BatchRenderer",
    "RenderService",
    "ProxyService",
]
