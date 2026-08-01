"""Static contract for selection-bound video scene loading."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_video_scenes_apply_only_to_current_selection_and_generation():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "VideoLibraryViewModel.cs"
    ).read_text(encoding="utf-8")
    selection = source[
        source.index("partial void OnSelectedClipChanged"):
        source.index("[RelayCommand]", source.index("partial void OnSelectedClipChanged"))
    ]
    load = selection[selection.index("private async Task LoadScenesAsync"):]

    assert "private int _sceneLoadSequence;" in source
    assert "Interlocked.Increment(ref _sceneLoadSequence);" in selection
    assert "IsLoadingScenes = false;" in selection
    assert "var sequence = Interlocked.Increment(ref _sceneLoadSequence);" in load
    assert "sequence != Volatile.Read(ref _sceneLoadSequence)" in load
    assert "SelectedClip?.Id != clipId" in load
    assert "sequence == Volatile.Read(ref _sceneLoadSequence)" in load
    assert "_projectService.IsCurrent(projectContext)" in load
