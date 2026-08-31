"""Waechter: `beat_grid_provenance` ueberlebt den Neustart.

Befund 2026-08-31: das Feld erschien in der API-Antwort und im
Checkpoint-Merge, wurde aber nie persistiert - `AppState.update_audio_analysis`
kannte keinen Parameter dafuer, und `_load_index` restaurierte es nicht. Nach
einem Neustart war die Rasterherkunft weg.

Das ist das Producer-ohne-Consumer-Muster in seiner zweiten Form: ein Wert
entsteht korrekt, hat aber keinen Abnehmer, der ihn haelt. Diese Tests pruefen
die vollstaendige Kette Router -> AppState -> Datenbank -> Neuladen.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

APP_STATE = REPO_ROOT / "backend" / "app_state.py"
AUDIO_ROUTER = REPO_ROOT / "backend" / "routers" / "audio_router.py"

FIELD = "beat_grid_provenance"


def _function_named(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} nicht in {path.name} gefunden")


def test_update_audio_analysis_accepts_the_field() -> None:
    """Ohne Parameter kann der Wert die Persistenzschicht gar nicht erreichen."""
    function = _function_named(APP_STATE, "update_audio_analysis")
    names = [arg.arg for arg in function.args.args + function.args.kwonlyargs]
    assert FIELD in names, (
        "update_audio_analysis nimmt beat_grid_provenance nicht entgegen; "
        "der Wert kann dann nicht persistiert werden"
    )


def test_app_state_writes_the_field_to_both_stores() -> None:
    """Es gibt zwei Speicherorte - ai_data (DB) und den Laufzeit-Cache."""
    source = APP_STATE.read_text(encoding="utf-8")
    assert f'ai_data["{FIELD}"]' in source, (
        "beat_grid_provenance wird nicht nach ai_data geschrieben (keine "
        "Persistenz in der Datenbank)"
    )
    assert f'cache_update["{FIELD}"]' in source, (
        "beat_grid_provenance wird nicht in den Laufzeit-Cache geschrieben"
    )


def test_load_index_restores_the_field() -> None:
    """Ohne Restore beim Laden ist die Persistenz wertlos."""
    source = APP_STATE.read_text(encoding="utf-8")
    assert f'ai_data.get(\n                                "{FIELD}"' in source or (
        f'"{FIELD}": ai_data.get(' in source
    ), "_load_index restauriert beat_grid_provenance nicht aus ai_data"


def test_legacy_rows_are_marked_unavailable_not_plausible() -> None:
    """Bestandsdaten duerfen nicht als geprueft ausgegeben werden.

    Clips, die vor C-3 analysiert wurden, tragen kein Raster-Urteil. Sie als
    `plausible` zu fuehren waere eine Behauptung ueber nie geprueftes Material -
    genau die Sorte stiller Unwahrheit, gegen die die Provenance eingebaut wurde.
    """
    source = APP_STATE.read_text(encoding="utf-8")
    marker = f'"{FIELD}": ai_data.get('
    start = source.index(marker)
    block = source[start:start + 700]
    assert '"legacy_cache"' in block, "Altbestand wird nicht als solcher markiert"
    assert '"unavailable"' in block, "Altbestand bekommt keinen ehrlichen Status"
    assert '"plausible"' not in block, (
        "Altbestand wird als plausible ausgegeben, obwohl er nie geprueft wurde"
    )


def test_router_passes_the_field_at_every_persisting_call() -> None:
    """Jeder Aufruf, der downbeat_provenance persistiert, muss auch das Raster halten.

    Beide Werte stammen aus demselben Analyselauf. Bleibt einer zurueck,
    entsteht ein Datensatz mit halber Herkunft.
    """
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    downbeat_calls = source.count("downbeat_provenance=")
    grid_calls = source.count(f"{FIELD}=")
    assert grid_calls >= downbeat_calls, (
        f"{downbeat_calls} Aufrufe persistieren downbeat_provenance, aber nur "
        f"{grid_calls} auch beat_grid_provenance"
    )
