"""Waechter fuer die vollstaendige Verdrahtung des Beatgrids.

`src/pb_studio/audio/beat_grid.py` lag zunaechst im Repo, ohne dass es irgendwo
aufgerufen wurde - ein Producer ohne Consumer, das haeufigste Muster in diesem
Projekt. Diese Tests halten jedes Glied der Kette fest:

    Estimator -> Router -> Schema -> Persistenz -> Neuladen -> C#-Record -> XAML

Faellt einer, ist die Kette an genau dieser Stelle gerissen. Ein Test, der nur
prueft, ob das Modul existiert, wuerde das nicht bemerken.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

AUDIO_ROUTER = REPO_ROOT / "backend" / "routers" / "audio_router.py"
AUDIO_SCHEMAS = REPO_ROOT / "backend" / "schemas" / "audio_schemas.py"
APP_STATE = REPO_ROOT / "backend" / "app_state.py"
API_CLIENT = REPO_ROOT / "PBStudio.UI" / "Services" / "ApiClient.cs"
VIEW_MODEL = REPO_ROOT / "PBStudio.UI" / "ViewModels" / "AudioLibraryViewModel.cs"
VIEW = REPO_ROOT / "PBStudio.UI" / "Views" / "AudioLibraryView.xaml"
SNAPSHOT = REPO_ROOT / "PBStudio.UI" / "openapi.snapshot.json"

FIELD = "beat_grid"


def test_estimator_is_importable_and_returns_a_rule() -> None:
    """Das Grid muss eine Regel sein - Anker plus Tempo -, keine Zeitliste."""
    from pb_studio.audio.beat_grid import BeatGrid, estimate_beat_grid  # noqa: F401

    grid = BeatGrid(bpm=120.0, anchor_s=0.25, contrast=3.0, method="test",
                    status="plausible")
    times = grid.beat_times(0.0, 2.0)
    assert len(times) == 4, "aus 120 BPM ueber 2 s muessen 4 Beats folgen"
    assert times[0] == pytest.approx(0.25), "der Anker muss die Phase setzen"
    assert times[1] - times[0] == pytest.approx(0.5)


def test_router_calls_the_estimator() -> None:
    """Ohne Aufruf im Router bleibt der Estimator toter Code."""
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    assert "estimate_beat_grid" in source, (
        "audio_router ruft estimate_beat_grid nicht auf - das Modul waere "
        "wieder ein Producer ohne Consumer"
    )


def test_streaming_path_delivers_a_segmented_grid() -> None:
    """Lange Dateien bekommen ein SEGMENTIERTES Grid, keine Absage.

    Frueher meldete dieser Zweig `method: streaming_path` und lieferte nichts.
    Das war ehrlich, aber unbefriedigend: gerade bei langen DJ-Mixen ist ein
    Grid am wertvollsten. An 800 Segmenten aus 20 Mixen gemessen sitzt ein
    globales Raster in 19 % der Segmente, ein je Segment bestimmtes in 95 %.

    Der Segmentierer laedt fensterweise aus der Datei - ein 188-Minuten-Mix
    waere bei 22050 Hz sonst 995 MB float32 und damit genau das OOM-Szenario
    aus Audit-Befund H-5.
    """
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    assert "segment_beat_grids_from_file" in source, (
        "der Streaming-Zweig ruft den Segmentierer nicht auf"
    )
    assert "segments_as_payload" in source, (
        "das Segment-Ergebnis wird nicht in die Antwortstruktur uebersetzt"
    )


def test_streaming_grid_uses_the_file_reading_variant() -> None:
    """Nicht die Array-Variante - die verlangt das ganze Signal im Speicher."""
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    assert "segment_beat_grids(" not in source.replace(
        "segment_beat_grids_from_file(", ""
    ), (
        "der Router benutzt die Array-Variante segment_beat_grids(); die "
        "verlangt das gesamte Signal und wuerde bei langen Mixen genau den "
        "Voll-Load ausloesen, gegen den H-5 gebaut wurde"
    )


def test_segmentation_failure_is_reported_not_swallowed() -> None:
    """Ein Ausfall darf die Analyse nicht kippen, aber auch nicht stumm bleiben."""
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    assert '"method": "segmentation_failed"' in source, (
        "ein gescheiterter Segmentierungslauf hinterlaesst keine Spur im Feld"
    )


def test_schema_carries_the_field() -> None:
    source = AUDIO_SCHEMAS.read_text(encoding="utf-8")
    assert f"{FIELD}: dict[str, Any]" in source, (
        "AudioAnalysisResult hat kein beat_grid-Feld"
    )


def test_app_state_persists_and_restores_the_field() -> None:
    """Ohne Persistenz ueberlebt das Grid keinen Neustart."""
    source = APP_STATE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "update_audio_analysis":
            names = [a.arg for a in node.args.args + node.args.kwonlyargs]
            assert FIELD in names, "update_audio_analysis nimmt beat_grid nicht entgegen"
            break
    else:
        raise AssertionError("update_audio_analysis nicht gefunden")

    assert f'ai_data["{FIELD}"]' in source, "beat_grid wird nicht in die DB geschrieben"
    assert f'cache_update["{FIELD}"]' in source, "beat_grid fehlt im Laufzeit-Cache"
    assert f'"{FIELD}": ai_data.get(' in source, "_load_index restauriert beat_grid nicht"


def test_router_passes_the_field_when_persisting() -> None:
    source = AUDIO_ROUTER.read_text(encoding="utf-8")
    assert source.count(f"{FIELD}=") >= 2, (
        "nicht alle persistierenden Aufrufe reichen beat_grid durch"
    )


def test_merge_whitelist_carries_the_field() -> None:
    """Der Merge filtert nach einer Whitelist - fehlt das Feld, ist es weg.

    Beim ersten Live-Lauf war genau das der Bruch: das Grid wurde berechnet
    und geloggt ("Beatgrid ... 94.67 BPM"), aber
    `_merge_audio_analysis_result` liess es fallen, weil
    `_AUDIO_STAGE_RESULT_FIELDS["beats"]` es nicht kannte. Die API lieferte
    ein leeres Dict.

    Der urspruengliche Waechter hat das NICHT bemerkt, weil er nur pruefte,
    ob der Feldname irgendwo in der Datei vorkommt. Vorkommen ist nicht
    Durchleitung.
    """
    from backend.routers.audio_router import _AUDIO_STAGE_RESULT_FIELDS

    assert FIELD in _AUDIO_STAGE_RESULT_FIELDS["beats"], (
        "beat_grid fehlt in der Merge-Whitelist der beats-Stufe - der Wert "
        "wird berechnet und danach verworfen"
    )


def test_merge_actually_carries_the_field_through() -> None:
    """Gegenprobe an der echten Merge-Funktion, nicht an ihrer Konfiguration."""
    from backend.routers.audio_router import _merge_audio_analysis_result

    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    fresh = {
        "clip_id": 1,
        "bpm": 143.55,
        "beat_count": 8,
        "beats": [{"time": 0.0, "strength": 1.0, "beat_type": "beat"}],
        "beat_grid": {"status": "plausible", "bpm": 142.0, "anchor_s": 0.02},
        "_stage_status": {"beats": "completed"},
    }
    request = AudioAnalyzeRequest(
        clip_id=1, detect_beats=True, detect_structure=False,
        spectral_analysis=False, detect_key=False,
    )
    merged = _merge_audio_analysis_result(
        cached={}, fresh=fresh, requested=request, planned=request
    )
    assert merged.get("beat_grid"), (
        "der Merge reicht beat_grid nicht durch - genau der Live-Bruch"
    )
    assert merged["beat_grid"]["bpm"] == 142.0


def test_openapi_snapshot_contains_the_field() -> None:
    """Ohne Snapshot-Eintrag erzeugt NSwag keine C#-Property."""
    assert FIELD in SNAPSHOT.read_text(encoding="utf-8"), (
        "openapi.snapshot.json kennt beat_grid nicht - Snapshot nachziehen"
    )


def test_csharp_record_and_transport_mapping() -> None:
    source = API_CLIENT.read_text(encoding="utf-8")
    assert "BeatGrid" in source, "AudioAnalysisResult-Record hat kein BeatGrid"
    assert "ToJsonDictionary(value.Beat_grid)" in source, (
        "FromTransport uebertraegt Beat_grid nicht - das Feld kaeme leer an"
    )


def test_viewmodel_consumes_and_view_binds_it() -> None:
    """Der letzte Schritt: im ViewModel gesetzt UND im XAML gebunden.

    Ein ViewModel-Property ohne Binding ist in diesem Projekt schon zweimal
    unbemerkt geblieben (BrainViewModel, Timeline-StatusText).
    """
    view_model = VIEW_MODEL.read_text(encoding="utf-8")
    assert "ApplyBeatGrid(result.BeatGrid)" in view_model, (
        "das ViewModel liest BeatGrid nicht aus dem Analyseergebnis"
    )
    assert "_beatGridText" in view_model, "keine BeatGridText-Property"

    view = VIEW.read_text(encoding="utf-8")
    assert "{Binding BeatGridText}" in view, (
        "BeatGridText ist an kein XAML-Element gebunden - der Wert waere "
        "gesetzt, aber unsichtbar"
    )
