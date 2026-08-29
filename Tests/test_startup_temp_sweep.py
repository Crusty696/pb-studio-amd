"""Der Startup-Sweeper muss auch verwaiste Stage-Dateien (`.*.tmp`) entfernen.

Seit die Save-Pfade eindeutige uuid4-Stage-Namen benutzen, ueberschreibt kein
spaeterer Save mehr die Leiche eines harten Abbruchs zwischen ``write_text``
und ``os.replace``. Ohne Sweep waechst die Menge unbegrenzt.

Die Altersgrenze ist Teil des Vertrags: ohne sie loescht der Sweep die
Stage-Datei eines gerade laufenden Saves.
"""

import time
from pathlib import Path

from backend.main import _sweep_stale_temp_artifacts

_DAY = 24 * 3600


def _age(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    import os
    os.utime(path, (stamp, stamp))


def test_old_hidden_stage_file_is_removed(tmp_path):
    stale = tmp_path / ".project.json.abc123.tmp"
    stale.write_text("x", encoding="utf-8")
    _age(stale, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 1
    assert not stale.exists()


def test_fresh_hidden_stage_file_survives(tmp_path):
    """Schutz vor dem Loeschen der Stage-Datei eines laufenden Saves."""
    fresh = tmp_path / ".project.json.def456.tmp"
    fresh.write_text("x", encoding="utf-8")

    assert _sweep_stale_temp_artifacts(tmp_path) == 0
    assert fresh.exists()


def test_visible_tmp_file_is_never_touched(tmp_path):
    """Der Sweep greift nur die Hauskonvention, nicht jede fremde .tmp-Datei."""
    visible = tmp_path / "foo.tmp"
    visible.write_text("x", encoding="utf-8")
    _age(visible, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 0
    assert visible.exists()


def test_stale_temp_render_dir_still_removed(tmp_path):
    """Das bestehende Verhalten bleibt erhalten."""
    temp_dir = tmp_path / "Projekt" / ".temp_render"
    temp_dir.mkdir(parents=True)
    (temp_dir / "chunk.mp4").write_bytes(b"x")
    _age(temp_dir, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 1
    assert not temp_dir.exists()


def test_fresh_temp_render_dir_survives(tmp_path):
    temp_dir = tmp_path / "Projekt" / ".temp_render"
    temp_dir.mkdir(parents=True)

    assert _sweep_stale_temp_artifacts(tmp_path) == 0
    assert temp_dir.exists()
