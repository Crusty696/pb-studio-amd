"""Die generierte Timeline darf beim Projektwechsel und beim Schliessen nicht verloren gehen.

Belegter Defekt: `state.set_timeline(...)` aus der Pacing-Engine schreibt nur in den
RAM. Einziger Produktions-Schreiber von timeline.json war `_save_project_in_context`.
`close_project` und `_activate_project` riefen `state.reset()` bzw. leerten den State,
ohne vorher zu persistieren.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

from backend import _brain_singleton
from backend.app_state import AppState
from backend.routers.project_router import (
    _load_timeline_into_state,
    close_project,
    persist_timeline_for_context,
)

project_router = importlib.import_module("backend.routers.project_router")


def _make_video_file(tmp_path: Path) -> Path:
    video = tmp_path / "clip_one.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return video


def _timeline_entries() -> list[dict]:
    """Kanonisches Runtime-Format: clip_id ist ein String, Zeitfelder start_time/end_time."""
    return [
        {
            "clip_id": "clip_1",
            "start_time": 0.0,
            "end_time": 2.5,
            "metadata": {"trigger_type": "beat"},
        },
        {
            "clip_id": "clip_1",
            "start_time": 2.5,
            "end_time": 5.0,
            "metadata": {"trigger_type": "beat"},
        },
    ]


def _state_with_timeline(tmp_path: Path, video: Path) -> AppState:
    state = AppState()
    state.current_project = {
        "name": tmp_path.name,
        "path": str(tmp_path),
        "db_project_id": 7,
    }
    state.video_clips[1] = {"id": 1, "path": str(video), "name": video.name}
    state.set_timeline(_timeline_entries())
    return state


def _reader_state(video: Path) -> AppState:
    reader = AppState()
    reader.video_clips[1] = {"id": 1, "path": str(video), "name": video.name}
    return reader


def _neutralize_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_brain_singleton, "clear_project_state", lambda: None)
    monkeypatch.setattr(
        _brain_singleton, "current_project_state_identity", lambda: None
    )


def test_persist_timeline_writes_reader_compatible_payload(tmp_path: Path) -> None:
    """Round-Trip: der echte Leser muss die geschriebene Datei wieder verstehen."""
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)

    assert persist_timeline_for_context(state, tmp_path) is True

    timeline_path = tmp_path / "timeline.json"
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), "Der Leser erwartet ein Dict, keine nackte Liste"
    assert "timeline" in payload and "audio_path" in payload

    reader = _reader_state(video)
    assert _load_timeline_into_state(tmp_path, reader) is True
    loaded = reader.get_timeline_snapshot()
    assert len(loaded) == 2
    assert [entry["start_time"] for entry in loaded] == [0.0, 2.5]
    assert [entry["end_time"] for entry in loaded] == [2.5, 5.0]
    assert loaded[0]["clip_id"] == "clip_1"
    assert not list(tmp_path.glob(".timeline.json.*.tmp"))


def test_persist_timeline_returns_false_without_timeline(tmp_path: Path) -> None:
    state = AppState()
    assert persist_timeline_for_context(state, tmp_path) is False
    assert not (tmp_path / "timeline.json").exists()


def test_close_project_persists_timeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video = _make_video_file(tmp_path)
    state = _state_with_timeline(tmp_path, video)
    _neutralize_brain(monkeypatch)

    asyncio.run(close_project(state))

    assert state.get_timeline_snapshot() == []
    reader = _reader_state(video)
    assert _load_timeline_into_state(tmp_path, reader) is True
    assert len(reader.get_timeline_snapshot()) == 2


def test_activate_project_persists_previous_timeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_a = tmp_path / "project-a"
    project_a.mkdir()
    project_b = tmp_path / "project-b"
    project_b.mkdir()
    video = _make_video_file(project_a)
    state = _state_with_timeline(project_a, video)
    monkeypatch.setattr(
        project_router, "_bind_brain_to_project", lambda *_a, **_kw: None
    )

    asyncio.run(
        project_router._activate_project(
            state,
            project_b,
            {"name": "project-b", "path": str(project_b), "db_project_id": 9},
            None,
        )
    )

    assert state.get_timeline_snapshot() == []
    assert not (project_b / "timeline.json").exists()
    reader = _reader_state(video)
    assert _load_timeline_into_state(project_a, reader) is True
    assert len(reader.get_timeline_snapshot()) == 2
