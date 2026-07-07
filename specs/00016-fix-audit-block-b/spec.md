# Spec - Block B Audit Fixes (Production Readiness)

## Requirements
Address the 20+ remaining high-priority (orange) issues from the Full-Stack Audit 2026-06-10. These issues cover process control, database connection locking, render pipeline codec normalization, WPF bindings and collection synchronization, and DirectML-specific configuration issues.

## Scope
- Backend FastAPI (pacing_router, events_router, main.py)
- Rendering Core (render_service, preview_renderer)
- WPF Frontend (App.xaml, PythonBridgeService, controls, ViewModels)
- Audio Core (audio_router, beat_detector, structure_analyzer)
- Scripts (setup, model export scripts)
