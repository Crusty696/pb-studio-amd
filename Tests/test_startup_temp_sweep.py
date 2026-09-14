"""Der Startup-Sweeper muss auch verwaiste Stage-Dateien (`.*.tmp`) entfernen.

Seit die Save-Pfade eindeutige uuid4-Stage-Namen benutzen, ueberschreibt kein
spaeterer Save mehr die Leiche eines harten Abbruchs zwischen ``write_text``
und ``os.replace``. Ohne Sweep waechst die Menge unbegrenzt.

Die Altersgrenze ist Teil des Vertrags: ohne sie loescht der Sweep die
Stage-Datei eines gerade laufenden Saves.
"""

import time
import uuid
from pathlib import Path

import backend.main
from backend.main import _sweep_stale_temp_artifacts

_DAY = 24 * 3600
_HEX = uuid.uuid4().hex  # echter Token derselben Herkunft wie im Produktionspfad


def _age(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    import os
    os.utime(path, (stamp, stamp))


def test_old_hidden_stage_file_is_removed(tmp_path):
    stale = tmp_path / f".project.json.{_HEX}.tmp"
    stale.write_text("x", encoding="utf-8")
    _age(stale, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 1
    assert not stale.exists()


def test_fresh_hidden_stage_file_survives(tmp_path):
    """Schutz vor dem Loeschen der Stage-Datei eines laufenden Saves."""
    fresh = tmp_path / f".project.json.{_HEX}.tmp"
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


def test_rollback_stage_file_is_removed(tmp_path):
    """``_restore_file_snapshot`` haengt zusaetzlich ``.rollback`` an."""
    stale = tmp_path / f".project.json.{_HEX}.rollback.tmp"
    stale.write_text("x", encoding="utf-8")
    _age(stale, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 1
    assert not stale.exists()


def test_timeline_stage_file_is_removed(tmp_path):
    """Basenamen mit Punkt (``timeline.json``) muessen mitgetroffen werden."""
    stale = tmp_path / f".timeline.json.{_HEX}.tmp"
    stale.write_text("x", encoding="utf-8")
    _age(stale, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 1
    assert not stale.exists()


def test_foreign_hidden_tmp_file_is_never_touched(tmp_path):
    """Kern der Einschraenkung: fremde Dotfiles sind potenzielle Nutzerdaten.

    Ein liegengebliebener Fremd-Dotfile ist harmlos, eine geloeschte
    Fremddatei nicht.
    """
    foreign = tmp_path / ".fremdwerkzeug.tmp"
    foreign.write_text("x", encoding="utf-8")
    _age(foreign, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 0
    assert foreign.exists()


def test_hidden_tmp_without_hex_token_is_never_touched(tmp_path):
    """Nur der 32-stellige uuid4-Hex-Block gehoert uns."""
    lookalike = tmp_path / ".timeline.json.nichthex.tmp"
    lookalike.write_text("x", encoding="utf-8")
    _age(lookalike, 3 * _DAY)

    assert _sweep_stale_temp_artifacts(tmp_path) == 0
    assert lookalike.exists()


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


def test_sweep_is_wired_into_the_lifespan():
    """Waechter gegen Producer-ohne-Consumer.

    Die Funktion wurde aus dem ``lifespan`` herausgezogen, um sie testbar zu
    machen. Genau dadurch koennte ein spaeterer Refactor den Aufruf entfernen,
    ohne dass ein Test rot wird. Statisch geprueft (AST), weil ein echter
    Lifespan-Lauf Recovery, Modellinventar und Watchdog-Tasks startet.
    """
    import ast

    source = Path(backend.main.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    lifespan_node = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan"
    )
    called = {
        node.func.id
        for node in ast.walk(lifespan_node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_sweep_stale_temp_artifacts" in called, (
        "lifespan ruft _sweep_stale_temp_artifacts nicht mehr auf - "
        "der Startup-Sweep waere wirkungslos"
    )
