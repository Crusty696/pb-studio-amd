"""Characterization of the shared Pacing/Export timeline boundary contract."""

from copy import deepcopy

import pytest

from pb_studio.pacing.pacing_models import CutListEntry


@pytest.fixture(params=["legacy", "shared"])
def finalize(request):
    if request.param == "legacy":
        from pb_studio.services.pacing_service import PacingService

        def run(cuts, duration, resolver):
            service = PacingService()
            service._get_clip_duration = resolver
            return service._finalize_cut_list(cuts, duration)

        return run
    from pb_studio.pacing.timeline_finalizer import finalize_cut_list
    return finalize_cut_list


def _unused_probe(path):
    pytest.fail(f"unexpected media probe: {path}")


@pytest.mark.parametrize("duration", [0.0, -1.0])
def test_nonpositive_budget_leaves_list_and_entries_untouched(finalize, duration):
    original = CutListEntry("clip_1", 1.0, 2.0, {"custom": [1]})
    cuts = [original]
    assert finalize(cuts, duration, _unused_probe) is cuts
    assert cuts == [original]
    assert cuts[0] is original


def test_repeats_source_preserving_provenance_only_on_first_segment(finalize):
    original = CutListEntry("clip_1", 1.0, 2.0, {
        "clip_start": 1.0, "source_duration": 2.0,
        "trigger_type": "beat", "trigger_strength": 0.7,
        "trigger_provenance": {"time": 1}, "nested": {"values": [1]},
    })
    before = deepcopy(original)
    cuts = [original]
    assert finalize(cuts, 5.0, _unused_probe) is cuts
    assert [(c.start_time, c.end_time) for c in cuts] == [(0, 2), (2, 4), (4, 5)]
    assert cuts[0].metadata["trigger_provenance"] == {"time": 1}
    assert all("trigger_provenance" not in c.metadata for c in cuts[1:])
    assert all(c.metadata["trigger_type"] == "source_repeat" for c in cuts[1:])
    assert all(c.metadata["boundary_original_start"] == 1.0 for c in cuts)
    assert all(c.metadata["boundary_normalized_end"] == 5.0 for c in cuts)
    cuts[0].metadata["nested"]["values"].append(2)
    assert cuts[1].metadata["nested"]["values"] == [1]
    assert original == before


def test_sort_trim_and_legacy_missing_media_fill_budget(finalize):
    cuts = [CutListEntry("b", 3.0, 4.0), CutListEntry("a", 0.0, 1.0),
            CutListEntry("excluded", 6.0, 8.0)]
    result = finalize(cuts, 6.0, _unused_probe)
    assert result is cuts
    assert [(c.clip_id, c.start_time, c.end_time) for c in result] == [
        ("a", 0.0, 3.0), ("b", 3.0, 6.0)]


def test_existing_source_uses_injected_probe(finalize, tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    calls = []
    def probe(path):
        calls.append(path)
        return 2.0
    cuts = [CutListEntry("a", 0.0, 1.0, {"file_path": str(source)})]
    finalize(cuts, 3.0, probe)
    assert calls == [str(source)]
    assert [(c.start_time, c.end_time) for c in cuts] == [(0, 2), (2, 3)]
    assert all(c.metadata["source_duration"] == 2.0 for c in cuts)


def test_probe_failure_propagates(finalize, tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    def probe(path):
        raise ValueError("unreadable source")
    with pytest.raises(ValueError, match="unreadable source"):
        finalize([CutListEntry("a", 0.0, 1.0, {"file_path": str(source)})], 3, probe)


@pytest.mark.parametrize("clip_path", [
    "clip.mp4",
    "C:/Existing Media/Gr\u00fcne Szene & Take (2) [final].mp4",
])
def test_duration_probe_preserves_command_and_caches_success(monkeypatch, clip_path):
    import subprocess
    from pb_studio.pacing.media_duration import get_clip_duration
    from pb_studio.video import encoder_utils

    calls = []
    monkeypatch.setattr(encoder_utils, "_get_ffprobe_path", lambda: "bound-ffprobe.exe")
    def output(command, **kwargs):
        calls.append((command, kwargs))
        return b'{"format":{"duration":"2.5"}}'
    monkeypatch.setattr(subprocess, "check_output", output)
    cache = {}
    assert get_clip_duration(clip_path, cache) == 2.5
    assert get_clip_duration(clip_path, cache) == 2.5
    assert calls == [(["bound-ffprobe.exe", "-v", "error", "-show_entries",
                       "format=duration", "-of", "json", clip_path],
                      {"stderr": subprocess.STDOUT, "timeout": 30})]


def test_duration_probe_does_not_cache_failures(monkeypatch):
    import subprocess
    from pb_studio.pacing.media_duration import get_clip_duration
    from pb_studio.video import encoder_utils

    monkeypatch.setattr(encoder_utils, "_get_ffprobe_path", lambda: "bound-ffprobe.exe")
    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: b'{}')
    cache = {}
    with pytest.raises(ValueError, match="Konnte Dauer nicht lesen: clip.mp4") as error:
        get_clip_duration("clip.mp4", cache)
    assert isinstance(error.value.__cause__, KeyError)
    assert cache == {}


def test_render_finalizer_avoids_pacing_service_and_preserves_snapshot(monkeypatch):
    from backend.routers.render_router import _finalize_timeline_for_render
    from pb_studio.services.pacing_service import PacingService

    def forbidden(*args, **kwargs):
        pytest.fail("Export constructed the pacing orchestrator")
    monkeypatch.setattr(PacingService, "__init__", forbidden)
    timeline = [{"clip_id": "a", "start_time": 0.0, "end_time": 1.0,
                 "custom": [1], "metadata": {"source_duration": 2.0}}]
    before = deepcopy(timeline)
    result = _finalize_timeline_for_render(timeline, 3.0)
    assert [(c["start_time"], c["end_time"]) for c in result] == [(0, 2), (2, 3)]
    result[0]["custom"].append(2)
    assert result[1]["custom"] == [1]
    assert timeline == before
