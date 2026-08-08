from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_video_and_director_progress_are_correlated():
    video_vm = (
        ROOT / "PBStudio.UI" / "ViewModels" / "VideoLibraryViewModel.cs"
    ).read_text(encoding="utf-8")
    director_vm = (
        ROOT / "PBStudio.UI" / "ViewModels" / "DirectorViewModel.cs"
    ).read_text(encoding="utf-8")
    pacing_router = (
        ROOT / "backend" / "routers" / "pacing_router.py"
    ).read_text(encoding="utf-8")
    video_router = (
        ROOT / "backend" / "routers" / "video_router.py"
    ).read_text(encoding="utf-8")

    assert "_activeAnalysisClipId" in video_vm
    assert "private bool IsActiveAnalysisEvent(int clipId)" in video_vm
    assert "_activeAnalysisClipId == clipId" in video_vm
    assert "_projectService.IsCurrent(projectContext)" in video_vm
    assert 'e.TaskId != "video_import"' in video_vm
    assert "_activePacingAudioClipId" in director_vm
    assert 'e.EventType != "pacing_progress"' in director_vm
    assert "e.ClipId != _activePacingAudioClipId.Value" in director_vm
    assert '"task_id": "video_import"' in video_router
    assert '"task_id": f"pacing:{audio_clip_id}"' in pacing_router
