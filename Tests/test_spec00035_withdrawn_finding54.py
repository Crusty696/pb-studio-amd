"""Evidence for withdrawn finding 54: semantic-off remains off in live pacing."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

pytestmark = pytest.mark.unauthorized_backend


def test_service_semantic_off_passes_no_prompt_or_semantic_selection(
    monkeypatch, tmp_path
):
    from pb_studio.pacing.clip_selector import ClipSelector
    from pb_studio.services.pacing_service import PacingService

    audio = tmp_path / "semantic_off.wav"
    sample_rate = 22_050
    samples = np.zeros(sample_rate * 4, dtype=np.float32)
    sf.write(audio, samples, sample_rate)
    clips = [
        {
            "id": clip_id,
            "name": f"clip-{clip_id}",
            "file_path": str(tmp_path / f"clip-{clip_id}.mp4"),
            "duration": 4.0,
            "motion_score": float(clip_id),
        }
        for clip_id in (1, 2)
    ]
    for clip in clips:
        (tmp_path / f"clip-{clip['id']}.mp4").touch()

    prompts: list[str | None] = []
    original_select_clip = ClipSelector.select_clip

    def capture_selection(self, *args, **kwargs):
        prompts.append(kwargs.get("prompt"))
        assert self.use_semantic is False
        return original_select_clip(self, *args, **kwargs)

    def reject_semantic_selection(*_args, **_kwargs):
        pytest.fail("semantic selector entered while semantic matching is disabled")

    monkeypatch.setattr(ClipSelector, "select_clip", capture_selection)
    monkeypatch.setattr(ClipSelector, "_select_semantic", reject_semantic_selection)

    cuts = PacingService().generate_cut_list(
        audio_path=str(audio),
        clips=clips,
        pacing_config={
            "expected_bpm": 120,
            "use_motion_matching": True,
            "use_semantic_matching": False,
            "use_structure_awareness": False,
            "trigger_settings": {
                "beat_weight": 1.0,
                "onset_weight": 0.0,
                "kick_weight": 0.0,
                "snare_weight": 0.0,
                "hihat_weight": 0.0,
                "energy_weight": 0.0,
                "min_clip_length": 0.5,
                "max_clip_length": 2.0,
            },
        },
        total_duration=4.0,
        cached_analysis={
            "beats": [
                {"time": t, "strength": 1.0}
                for t in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
            ],
            "bpm": 120.0,
            "duration_seconds": 4.0,
        },
    )

    assert cuts
    assert prompts
    assert all(prompt is None for prompt in prompts)
