"""Regressionstest fuer die zlib-Kompression von ai_data-Feldern.

Audit 2026-08-29, Befund C-02: `_decomp` in `AppState.load_from_db` gab fuer
jeden Wert, der weder Liste noch String war, `[]` zurueck. Zwei Folgen:

1. `spectral_data` liegt in bestehenden DB-Zeilen unkomprimiert als **dict**
   (verifiziert: alle 5 Zeilen in data/pb_studio.db, type=dict, len=8).
   Der Legacy-Pfad lieferte dafuer `[]` -> stiller Datenverlust bei jedem Reload.
2. Ein fehlendes `spectral_data` (None) wurde zu `[]`. `AudioAnalysisResult`
   deklariert `Optional[SpectralData]`; `[]` bricht die Pydantic-Validierung,
   der Fehler landet im generischen except von `/audio/analyze` -> HTTP 500.

Diese Tests pruefen den echten Produktionspfad (`load_from_db`), nicht eine
Kopie der Hilfsfunktion.
"""

import base64
import json
import zlib

import pytest

from backend.app_state import AppState


SPECTRAL_DICT = {
    "times": [0.0, 0.5, 1.0],
    "band_energies": {"low": [0.1, 0.2, 0.3], "mid": [0.4], "high": [0.5]},
    "centroids": [800.0, 900.0, 1000.0],
    "band_means": [0.2, 0.4, 0.5],
    "band_variances": [0.01, 0.02, 0.03],
    "events": [],
    "clip_id": 7,
    "frequency_ranges": {"low": [20, 250]},
}


def _compress(payload):
    """Spiegelt `_comp` aus AppState.update_audio_analysis."""
    return base64.b64encode(
        zlib.compress(json.dumps(payload).encode("utf-8"))
    ).decode("ascii")


def _install_fake_repo(monkeypatch, ai_data, audio_path):
    rows = [
        {
            "id": 101,
            "file_path": str(audio_path),
            "duration_sec": 12.0,
            "metadata_json": json.dumps(
                {"clip_type": "audio", "clip_id": 7, "name": "regression"}
            ),
            "ai_data_json": json.dumps(ai_data),
        }
    ]

    class FakeRepo:
        def get_by_project(self, project_id):
            return rows

        def delete_media(self, media_id):
            raise AssertionError("delete_media darf hier nicht aufgerufen werden")

    monkeypatch.setattr(
        "pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo
    )


def _load(monkeypatch, tmp_path, ai_data):
    audio = tmp_path / "regression.wav"
    audio.write_bytes(b"RIFF")
    _install_fake_repo(monkeypatch, ai_data, audio)
    state = AppState()
    assert state.load_from_db() is True
    return state.get_audio_analysis(7)


class TestAiDataDecompression:
    def test_legacy_unkomprimiertes_spectral_dict_ueberlebt_den_reload(
        self, tmp_path, monkeypatch
    ):
        """C-02, Wirkung 1: dict darf nicht zu [] werden.

        Ohne den Fix: `_decomp` faellt fuer dict auf `return []` durch und die
        Spektraldaten sind nach jedem Backend-Neustart weg.
        """
        analysis = _load(
            monkeypatch,
            tmp_path,
            {"is_analyzed": True, "bpm": 128.0, "spectral_data": SPECTRAL_DICT},
        )

        assert isinstance(analysis["spectral_data"], dict), (
            "Legacy-dict wurde zu %r degradiert — Datenverlust"
            % (analysis["spectral_data"],)
        )
        assert analysis["spectral_data"] == SPECTRAL_DICT

    def test_fehlendes_spectral_data_bleibt_none(self, tmp_path, monkeypatch):
        """C-02, Wirkung 2: None darf nicht zu [] werden.

        `AudioAnalysisResult.spectral_data` ist `Optional[SpectralData]`.
        `None` ist gueltig, `[]` nicht — daraus wurde HTTP 500.
        """
        analysis = _load(
            monkeypatch, tmp_path, {"is_analyzed": True, "bpm": 128.0}
        )

        assert analysis["spectral_data"] is None, (
            "fehlendes spectral_data wurde zu %r — bricht Optional[SpectralData]"
            % (analysis["spectral_data"],)
        )

    def test_komprimiertes_spectral_dict_wird_entpackt(self, tmp_path, monkeypatch):
        """Der neue Schreibpfad muss weiterhin funktionieren (keine Regression)."""
        analysis = _load(
            monkeypatch,
            tmp_path,
            {
                "is_analyzed": True,
                "bpm": 128.0,
                "spectral_data": _compress(SPECTRAL_DICT),
            },
        )

        assert analysis["spectral_data"] == SPECTRAL_DICT

    def test_energy_curve_bleibt_eine_liste(self, tmp_path, monkeypatch):
        """Listenfelder behalten ihren Typ — komprimiert wie unkomprimiert.

        Wichtig, weil `models/audio.py:94` ueber `energy_curve` iteriert, ohne
        vorher auf None zu pruefen.
        """
        curve = [0.1, 0.5, 0.9, 0.4]

        komprimiert = _load(
            monkeypatch,
            tmp_path,
            {"is_analyzed": True, "energy_curve": _compress(curve)},
        )
        assert komprimiert["energy_curve"] == curve

        unkomprimiert = _load(
            monkeypatch,
            tmp_path,
            {"is_analyzed": True, "energy_curve": curve},
        )
        assert unkomprimiert["energy_curve"] == curve

    def test_fehlende_listenfelder_bleiben_listen(self, tmp_path, monkeypatch):
        """Ein fehlendes Listenfeld liefert [], nicht None."""
        analysis = _load(monkeypatch, tmp_path, {"is_analyzed": True})

        assert analysis["energy_curve"] == []
        assert analysis["tempo_curve"] == []

    def test_korrupter_blob_wird_verworfen_statt_zu_taeuschen(
        self, tmp_path, monkeypatch, caplog
    ):
        """Ein unlesbarer Wert darf nicht als leeres Ergebnis durchgehen.

        Die Vorgaengerfassung verschluckte den Fehler doppelt und lieferte `[]`
        — ununterscheidbar von 'Analyse lief, fand nichts'. Erwartet wird ein
        leerer Wert PLUS eine Logzeile.
        """
        with caplog.at_level("WARNING"):
            analysis = _load(
                monkeypatch,
                tmp_path,
                {"is_analyzed": True, "spectral_data": "kein-gueltiges-base64-!!"},
            )

        assert not analysis["spectral_data"]
        assert any(
            "dekomprimiert" in r.message.lower() or "ai_data" in r.message.lower()
            for r in caplog.records
        ), "korrupter ai_data-Blob wurde still verworfen, ohne Logzeile"
