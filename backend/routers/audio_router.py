"""
Audio Router – Import, Analyse, Beats, Waveform, Stems.

Endpoints:
  POST /audio/import           — Audio-Datei importieren
  POST /audio/analyze          — Audio analysieren (Beats, Struktur, Spektral)
  GET  /audio/beats/{id}       — Beat-Daten abrufen
  GET  /audio/waveform/{id}    — Waveform-Daten abrufen
  POST /audio/stems/separate   — Stem-Separation starten
  GET  /audio/structure/{id}   — Struktur-Segmente abrufen
  GET  /audio/spectral/{id}    — Spektral-Analyse abrufen
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..app_state import AppState, get_app_state
from ..dependencies import with_gpu_task, publish_event, publish_log
from ..schemas.audio_schemas import (
    AudioImportRequest, AudioClipInfo,
    AudioAnalyzeRequest, AudioAnalysisResult,
    BeatData, WaveformData,
    StemSeparateRequest, StemResult,
    StructureSegment, SpectralData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["Audio"])


@router.post(
    "/import",
    response_model=AudioClipInfo,
    summary="Audio-Datei importieren",
    description=(
        "Importiert eine Audio-Datei (MP3, WAV, FLAC, OGG, M4A, AAC) in den Clip-Store. "
        "Ermittelt Dauer via ffprobe und gibt die Clip-Metadaten zurück."
    ),
)
async def import_audio(
    request: AudioImportRequest,
    state: AppState = Depends(get_app_state),
) -> AudioClipInfo:
    """Importiert eine Audio-Datei."""
    audio_path = Path(request.path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {request.path}")

    if audio_path.suffix.lower() not in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}:
        raise HTTPException(status_code=400, detail=f"Nicht unterstütztes Format: {audio_path.suffix}")

    try:
        probe_info = await asyncio.to_thread(_probe_audio_info, str(audio_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio-Info nicht ermittelbar: {e}")

    clip = state.register_audio_clip({
        "name": audio_path.stem,
        "path": str(audio_path.absolute()),
        "duration_seconds": probe_info["duration"],
        "sample_rate": probe_info["sample_rate"],
        "channels": probe_info["channels"],
        "format": audio_path.suffix.lstrip("."),
        "bpm": 0.0,
        "key": None,
        "beat_count": 0,
        "is_analyzed": False,
    })

    logger.info(f"Audio importiert: {audio_path.name} (ID={clip['id']}, {probe_info['duration']:.1f}s)")
    await publish_log(
        f"Audio importiert: {audio_path.name}",
        level="info",
        source="audio.import",
        detail=f"clip_id={clip['id']} duration={probe_info['duration']:.2f}s",
    )
    await publish_event("import_progress", {"clip_id": clip['id'], "percent": 100.0, "message": "Import abgeschlossen"})
    return AudioClipInfo(**clip)


@router.get(
    "/clips",
    response_model=list[AudioClipInfo],
    summary="Audio-Clip-Liste abrufen",
    description=(
        "Gibt alle importierten Audio-Clips zurück. Unterstützt Paginierung via "
        "'page' (1-basiert) und 'limit' (max. 200 Einträge pro Seite)."
    ),
)
async def list_clips(
    page: int = Query(1, ge=1, description="Seitennummer (1-basiert)"),
    limit: int = Query(50, ge=1, le=200, description="Einträge pro Seite"),
    state: AppState = Depends(get_app_state),
) -> list[AudioClipInfo]:
    """Gibt die Audio-Clip-Liste zurück (paginiert)."""
    clips = list(state.get_audio_clips_snapshot().values())
    start = (page - 1) * limit
    end = start + limit

    items: list[AudioClipInfo] = []
    for clip in clips[start:end]:
        analysis = state.get_audio_analysis(clip["id"])
        merged = dict(clip)
        merged["bpm"] = float(analysis.get("bpm", 0.0)) if analysis else float(clip.get("bpm", 0.0) or 0.0)
        merged["key"] = analysis.get("key") if analysis else clip.get("key")
        merged["beat_count"] = int(analysis.get("beat_count", 0)) if analysis else int(clip.get("beat_count", 0) or 0)
        merged["is_analyzed"] = analysis is not None or bool(clip.get("is_analyzed", False))
        items.append(AudioClipInfo(**merged))

    return items


@router.post(
    "/analyze",
    response_model=AudioAnalysisResult,
    summary="Audio-Clip analysieren",
    description=(
        "Analysiert einen importierten Audio-Clip: Beats (BeatNet), Struktur-Segmente, "
        "spektrale Daten. Ergebnis wird gecacht. Kann mehrere Sekunden dauern."
    ),
)
async def analyze_audio(
    request: AudioAnalyzeRequest,
    state: AppState = Depends(get_app_state),
) -> AudioAnalysisResult:
    """Analysiert einen Audio-Clip (Beats, Struktur, Spektral)."""
    clip = state.get_audio_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")

    audio_path = clip["path"]

    logger.info(f"Starte Audio-Analyse für Clip {request.clip_id}: {clip['name']}")
    await publish_log(
        f"Audio-Analyse gestartet: {clip['name']}",
        level="info",
        source="audio.analyze",
        detail=f"clip_id={request.clip_id}",
    )

    try:
        result = await asyncio.to_thread(
            _run_audio_analysis, audio_path, request.clip_id, request
        )
        state.set_audio_analysis(request.clip_id, result)
        clip["bpm"] = float(result.get("bpm", 0.0) or 0.0)
        clip["key"] = result.get("key")
        clip["beat_count"] = int(result.get("beat_count", 0) or 0)
        clip["is_analyzed"] = True
        state.set_audio_clip(request.clip_id, clip)

        # P-1: Analyse-Ergebnisse in SQLite persistieren
        import json as _json
        beats_json = _json.dumps(result.get("beats", []))
        state.update_audio_analysis(
            clip_id=request.clip_id,
            bpm=clip["bpm"],
            key=clip["key"],
            beat_count=clip["beat_count"],
            beats_json=beats_json,
            is_analyzed=True,
        )

        await publish_log(
            f"Audio-Analyse abgeschlossen: {clip['name']}",
            level="info",
            source="audio.analyze",
            detail=f"clip_id={request.clip_id} bpm={float(result.get('bpm', 0.0) or 0.0):.2f} beats={int(result.get('beat_count', 0) or 0)}",
        )
        return AudioAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Audio-Analyse fehlgeschlagen: {e}", exc_info=True)
        await publish_log(
            f"Audio-Analyse fehlgeschlagen: {clip['name']}",
            level="error",
            source="audio.analyze",
            detail=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Analyse fehlgeschlagen: {e}")


@router.get(
    "/beats/{clip_id}",
    response_model=list[BeatData],
    summary="Beat-Daten abrufen",
    description="Gibt die detektierten Beat-Zeitpunkte für einen zuvor analysierten Clip zurück.",
)
async def get_beats(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[BeatData]:
    """Gibt Beat-Daten für einen Clip zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    beats = analysis.get("beats", [])
    return [BeatData(**b) if isinstance(b, dict) else b for b in beats]


@router.get(
    "/waveform/{clip_id}",
    response_model=WaveformData,
    summary="Waveform-Daten abrufen",
    description=(
        "Extrahiert Multi-Band Waveform-Daten für die Visualisierung im WPF Frontend. "
        "Der Parameter 'bands' bestimmt die Anzahl der Frequenzbänder (Standard: 3)."
    ),
)
async def get_waveform(
    clip_id: int,
    bands: int = Query(3, ge=1, le=8, description="Frequenzbänder (1-8)"),
    state: AppState = Depends(get_app_state),
) -> WaveformData:
    """Gibt Waveform-Daten für einen Clip zurück."""
    if clip_id not in state.audio_clips:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} nicht gefunden")

    clip = state.audio_clips[clip_id]
    try:
        waveform = await asyncio.to_thread(_extract_waveform, clip["path"], bands)
        return WaveformData(
            clip_id=clip_id,
            sample_rate=clip["sample_rate"],
            bands=waveform,
            duration_seconds=clip["duration_seconds"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Waveform-Extraktion fehlgeschlagen: {e}")


@router.post(
    "/stems/separate",
    response_model=StemResult,
    summary="Stem-Separation starten",
    description=(
        "Trennt einen Audio-Clip in Stems (Vocals, Instrumental, Drums, Bass, Other) "
        "via Demucs-ONNX auf der AMD DirectML GPU. "
        "Belegt GPU-Lock für die Dauer der Separation (kann mehrere Minuten dauern)."
    ),
)
async def separate_stems(
    request: StemSeparateRequest,
    state: AppState = Depends(get_app_state),
) -> StemResult:
    """Führt Stem-Separation durch (GPU-Lock via Middleware)."""
    if request.clip_id not in state.audio_clips:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")

    clip = state.audio_clips[request.clip_id]
    logger.info(f"Starte Stem-Separation: {clip['name']} mit {request.model.value}")

    try:
        result = await with_gpu_task(
            _run_stem_separation, clip["path"], request.model.value,
            model_id="mdx_net_inst",  # VRAM-Budget-Check via VRAMBudgetManager
        )
        return StemResult(clip_id=request.clip_id, **result)
    except Exception as e:
        logger.error(f"Stem-Separation fehlgeschlagen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stem-Separation fehlgeschlagen: {e}")


@router.get(
    "/structure/{clip_id}",
    response_model=list[StructureSegment],
    summary="Struktur-Segmente abrufen",
    description=(
        "Gibt die detektierten Struktur-Segmente (Intro, Verse, Chorus, Bridge, Outro) "
        "für einen analysierten Clip zurück. Benötigt vorherige Analyse via POST /audio/analyze."
    ),
)
async def get_structure(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[StructureSegment]:
    """Gibt Struktur-Segmente für einen Clip zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    segments = analysis.get("structure_segments", [])
    return [StructureSegment(**s) if isinstance(s, dict) else s for s in segments]


@router.get(
    "/spectral/{clip_id}",
    response_model=SpectralData,
    summary="Spektral-Analyse abrufen",
    description=(
        "Gibt die spektralen Analysedaten (Frequenzspektrum, Energie pro Band) "
        "für einen analysierten Clip zurück."
    ),
)
async def get_spectral(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> SpectralData:
    """Gibt Spektral-Analyse Daten zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    spectral = analysis.get("spectral_data", {}) or {}
    if spectral.get("clip_id") != clip_id:
        spectral = {**spectral, "clip_id": clip_id}
    return SpectralData(**spectral)


# --- Private Hilfsfunktionen (blockierend, werden via to_thread aufgerufen) ---

def _probe_audio_info(path: str) -> dict[str, Any]:
    """Ermittelt Audio-Dauer, Sample-Rate und Channels via ffprobe."""
    import json
    import subprocess
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=sample_rate,channels",
        "-select_streams", "a:0",
        "-of", "json", path,
    ]
    res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
    data = json.loads(res)

    duration = float(data.get("format", {}).get("duration", 0.0))

    # Sample-Rate und Channels aus dem ersten Audio-Stream
    sample_rate = 44100  # Fallback
    channels = 2         # Fallback
    streams = data.get("streams", [])
    if streams:
        stream = streams[0]
        try:
            sample_rate = int(stream.get("sample_rate", 44100))
        except (ValueError, TypeError):
            pass
        try:
            channels = int(stream.get("channels", 2))
        except (ValueError, TypeError):
            pass

    return {"duration": duration, "sample_rate": sample_rate, "channels": channels}


def _run_audio_analysis(audio_path: str, clip_id: int, request: AudioAnalyzeRequest) -> dict[str, Any]:
    """Führt die vollständige Audio-Analyse durch (blockierend)."""
    import librosa
    import numpy as np

    # Audio einmalig laden — wird von StructureAnalyzer und KeyDetector benötigt
    try:
        y, sr = librosa.load(audio_path, sr=22050, mono=True)
    except Exception as e:
        logger.error(f"Audio-Load fehlgeschlagen: {audio_path}: {e}")
        return {
            "clip_id": clip_id, "duration_seconds": 0.0, "bpm": 0.0,
            "beat_count": 0, "beats": [], "key": None,
            "energy_curve": [], "structure_segments": [], "spectral_data": None,
        }

    duration = float(len(y)) / sr if sr > 0 else 0.0

    # 1. BeatNet Beat-Detection
    beats: list[dict] = []
    bpm: float = 0.0
    energy_curve: list[float] = []

    if request.detect_beats:
        try:
            from pb_studio.audio.beat_detector import BeatDetector
            detector = BeatDetector()
            # detect_beats gibt list[float] zurück — BeatNet oder Librosa-Fallback
            beat_times = detector.detect_beats(audio_path)
            if beat_times:
                arr = np.asarray(beat_times, dtype=np.float64)
                for t in arr:
                    beats.append({
                        "time": float(t),
                        "strength": 1.0,
                        "beat_type": "beat",
                    })
                if len(arr) > 1:
                    intervals = np.diff(arr)
                    avg_interval = float(np.median(intervals))
                    bpm = 60.0 / avg_interval if avg_interval > 0 else 0.0

            # Energy-Curve via librosa (unabhängig von BeatNet-Verfügbarkeit)
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
            rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
            energy_curve = (rms / rms_max).tolist() if rms_max > 0 else rms.tolist()
        except Exception as e:
            logger.warning(f"Beat-Analyse fehlgeschlagen: {e}")

    # 2. Struktur-Analyse (Novelty + Clustering)
    structure_segments: list = []
    if request.detect_structure:
        try:
            from pb_studio.audio.structure_analyzer import StructureAnalyzer
            struct_result = StructureAnalyzer().analyze_song_structure(y, sr)
            structure_segments = struct_result.get("segments", [])
        except Exception as e:
            logger.warning(f"Struktur-Analyse fehlgeschlagen: {e}")

    # 3. Spektral-Analyse (8-Band STFT) — nutzt bereits geladenes y/sr (kein erneuter Disk-Zugriff)
    spectral_data = None
    if request.spectral_analysis:
        try:
            from pb_studio.audio.spectral_analyzer import SpectralAnalyzer
            spec_result = SpectralAnalyzer(sr=sr).analyze_from_array(y, sr)
            spectral_data = {
                "clip_id": clip_id,
                "bands": spec_result.get("band_energies", {}),
                "frequency_ranges": {},
            }
        except Exception as e:
            logger.warning(f"Spektral-Analyse fehlgeschlagen: {e}")

    # 4. Tonart-Erkennung (Krumhansl-Kessler, immer aktiv)
    key = None
    try:
        from pb_studio.audio.key_detector import KeyDetector
        key = KeyDetector().detect_key(y, sr)
    except Exception as e:
        logger.warning(f"Key-Detection fehlgeschlagen: {e}")

    return {
        "clip_id": clip_id,
        "duration_seconds": duration,
        "bpm": bpm,
        "beat_count": len(beats),
        "beats": beats,
        "key": key,
        "energy_curve": energy_curve,
        "structure_segments": structure_segments,
        "spectral_data": spectral_data,
    }


def _extract_waveform(audio_path: str, bands: int) -> list[list[float]]:
    """Extrahiert N-Band Waveform-Daten, blockierend.

    bands=1: nur 'mid', bands=2: 'low'+'high', bands=3: 'low'+'mid'+'high'
    bands>=4: alle 3 Bänder (max verfügbar)
    """
    try:
        from pb_studio.audio.waveform_analyzer import WaveformAnalyzer
        result = WaveformAnalyzer().get_downsampled_waveform(
            audio_path, target_points=1000
        )
        # result: dict mit 'low', 'mid', 'high' als numpy arrays
        all_keys = ["low", "mid", "high"]
        if bands <= 1:
            band_keys = ["mid"]
        elif bands == 2:
            band_keys = ["low", "high"]
        else:
            band_keys = all_keys
        output = []
        for k in band_keys:
            arr = result.get(k)
            if arr is not None:
                output.append([float(v) for v in arr])
        return output
    except ImportError:
        logger.warning("WaveformAnalyzer nicht verfügbar, leere Daten")
        return []
    except Exception as e:
        logger.warning(f"Waveform-Extraktion fehlgeschlagen: {e}")
        return []


def _run_stem_separation(audio_path: str, model_name: str) -> dict[str, Any]:
    """Führt Stem-Separation durch (blockierend, GPU)."""
    from pb_studio.audio.separator import StemSeparator

    separator = StemSeparator()
    result = separator.separate(audio_path, model_name=model_name)

    # Fehler vom Separator prüfen
    if "error" in result:
        raise RuntimeError(f"Stem-Separation fehlgeschlagen: {result['error']}")

    # StemSeparator.separate() kann relative Dateinamen zurückgeben.
    # Diese auf den konfigurierten Output-/Temp-Ordner normalisieren.
    output_dir_raw = separator.config.get("paths", {}).get("temp_dir", "./temp")
    output_dir = separator.config.resolve_path(output_dir_raw)

    # StemSeparator.separate() gibt {"stems": [path1, path2, ...]} zurück.
    # audio-separator benennt Output-Dateien mit (Vocals), (Instrumental), etc.
    stem_files = result.get("stems", [])
    normalized_stem_files: list[str] = []
    for fpath in stem_files:
        p = Path(fpath)
        resolved = p.resolve() if p.is_absolute() else (output_dir / p).resolve()
        normalized_stem_files.append(str(resolved))

    mapped: dict[str, str | None] = {
        "vocals_path": None,
        "instrumental_path": None,
        "drums_path": None,
        "bass_path": None,
        "other_path": None,
        "model_used": model_name,
    }

    for fpath in normalized_stem_files:
        name_lower = Path(fpath).stem.lower()
        if "vocal" in name_lower:
            mapped["vocals_path"] = fpath
        elif "instrumental" in name_lower or "no_vocals" in name_lower or "instrum" in name_lower:
            mapped["instrumental_path"] = fpath
        elif "drum" in name_lower:
            mapped["drums_path"] = fpath
        elif "bass" in name_lower:
            mapped["bass_path"] = fpath
        elif "other" in name_lower:
            mapped["other_path"] = fpath
        else:
            # Unbekannter Stem — als "other" zuweisen falls noch frei
            if mapped["other_path"] is None:
                mapped["other_path"] = fpath

    logger.info(f"Stem-Mapping: {len(normalized_stem_files)} Dateien → {sum(1 for v in mapped.values() if v and v != model_name)} Stems")
    return mapped
