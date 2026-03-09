"""FastAPI Router für PB Studio AMD Backend."""

from .project_router import router as project_router
from .audio_router import router as audio_router
from .video_router import router as video_router
from .pacing_router import router as pacing_router
from .render_router import router as render_router
from .events_router import router as events_router

__all__ = [
    "project_router",
    "audio_router",
    "video_router",
    "pacing_router",
    "render_router",
    "events_router",
]
