"""Hashvergleich aller kritischen Projektdateien."""
import hashlib
import os

PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"

critical_files = [
    "requirements.txt",
    "backend/routers/audio_router.py",
    "backend/routers/video_router.py",
    "backend/routers/render_router.py",
    "backend/routers/project_router.py",
    "backend/routers/pacing_router.py",
    "backend/routers/events_router.py",
    "backend/schemas/audio_schemas.py",
    "backend/schemas/video_schemas.py",
    "backend/schemas/render_schemas.py",
    "backend/schemas/pacing_schemas.py",
    "backend/schemas/project_schemas.py",
    "backend/app_state.py",
    "backend/dependencies.py",
    "backend/config.py",
    "backend/main.py",
    "src/pb_studio/audio/analyzer.py",
    "src/pb_studio/audio/beat_detector.py",
    "src/pb_studio/audio/spectral_analyzer.py",
    "src/pb_studio/audio/structure_analyzer.py",
    "src/pb_studio/audio/key_detector.py",
    "src/pb_studio/audio/waveform_analyzer.py",
    "src/pb_studio/video/raft.py",
    "src/pb_studio/video/scene_detect.py",
    "src/pb_studio/core/vram_budget_manager.py",
    "PBStudio.UI/Services/ApiClient.cs",
    "PBStudio.UI/Services/IApiClient.cs",
    "PBStudio.UI/ViewModels/AudioViewModel.cs",
    "PBStudio.UI/ViewModels/VideoViewModel.cs",
    "PBStudio.UI/ViewModels/DirectorViewModel.cs",
    "PBStudio.UI/ViewModels/RenderViewModel.cs",
    "PBStudio.UI/PBStudio.UI.csproj",
]

for f in critical_files:
    path = os.path.join(PROJECT, f)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            h = hashlib.md5(fh.read()).hexdigest()[:12]
        sz = os.path.getsize(path)
        print(f"OK  {h} {sz:>8}B  {f}")
    else:
        print(f"MISSING                 {f}")
