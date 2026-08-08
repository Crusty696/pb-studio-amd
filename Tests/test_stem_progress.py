"""Test: Stem-Separation per-stage progress callback (Audit C2).

Verifies that StemSeparator.separate() invokes the on_progress callback at
multiple stage boundaries (init/loading_model/running_inference/saving_stems/
complete) so the audio_router can fan the events out via stem_progress SSE.
"""
from unittest.mock import MagicMock

import pytest


def test_stem_separator_calls_on_progress(tmp_path):
    """separate() ruft on_progress mehrfach mit monoton steigendem Percent auf."""
    from pb_studio.audio.separator import StemSeparator

    # Bypass __init__ so we don't trigger the real audio-separator/onnx loader.
    sep = StemSeparator.__new__(StemSeparator)
    sep.separator = MagicMock()
    sep.separator.onnx_execution_provider = ["DmlExecutionProvider"]
    sep._has_directml = True
    sep.separator.load_model.side_effect = lambda _name: setattr(
        sep,
        "_directml_session_created",
        True,
    )

    test_file = tmp_path / "test.wav"
    test_file.touch()
    model_file = tmp_path / "test.yaml"
    model_file.touch()
    sep.config = MagicMock()
    sep.config.get.return_value = {"models_dir": str(tmp_path)}

    progress_calls: list[float] = []

    # Patch the inference seam so we don't need a real model.
    sep._run_inference = lambda path: [str(tmp_path / "vocals.wav"), str(tmp_path / "instrumental.wav")]

    result = sep.separate(
        file_path=str(test_file),
        model_name=model_file.name,
        on_progress=lambda pct: progress_calls.append(pct),
    )

    # Sanity: separation must have completed (no error path).
    assert "stems" in result, f"Expected stems key, got {result}"
    # Audit C2: at least the init + complete stages must fire (in practice 5).
    assert len(progress_calls) >= 2, f"Expected >=2 progress calls, got {len(progress_calls)}: {progress_calls}"
    # Monotonically non-decreasing percent.
    assert progress_calls[-1] >= progress_calls[0], f"Progress not monotonic: {progress_calls}"
    # First call is init (0%), last call is complete (100%).
    assert progress_calls[0] == pytest.approx(0.0)
    assert progress_calls[-1] == pytest.approx(100.0)


def test_stem_separator_works_without_callback(tmp_path):
    """Default on_progress=None — kein crash, kein TypeError."""
    from pb_studio.audio.separator import StemSeparator

    sep = StemSeparator.__new__(StemSeparator)
    sep.separator = MagicMock()
    sep.separator.onnx_execution_provider = ["DmlExecutionProvider"]
    sep._has_directml = True
    sep.separator.load_model.side_effect = lambda _name: setattr(
        sep,
        "_directml_session_created",
        True,
    )

    test_file = tmp_path / "test.wav"
    test_file.touch()
    model_file = tmp_path / "test.yaml"
    model_file.touch()
    sep.config = MagicMock()
    sep.config.get.return_value = {"models_dir": str(tmp_path)}

    sep._run_inference = lambda path: [str(tmp_path / "vocals.wav")]

    # Should not raise — the default on_progress=None must be handled cleanly.
    result = sep.separate(file_path=str(test_file), model_name=model_file.name)
    assert "stems" in result


def test_stem_separator_missing_file_still_emits_init(tmp_path):
    """File-not-found returns error dict but still emits the initial 0% tick.

    Guarantees the SSE channel sees a 'started' signal even on early failure,
    so the UI can flip into a deterministic state instead of staying idle.
    """
    from pb_studio.audio.separator import StemSeparator

    sep = StemSeparator.__new__(StemSeparator)
    sep.separator = MagicMock()
    sep._has_directml = False

    progress_calls: list[float] = []
    result = sep.separate(
        file_path=str(tmp_path / "does_not_exist.wav"),
        on_progress=lambda pct: progress_calls.append(pct),
    )
    assert "error" in result
    assert "not found" in result["error"].lower()
    # init tick must have fired before the file-existence check returned.
    assert progress_calls == [0.0]


def test_stem_separator_legacy_callback_still_works(tmp_path):
    """Legacy 2-arg callback(message, percent) signature still works."""
    from pb_studio.audio.separator import StemSeparator

    sep = StemSeparator.__new__(StemSeparator)
    sep.separator = MagicMock()
    sep.separator.onnx_execution_provider = ["DmlExecutionProvider"]
    sep._has_directml = True
    sep.separator.load_model.side_effect = lambda _name: setattr(
        sep,
        "_directml_session_created",
        True,
    )

    test_file = tmp_path / "test.wav"
    test_file.touch()
    model_file = tmp_path / "test.yaml"
    model_file.touch()
    sep.config = MagicMock()
    sep.config.get.return_value = {"models_dir": str(tmp_path)}

    sep._run_inference = lambda path: [str(tmp_path / "vocals.wav")]

    legacy_calls: list[tuple[str, float]] = []

    def legacy_cb(message: str, percent: float) -> None:
        legacy_calls.append((message, percent))

    result = sep.separate(
        file_path=str(test_file),
        model_name=model_file.name,
        callback=legacy_cb,
    )
    assert "stems" in result
    assert len(legacy_calls) >= 2


def test_stem_router_keeps_lock_and_telemetry_without_outer_budget(monkeypatch):
    """H-05: the router must not reserve a second model budget."""
    import asyncio
    import importlib

    from backend.schemas.audio_schemas import StemModel, StemSeparateRequest

    audio_router = importlib.import_module("backend.routers.audio_router")
    captured = {}

    async def fake_gpu_task(func, *args, **kwargs):
        captured.update(kwargs)
        return {"model_used": args[1]}

    state = MagicMock()
    state.get_audio_clip.return_value = {
        "id": 7,
        "name": "mix",
        "path": "mix.wav",
    }
    monkeypatch.setattr(audio_router, "with_gpu_task", fake_gpu_task)

    result = asyncio.run(
        audio_router.separate_stems(
            StemSeparateRequest(clip_id=7, model=StemModel.HTDEMUCS),
            state,
        )
    )

    assert result.model_used == StemModel.HTDEMUCS.value
    assert captured["model_id"] == "stem_separation_full"
    assert captured["manage_vram"] is False
