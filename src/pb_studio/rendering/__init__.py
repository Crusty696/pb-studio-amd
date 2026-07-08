"""Rendering & Export Module for PB_studio AMD.

Stellt folgende Klassen bereit:
- RenderEngine + RenderConfig: GPU-Rendering mit AMD AMF
- PreviewGenerator: Schnelle 90s-Vorschau
- BatchRenderer: Chunk-basierter Export
- RenderService: Timeline-Rendering mit Normalisierung
- ProxyService: Optimierte Proxy-Videos
"""

try:
    from .preview_renderer import PreviewGenerator, TimelineEntry
except ImportError:
    PreviewGenerator = None
    TimelineEntry = None

try:
    from .render_service import RenderService
except ImportError:
    RenderService = None

__all__ = [
    "PreviewGenerator", "TimelineEntry",
    "RenderService",
]
