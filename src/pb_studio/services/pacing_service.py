"""
Pacing Service für PB_studio AMD

Orchestriert die Cut-List-Generierung aus Audio, Clips und Pacing-Config.
Kein ffmpeg-python — nutzt subprocess für Clip-Dauer.
Kein RLStyleModel (AMD Version hat keins).
"""

import json
import logging
import random
import subprocess
import re
from pathlib import Path
from typing import Any, List, Dict, Callable, Optional
import numpy as np

from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import CutListEntry

logger = logging.getLogger(__name__)


# =============================================================================
# THEMATISCHE ÜBERGANGSMATRIX & KAPITEL-SCHLEIFE (Stufe 3)
# =============================================================================

TRANSITION_COMPATIBILITY: Dict[str, List[str]] = {
    "gothic_demonic": ["gothic_demonic", "mystic_nature"],
    "neon_cyber_rave": ["neon_cyber_rave", "ethereal_water"],
    "mystic_nature": ["mystic_nature", "gothic_demonic", "ethereal_water"],
    "ethereal_water": ["ethereal_water", "mystic_nature", "neon_cyber_rave"]
}

def select_theme_for_chapter(energy: float, prev_theme: Optional[str]) -> str:
    """Bestimmt das beste Thema basierend auf der Energie und dem vorherigen Thema."""
    if energy > 0.58:
        candidates = ["gothic_demonic", "neon_cyber_rave"]
    else:
        candidates = ["mystic_nature", "ethereal_water"]

    if not prev_theme:
        return random.choice(candidates)

    # Übergänge filtern
    compat = TRANSITION_COMPATIBILITY.get(prev_theme, [])
    valid_candidates = [c for c in candidates if c in compat]
    if valid_candidates:
        return random.choice(valid_candidates)
        
    # Fallback
    return prev_theme


def _uses_advanced_pacing(pacing_config: dict, semantic_enabled: bool) -> bool:
    return bool(
        pacing_config.get("use_motion_matching", False)
        or semantic_enabled
        or pacing_config.get("use_structure_awareness", False)
        or pacing_config.get("use_brain", False)
    )


class PacingService:
    """Service-Layer für Cut-List-Generierung."""

    def __init__(self):
        # R18/HIGH-018-2: Cache ffprobe results — avoids 2 subprocess calls per cut
        # for the same file (once inside _get_random_clip_start, once for out-point check).
        self._duration_cache: Dict[str, float] = {}
        # Audit A2: Test-Hint — wurde cached energy_curve in den Engine injiziert?
        self._last_used_cached_energy: bool = False
        # Audit A3: Test-Hint — wurde cached structure_segments in den Engine injiziert
        # (statt redundanter librosa-Re-Analyse via analyze_song_structure)?
        self._last_skipped_structure_reanalyze: bool = False
        # Audit E2: Test-Hint — wurde cached spectral_data["bands"]["low"] (bass_curve)
        # in den Engine injiziert (fuer drop-section trigger weighting)?
        self._last_used_cached_bass: bool = False
        # Audit E3: Test-Hint — wurde cached subtrack_segments in den Engine injiziert
        # (fuer subtrack-aware cut generation / boundary-anchors)?
        self._last_used_cached_subtracks: bool = False
        # Audit L-M1: Test-Hint — wurde cached tempo_curve (SubtrackDetector
        # DJ-Tempo-Variation) in den Engine injiziert (fuer varying-BPM mixes)?
        self._last_used_cached_tempo: bool = False

    def _resolve_semantic_audio(
        self,
        audio_path: str,
        requested: bool,
    ) -> tuple[bool, Optional[str]]:
        """Resolve Semantic Audio once and fail closed when CLAP is unavailable."""
        if not requested:
            return False, None

        try:
            from pb_studio.ai.smart_director import SmartDirector

            director = SmartDirector.get_instance()
            prompt = director.get_dominant_mood(audio_path)
            return True, prompt
        except Exception as exc:
            logger.warning(
                "Semantic Audio unavailable; semantic matching disabled: %s",
                exc,
            )
            return False, None

    def _get_clip_duration(self, clip_path: str) -> float:
        """Ermittelt Clip-Dauer via ffprobe (kein ffmpeg-python). Cached per Pfad."""
        key = str(clip_path)
        if key in self._duration_cache:
            return self._duration_cache[key]
        from pb_studio.video.encoder_utils import _get_ffprobe_path
        cmd = [
            _get_ffprobe_path(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(clip_path)
        ]
        try:
            res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            dur = float(json.loads(res)["format"]["duration"])
            self._duration_cache[key] = dur
            return dur
        except Exception as e:
            logger.error(f"Clip-Dauer nicht ermittelbar: {clip_path}: {e}")
            raise ValueError(f"Konnte Dauer nicht lesen: {Path(clip_path).name}") from e

    def _get_random_clip_start(self, clip_path: str, required_duration: float) -> float:
        """Berechnet zufällige Start-Position im Clip."""
        clip_dur = self._get_clip_duration(clip_path)
        max_start = max(0.0, clip_dur - required_duration)
        if max_start <= 0.0:
            return 0.0
        return random.uniform(0.0, max_start)

    def _process_pacing_cuts_to_cutlist(
        self, cut_with_clips: list, target_duration: float
    ) -> List[CutListEntry]:
        """Konvertiert Pacing-Cuts zu CutListEntry-Liste."""
        cut_list = []
        for i in range(len(cut_with_clips) - 1):
            current_cut, clip_path, clip_id = cut_with_clips[i]
            next_cut, _, _ = cut_with_clips[i + 1]

            if target_duration is not None and current_cut.time >= target_duration:
                break

            duration = next_cut.time - current_cut.time
            if duration < 0.5:
                continue
            if not clip_path:
                continue

            file_path = str(Path(clip_path).absolute())
            clip_start = self._get_random_clip_start(file_path, duration)

            # Prüfe ob out_point die tatsächliche Clip-Dauer überschreitet
            actual_clip_dur = self._get_clip_duration(file_path)
            if actual_clip_dur > 0 and (clip_start + duration) > actual_clip_dur:
                # Clip zu kurz: von vorne, Dauer auf verfügbare Länge kappen
                clip_start = 0.0
                duration = min(duration, actual_clip_dur)

            metadata = {
                "file_path": file_path,
                "clip_name": Path(clip_path).stem,
                "clip_start": clip_start,
                "trigger_type": current_cut.trigger_type,
                "trigger_strength": current_cut.strength,
            }
            if hasattr(current_cut, "segment_type") and current_cut.segment_type:
                metadata["segment_type"] = current_cut.segment_type
            if getattr(current_cut, "provenance", None):
                metadata["trigger_provenance"] = dict(current_cut.provenance)

            normalized_clip_id = str(clip_id)
            if not normalized_clip_id.startswith("clip_"):
                normalized_clip_id = f"clip_{normalized_clip_id}"

            cut = CutListEntry(
                clip_id=normalized_clip_id,
                start_time=current_cut.time,
                end_time=current_cut.time + duration,
                metadata=metadata,
            )
            cut_list.append(cut)
        return cut_list

    def _stretch_last_cut_to_audio(
        self, cut_list: list, audio_duration: float
    ) -> list:
        """Stretches the last cut so cut_list[-1].end_time == audio_duration.

        Why: validate_timeline already blocks overflow (>audio_duration). Underflow
        (timeline ends before audio) was silent — user heard music keep playing
        after last visible frame. Premiere/Davinci force V1.length == A1.length.

        No-op on empty list, on audio_duration <= 0, or if last cut already
        reaches audio_duration.
        """
        if not cut_list or audio_duration <= 0.0:
            return cut_list
        last = cut_list[-1]
        if last.end_time >= audio_duration - 0.001:
            return cut_list

        # Mutate end_time in-place (CutListEntry is a dataclass-like model).
        last.end_time = audio_duration
        return cut_list

    def _finalize_cut_list(self, cut_list: list, target_duration: float) -> list:
        """Single exit-point post-processing for all auto-pacing return paths.
        Future cut-list invariants (e.g. min-gap normalization, last-cut stretch)
        belong here, not at each return site.

        BUGFIX H1: target_duration MUST be the same budget the cuts were generated
        against (duration_limit or total_duration), NOT the full song length.
        Passing total_duration here stretched the last cut of a duration_limit'd
        (preview/short) render across the entire song -> giant runaway final clip.
        """
        if not cut_list or target_duration <= 0.0:
            return cut_list

        cut_list[:] = [
            cut for cut in cut_list
            if float(cut.start_time) < target_duration
        ]
        if not cut_list:
            return cut_list

        first = cut_list[0]
        original_start = float(first.start_time)
        if abs(original_start) > 0.001:
            metadata = first.metadata if isinstance(first.metadata, dict) else {}
            first.metadata = metadata
            clip_start = float(metadata.get("clip_start", 0.0) or 0.0)
            if original_start > 0.0:
                metadata["clip_start"] = max(0.0, clip_start - original_start)
            else:
                metadata["clip_start"] = clip_start + abs(original_start)
            metadata["boundary_original_start"] = original_start
            metadata["boundary_normalized_start"] = 0.0
            first.start_time = 0.0

        last = cut_list[-1]
        original_end = float(last.end_time)
        last.end_time = target_duration
        if isinstance(last.metadata, dict) and abs(original_end - target_duration) > 0.001:
            last.metadata["boundary_original_end"] = original_end
            last.metadata["boundary_normalized_end"] = target_duration

        return cut_list

    def _inject_cached_into_engine(
        self,
        pacing_engine: AdvancedPacingEngine,
        audio_path: str,
        cached_analysis: Dict | None,
    ) -> None:
        """L-K5: Extracted pre-cached injection logic so both generate_cut_list and
        generate_cut_list_with_stems wrappers can re-use it.

        Injects pre_cached_beats, _pre_cached_bpm, _pre_cached_duration,
        _pre_cached_energy, _pre_cached_bass_curve, _pre_cached_subtracks,
        _pre_cached_tempo_curve (mirrors what generate_cut_list does in-line).
        """
        if not cached_analysis:
            self._last_used_cached_energy = False
            self._last_used_cached_bass = False
            self._last_used_cached_subtracks = False
            self._last_used_cached_tempo = False
            return

        # Beats + BPM + Duration (+ Audit L-N8: per-beat strength)
        pre_cached_beats: List[float] = []
        pre_cached_beat_strengths: List[float] = []
        pre_cached_downbeats: List[float] = []
        downbeat_provenance = cached_analysis.get("downbeat_provenance") or {
            "status": "unavailable",
            "method": "cache_field_missing",
            "synthetic": False,
            "measured_count": 0,
        }
        if not isinstance(downbeat_provenance, dict):
            downbeat_provenance = {
                "status": "unavailable",
                "method": "invalid_cache_field",
                "synthetic": False,
                "measured_count": 0,
            }
        has_real_strengths = False
        for b in cached_analysis.get("beats", []):
            if isinstance(b, dict):
                beat_time = float(b.get("time", 0.0))
                pre_cached_beats.append(beat_time)
                if (
                    downbeat_provenance.get("status") == "measured"
                    and str(b.get("beat_type") or "").lower()
                    in {"downbeat", "bar"}
                ):
                    pre_cached_downbeats.append(beat_time)
                # L-N8: preserve per-beat strength. Engine uses it as
                # trigger-weight multiplier instead of the previous
                # hardcoded 1.0.
                s = b.get("strength")
                if s is None:
                    pre_cached_beat_strengths.append(1.0)
                else:
                    pre_cached_beat_strengths.append(float(s))
                    has_real_strengths = True
            else:
                pre_cached_beats.append(float(b))
                pre_cached_beat_strengths.append(1.0)
        pre_cached_bpm = cached_analysis.get("bpm") or None
        if pre_cached_beats:
            pacing_engine._pre_cached_beats = pre_cached_beats
            measured_downbeats = cached_analysis.get("downbeats") or []
            if downbeat_provenance.get("status") == "measured":
                pre_cached_downbeats.extend(
                    float(value) for value in measured_downbeats
                )
                pre_cached_downbeats = sorted(set(pre_cached_downbeats))
            if pre_cached_downbeats:
                pacing_engine._pre_cached_downbeats = pre_cached_downbeats
            pacing_engine._pre_cached_downbeat_provenance = downbeat_provenance
            if has_real_strengths:
                pacing_engine._pre_cached_beat_strengths = pre_cached_beat_strengths
            if pre_cached_bpm:
                pacing_engine._pre_cached_bpm = pre_cached_bpm
            cached_dur = float(cached_analysis.get("duration_seconds", 0.0) or 0.0)
            if cached_dur > 0:
                pacing_engine._pre_cached_duration = cached_dur

        # Energy
        cached_energy = cached_analysis.get("energy_curve")
        if cached_energy:
            import numpy as _np
            pacing_engine._pre_cached_energy = _np.array(cached_energy, dtype=_np.float32)
            self._last_used_cached_energy = True
        else:
            self._last_used_cached_energy = False

        # Bass-curve from spectral_data.bands.low
        spectral = cached_analysis.get("spectral_data")
        if spectral and isinstance(spectral, dict):
            bands = spectral.get("bands", {})
            low_band = bands.get("low") if isinstance(bands, dict) else None
            if low_band and len(low_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_bass_curve = _np.array(low_band, dtype=_np.float32)
                if not hasattr(pacing_engine, "_pre_cached_duration") or \
                        getattr(pacing_engine, "_pre_cached_duration", 0.0) <= 0:
                    cached_dur = float(cached_analysis.get("duration_seconds", 0.0) or 0.0)
                    if cached_dur > 0:
                        pacing_engine._pre_cached_duration = cached_dur
                self._last_used_cached_bass = True
            else:
                self._last_used_cached_bass = False

            # L-M2: mid + high curves analog bass.
            # spectral_data.bands.mid + .high werden vom SpectralAnalyzer 3-Band
            # Output gleich neben .low persistiert. Engine nutzt sie via
            # _mid_weight_at_time() / _high_weight_at_time() — heute kein
            # automatischer Apply-Punkt im Strength-Adjust, aber Helper-API ready.
            mid_band = bands.get("mid") if isinstance(bands, dict) else None
            if mid_band and len(mid_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_mid_curve = _np.array(
                    mid_band, dtype=_np.float32
                )
            high_band = bands.get("high") if isinstance(bands, dict) else None
            if high_band and len(high_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_high_curve = _np.array(
                    high_band, dtype=_np.float32
                )
        else:
            self._last_used_cached_bass = False

        # Subtracks
        subtracks = cached_analysis.get("subtrack_segments")
        if subtracks and isinstance(subtracks, list) and len(subtracks) > 0:
            pacing_engine._pre_cached_subtracks = subtracks
            self._last_used_cached_subtracks = True
        else:
            self._last_used_cached_subtracks = False

        # L-M1: tempo_curve injection (SubtrackDetector DJ-Tempo-Variation)
        # Hilft bei Mixen mit varying BPM — Engine kann _tempo_at_time(t) abfragen.
        tempo_curve = cached_analysis.get("tempo_curve")
        if tempo_curve and len(tempo_curve) > 0:
            import numpy as _np
            pacing_engine._pre_cached_tempo_curve = _np.array(
                tempo_curve, dtype=_np.float32
            )
            # Duration sicherstellen (fuer time->index mapping in _tempo_at_time)
            if not hasattr(pacing_engine, "_pre_cached_duration") or \
                    getattr(pacing_engine, "_pre_cached_duration", 0.0) <= 0:
                cached_dur = float(
                    cached_analysis.get("duration_seconds", 0.0) or 0.0
                )
                if cached_dur > 0:
                    pacing_engine._pre_cached_duration = cached_dur
            self._last_used_cached_tempo = True
        else:
            self._last_used_cached_tempo = False

        # Audit-Fix 2026-07-10 (Sweep-Finding HIGH-1): Onset/Kick/Snare/HiHat-
        # Trigger-Kandidaten mit-injizieren. Ersetzt den toten
        # `core.session_manager`-Import in AdvancedPacingEngine — vorher blieben
        # diese Trigger im normalen (pre-cached) Pacing-Pfad komplett wirkungslos.
        for _field, _attr in (
            ("onset_times", "_pre_cached_onset_times"),
            ("kick_times", "_pre_cached_kick_times"),
            ("snare_times", "_pre_cached_snare_times"),
            ("hihat_times", "_pre_cached_hihat_times"),
        ):
            _values = cached_analysis.get(_field)
            if _values:
                setattr(pacing_engine, _attr, list(_values))

        # Stufe 2 Audio-Heuristik: Kurven an Selector spiegeln
        cs = pacing_engine.clip_selector
        if hasattr(pacing_engine, "_pre_cached_bass_curve"):
            cs.bass_curve = pacing_engine._pre_cached_bass_curve
        if hasattr(pacing_engine, "_pre_cached_energy"):
            cs.energy_curve = pacing_engine._pre_cached_energy
        if hasattr(pacing_engine, "_pre_cached_duration"):
            cs.duration_seconds = pacing_engine._pre_cached_duration

    def _configure_brain_selector(
        self,
        pacing_engine: AdvancedPacingEngine,
        pacing_config: dict,
        cached_analysis: Dict | None,
        clips: list,
        total_duration: float,
        song_mood: Optional[str],
    ) -> None:
        """Bind Brain reranker and forward real analysis features to ClipSelector."""
        if not pacing_config.get("use_brain", False):
            return

        try:
            from pb_studio.brain.brain_service import BrainService
            from pb_studio.brain.feature_adapter import CanonicalFeatureAdapter

            selector = pacing_engine.clip_selector
            selector.brain_reranker = BrainService.get().reranker
            selector.brain_context_keys = [""]
            selector.brain_min_confidence = float(
                pacing_config.get("brain_min_confidence", 0.0)
            )

            analysis = cached_analysis or {}
            mood_tags = list(analysis.get("mood_tags") or [])
            if not mood_tags and song_mood:
                mood_tags = [str(song_mood)]

            video_features = {
                str(clip.get("id")): dict(clip)
                for clip in clips
                if clip.get("id") is not None
            }
            adapter = CanonicalFeatureAdapter(
                audio_analysis=analysis,
                video_analysis_by_clip=video_features,
                fallback_duration=total_duration,
                fallback_mood_tags=mood_tags,
            )
            selector.brain_feature_adapter = adapter
            selector.brain_audio_features = {
                "energy_curve": list(adapter.energy_curve),
                "centroid_curve": list(adapter.centroid_curve),
                "duration_seconds": adapter.duration_seconds,
                "mood_tags": list(adapter.audio_mood_tags),
                "audio_embedding": analysis.get("audio_embedding"),
                "confidence": adapter.audio_confidence,
            }
            selector.brain_video_features_by_clip = video_features
            logger.info(
                "Brain reranker bound: audio_features=%s video_features=%d threshold=%.3f",
                bool(selector.brain_audio_features["energy_curve"]),
                len(selector.brain_video_features_by_clip),
                selector.brain_min_confidence,
            )
        except Exception as exc:
            logger.warning("Brain deep-hook bind fehlgeschlagen: %s", exc)

    def segment_timeline_into_chapters(
        self,
        energy_curve: Optional[np.ndarray],
        beats: List[float],
        bpm: float,
        duration: float,
    ) -> List[dict]:
        """Teilt die Timeline in narrative Abschnitte (Kapitel) von ca. 8-16 Takten (Bars) ein."""
        if not beats or len(beats) < 4:
            # Fallback: ein einziges Kapitel für die gesamte Länge
            return [{"start": 0.0, "end": duration, "theme": "mystic_nature"}]

        # Berechne Sekunden pro Bar (4 Beats)
        bpm_val = bpm or 120.0
        secs_per_beat = 60.0 / bpm_val
        secs_per_bar = secs_per_beat * 4.0
        
        # Kapitelgröße soll z.B. ca. 8 oder 16 Bars betragen (ca. 15-30 Sekunden)
        # Wir segmentieren basierend auf Beats, z.B. alle 32 oder 64 Beats.
        beats_per_chapter = 32 # 8 Bars
        
        chapters = []
        num_beats = len(beats)
        prev_theme = None
        
        # Finde durchschnittliche Energie für jedes Kapitel
        energy_data = energy_curve if energy_curve is not None and len(energy_curve) > 0 else None
        
        for i in range(0, num_beats, beats_per_chapter):
            start_beat_idx = i
            end_beat_idx = min(i + beats_per_chapter, num_beats - 1)
            
            start_time = beats[start_beat_idx]
            # Für das letzte Kapitel dehnen wir das Ende bis zur vollen Dauer aus
            if end_beat_idx == num_beats - 1 or (i + beats_per_chapter) >= num_beats:
                end_time = duration
            else:
                end_time = beats[end_beat_idx]
                
            if end_time - start_time < 2.0:
                # Zu kurzes Restkapitel, hänge an letztes an
                if chapters:
                    chapters[-1]["end"] = duration
                    break
            
            # Schätze Energie für dieses Zeitintervall
            avg_energy = 0.5
            if energy_data is not None:
                curve_len = len(energy_data)
                start_idx = int((start_time / duration) * curve_len) if duration > 0 else 0
                end_idx = int((end_time / duration) * curve_len) if duration > 0 else curve_len
                start_idx = max(0, min(curve_len - 1, start_idx))
                end_idx = max(start_idx + 1, min(curve_len, end_idx))
                avg_energy = float(np.mean(energy_data[start_idx:end_idx]))
                
            theme = select_theme_for_chapter(avg_energy, prev_theme)
            chapters.append({
                "start": start_time,
                "end": end_time,
                "theme": theme
            })
            prev_theme = theme
            
        if not chapters:
            chapters.append({"start": 0.0, "end": duration, "theme": "mystic_nature"})
            
        # Stelle sicher, dass das erste Kapitel bei 0.0 startet
        chapters[0]["start"] = 0.0
        # Und das letzte Kapitel bei duration endet
        chapters[-1]["end"] = duration
        
        return chapters

    def load_canvas_manual_anchors(self, canvas_path: str | None, clips: List[dict]) -> List[dict]:
        """Storyboard-Anker und manuelle Clips aus Obsidian .canvas File einlesen (Stufe 4)."""
        if not canvas_path:
            return []
        p = Path(canvas_path)
        if not p.exists():
            logger.info(f"Storyboard-Canvas nicht gefunden unter {canvas_path} — fahre automatisch fort.")
            return []
            
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Fehler beim Laden des Storyboards: {e}")
            return []
            
        nodes = data.get("nodes", [])
        
        # 1. Parse Zeitanker
        anchors = []
        for n in nodes:
            if n.get("type") == "text":
                text = n.get("text", "")
                m = re.search(r"@(\d{1,2}):(\d{2})", text)
                if m:
                    minutes = int(m.group(1))
                    seconds = int(m.group(2))
                    anchors.append({
                        "x": float(n.get("x", 0)),
                        "seconds": minutes * 60 + seconds
                    })
                    
        if len(anchors) < 2:
            logger.info("Canvas hat weniger als 2 Zeitanker — Überspringe Storyboard-Mapping.")
            return []
            
        anchors.sort(key=lambda a: a["x"])
        
        def x_to_seconds(x: float) -> float | None:
            if x <= anchors[0]["x"]:
                return float(anchors[0]["seconds"])
            if x >= anchors[-1]["x"]:
                return float(anchors[-1]["seconds"])
            for i in range(len(anchors) - 1):
                a = anchors[i]
                b = anchors[i+1]
                if a["x"] <= x <= b["x"]:
                    frac = (x - a["x"]) / (b["x"] - a["x"])
                    return float(a["seconds"] + frac * (b["seconds"] - a["seconds"]))
            return None
            
        # 2. Clips extrahieren, die oberhalb y=520 platziert wurden (manuelle Zuweisung)
        manual_clips = []
        clip_map_by_name = {Path(c.get("file_path", c.get("path", ""))).stem.lower(): c for c in clips}
        clip_map_by_path = {c.get("file_path", c.get("path", "")).lower(): c for c in clips}
        
        for n in nodes:
            if n.get("type") == "file":
                y = float(n.get("y", 999))
                if y < 520: # Clip-Lobby-Grenze
                    file_rel = n.get("file", "")
                    if not file_rel.lower().endswith(".mp4"):
                        continue
                        
                    x = float(n.get("x", 0))
                    sec = x_to_seconds(x)
                    
                    if sec is not None:
                        filename = Path(file_rel).stem.lower()
                        clip_info = clip_map_by_name.get(filename)
                        if not clip_info:
                            for key_path, val in clip_map_by_path.items():
                                if filename in key_path:
                                    clip_info = val
                                    break
                                    
                        if clip_info:
                            manual_clips.append({
                                "id": clip_info.get("id"),
                                "file_path": clip_info.get("file_path", clip_info.get("path")),
                                "mix_start": sec,
                                "duration": float(clip_info.get("duration", 5.0) or 5.0),
                                "cluster": clip_info.get("cluster"),
                                "clip_info": clip_info
                            })
                            
        manual_clips.sort(key=lambda c: c["mix_start"])
        
        # 3. Überlappungen auflösen
        resolved = []
        last_end = 0.0
        for mc in manual_clips:
            if mc["mix_start"] < last_end:
                mc["mix_start"] = last_end
            mc["mix_end"] = mc["mix_start"] + mc["duration"]
            resolved.append(mc)
            last_end = mc["mix_end"]
            
        logger.info(f"{len(resolved)} manuelle Storyboard-Clips aus Obsidian Canvas geladen.")
        return resolved

    def generate_cut_list_with_stems(
        self,
        audio_path: str,
        stems: Dict[str, str],
        clips: list,
        pacing_config: dict,
        total_duration: float,
        duration_limit: float | None = None,
        cached_analysis: Dict | None = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> List[CutListEntry]:
        """L-K5: Stem-basiertes Pacing.

        Wrapper um AdvancedPacingEngine.generate_cut_list_with_stems().
        Nutzt dieselbe pre-cached-injection wie generate_cut_list (Beats/BPM/Energy/
        Bass/Subtracks), generiert dann Cuts via Demucs-Stems (drums/bass) und
        weist Clips per ClipSelector zu (Round-Robin als simple-fallback).

        Args:
            on_progress: Audit L-M7 — Callback(pct: float in [0..100]) wird
                         waehrend der Cut-Generation gefeuert (siehe Engine).
        """
        if not audio_path:
            raise ValueError("Audio-Pfad erforderlich.")
        if not clips:
            logger.warning("Keine Video-Clips vorhanden.")
            return []
        if not stems:
            logger.warning("L-K5: stems leer -> fallback auf generate_cut_list (no-stems)")
            return self.generate_cut_list(
                audio_path=audio_path,
                clips=clips,
                pacing_config=pacing_config,
                total_duration=total_duration,
                duration_limit=duration_limit,
                cached_analysis=cached_analysis,
                on_progress=on_progress,
            )

        from pb_studio.data.vector_store import VectorStore
        vstore = VectorStore(index_name="video_index")

        if (not total_duration or total_duration <= 0) and audio_path:
            try:
                total_duration = self._get_clip_duration(audio_path)
            except Exception as e:
                logger.warning(f"Ad-hoc Probe fehlgeschlagen: {e}")
                total_duration = 30.0

        semantic_enabled, song_mood = self._resolve_semantic_audio(
            audio_path,
            pacing_config.get("use_semantic_matching", False),
        )

        pacing_engine = AdvancedPacingEngine(
            trigger_settings=pacing_config["trigger_settings"]
        )
        pacing_engine.clip_selector.vector_store = vstore
        pacing_engine.clip_selector.use_semantic = semantic_enabled

        # Key-matching hook (E1 + L-K4) — auch fuer stem-pacing relevant
        if pacing_config.get("use_key_matching", False):
            pacing_engine.clip_selector.use_key_matching = True
            cached_audio_key = cached_analysis.get("key") if cached_analysis else None
            pacing_engine.clip_selector.audio_key = cached_audio_key
            video_keys_map: Dict[Any, str] = {}
            for c in clips:
                cid = c.get("id")
                ak = c.get("audio_key")
                if cid is not None and ak:
                    video_keys_map[cid] = ak
            pacing_engine.clip_selector.video_keys = video_keys_map
        else:
            pacing_engine.clip_selector.use_key_matching = False
            pacing_engine.clip_selector.audio_key = None
            pacing_engine.clip_selector.video_keys = {}

        # Pre-cached injection (Beats/Energy/Bass/Subtracks)
        self._inject_cached_into_engine(pacing_engine, audio_path, cached_analysis)
        self._configure_brain_selector(
            pacing_engine,
            pacing_config,
            cached_analysis,
            clips,
            total_duration,
            song_mood,
        )

        target_duration = duration_limit or total_duration
        min_cut_interval = float(pacing_config.get("min_cut_interval", 0.5))
        expected_bpm = pacing_config.get("expected_bpm", 120)

        logger.info(
            f"L-K5 Stem-Pacing: stems={list(stems.keys())} target={target_duration:.2f}s"
        )

        try:
            pacing_cuts = pacing_engine.generate_cut_list_with_stems(
                audio_path=audio_path,
                stems=stems,
                expected_bpm=expected_bpm,
                min_cut_interval=min_cut_interval,
                on_progress=on_progress,
            )

            # Stufe 3: Kapitel segmentieren
            pre_cached_beats_stems = []
            if cached_analysis:
                for b in cached_analysis.get("beats", []):
                    if isinstance(b, dict):
                        pre_cached_beats_stems.append(b.get("time", 0.0))
                    else:
                        pre_cached_beats_stems.append(float(b))

            chapters = self.segment_timeline_into_chapters(
                pacing_engine._pre_cached_energy if hasattr(pacing_engine, "_pre_cached_energy") else None,
                pre_cached_beats_stems,
                expected_bpm,
                target_duration
            )

            # Clip-Zuweisung via clip_selector (mit semantic prompt falls aktiv)
            # Stufe 4: Obsidian Canvas & manuelle Anker einlesen
            canvas_path = pacing_config.get("canvas_path")
            manual_anchors = self.load_canvas_manual_anchors(canvas_path, clips) if canvas_path else []

            cut_with_clips = []
            last_manual_end = 0.0
            last_manual_clip = None

            for cut_index, cut in enumerate(pacing_cuts):
                # Prüfen, ob wir uns in einem reservierten manuellen Storyboard-Clip-Intervall befinden
                active_anchor = None
                for ma in manual_anchors:
                    if ma["mix_start"] <= cut.time < ma["mix_end"]:
                        active_anchor = ma
                        break
                        
                if active_anchor:
                    # Verwende den manuellen Storyboard-Clip
                    cut_with_clips.append((cut, active_anchor["file_path"], f"clip_{active_anchor['id']}"))
                    last_manual_end = active_anchor["mix_end"]
                    last_manual_clip = active_anchor
                    continue

                prompt = song_mood if semantic_enabled else None
                if prompt and hasattr(cut, "segment_type") and cut.segment_type:
                    prompt = f"{cut.segment_type} {prompt}"
                
                # Finde das aktive Kapitelthema für diesen Schnitt
                active_theme = None
                for ch in chapters:
                    if ch["start"] <= cut.time < ch["end"]:
                        active_theme = ch["theme"]
                        break
                
                # Stufe 4: Bridge-Berechnung für anstehende und gerade verlassene manuelle Clips
                next_manual = None
                for ma in manual_anchors:
                    if ma["mix_start"] > cut.time:
                        next_manual = ma
                        break
                        
                bridging_in_to = None
                if next_manual and (next_manual["mix_start"] - cut.time) <= 8.0:
                    bridging_in_to = next_manual
                    
                bridging_out_of = None
                if last_manual_end and abs(cut.time - last_manual_end) < 0.2:
                    bridging_out_of = last_manual_clip
                    
                pacing_engine.clip_selector.bridging_in_to = bridging_in_to
                pacing_engine.clip_selector.bridging_out_of = bridging_out_of

                sel = pacing_engine.clip_selector.select_clip(
                    clips,
                    cut.strength,
                    cut.trigger_type,
                    prompt=prompt,
                    current_time=cut.time,
                    active_theme=active_theme,
                    cut_duration_sec=(
                        pacing_cuts[cut_index + 1].time - cut.time
                        if cut_index + 1 < len(pacing_cuts)
                        else 1.0
                    ),
                )
                cut_with_clips.append((cut, sel.clip_path, sel.clip_id))

                # Zurücksetzen der Bridge-Variablen
                pacing_engine.clip_selector.bridging_in_to = None
                pacing_engine.clip_selector.bridging_out_of = None

            if not cut_with_clips:
                logger.warning("L-K5 Stem-generation lieferte 0 Cuts -> fallback round-robin.")
                cut_list = self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    expected_bpm, target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
                return self._finalize_cut_list(cut_list, duration_limit or total_duration)

            cut_list = self._process_pacing_cuts_to_cutlist(cut_with_clips, target_duration)
            return self._finalize_cut_list(cut_list, duration_limit or total_duration)
        except Exception as e:
            logger.error(f"L-K5 Stem-Cut-Generierung fehlgeschlagen: {e}", exc_info=True)
            try:
                cut_list = self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    expected_bpm, target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
                return self._finalize_cut_list(cut_list, duration_limit or total_duration)
            except Exception as final_e:
                raise RuntimeError(
                    f"L-K5 Stem-Cut-Generierung endgueltig fehlgeschlagen: {final_e}"
                ) from e

    def generate_cut_list(
        self,
        audio_path: str,
        clips: list,
        pacing_config: dict,
        total_duration: float,
        duration_limit: float | None = None,
        sequencer_cuts: List[CutListEntry] | None = None,
        rule_engine: Any | None = None,
        cached_analysis: Dict | None = None,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> List[CutListEntry]:
        """Haupteinstiegspunkt für Cut-List-Generierung.

        Args:
            on_progress: Audit L-M7 — Callback(pct: float in [0..100]) wird waehrend
                         der Cut-Generation gefeuert (incremental, alle ~5%) damit
                         SSE-Subscriber bei langen Mixen Progress sehen.
        """
        if not audio_path:
            raise ValueError("Audio-Pfad erforderlich.")
        if not clips:
            logger.warning("Keine Video-Clips vorhanden.")
            return []

        # 1. Sequencer Cuts (höchste Priorität)
        if sequencer_cuts:
            logger.info(f"Verwende {len(sequencer_cuts)} Sequencer-Cuts.")
            clip_map = {f"clip_{c['id']}": c for c in clips}
            final_cuts = []
            for cut in sequencer_cuts:
                if cut.clip_id in clip_map:
                    cd = clip_map[cut.clip_id]
                    fp = str(Path(cd.get("file_path", "")).absolute())
                    if not cut.metadata:
                        cut.metadata = {}
                    cut.metadata.update({
                        "file_path": fp,
                        "clip_name": cd.get("name", "Unknown"),
                    })
                    if "clip_start" not in cut.metadata:
                        # R18/CRIT-018-1: CutListEntry has no .duration attribute —
                        # must compute from start_time/end_time.
                        cut_dur = cut.end_time - cut.start_time
                        cut.metadata["clip_start"] = self._get_random_clip_start(fp, cut_dur)

                    # R12b/SEV-004: Cap sequencer cut duration to actual clip length
                    # (automatic pacing paths already do this at lines 79-83 and 252-256)
                    try:
                        actual_clip_dur = self._get_clip_duration(fp)
                        clip_start = float(cut.metadata.get("clip_start", 0.0))
                        cut_dur = cut.end_time - cut.start_time
                        if actual_clip_dur > 0 and (clip_start + cut_dur) > actual_clip_dur:
                            cut.metadata["clip_start"] = 0.0
                            capped_dur = min(cut_dur, actual_clip_dur)
                            cut.end_time = cut.start_time + capped_dur
                    except ValueError:
                        pass  # ffprobe failed — let render handle it

                    final_cuts.append(cut)
            return self._finalize_cut_list(
                final_cuts,
                duration_limit or total_duration,
            )

        # 2. Rule Engine (mittlere Priorität)
        if rule_engine and hasattr(rule_engine, "rules") and rule_engine.rules:
            logger.info(f"Rule Engine mit {len(rule_engine.rules)} Regeln.")
            rule_engine.available_clips = clips
            target = duration_limit or total_duration
            return self._finalize_cut_list(
                rule_engine.apply_rules(duration=target),
                target,
            )

        # 3. Automatisches Pacing (Standard)
        from pb_studio.data.vector_store import VectorStore
        vstore = VectorStore(index_name="video_index")
        
        # S01/CRITICAL: Ensure total_duration is valid. If 0.0, probe it now.
        if (not total_duration or total_duration <= 0) and audio_path:
            logger.info(f"Audio-Dauer fehlt in Snapshot, starte Ad-hoc Probe: {audio_path}")
            try:
                total_duration = self._get_clip_duration(audio_path)
            except Exception as e:
                logger.warning(f"Ad-hoc Probe fehlgeschlagen: {e}")
                total_duration = 30.0 # Absoluter Notfall-Fallback

        semantic_enabled, song_mood = self._resolve_semantic_audio(
            audio_path,
            pacing_config.get("use_semantic_matching", False),
        )

        pacing_engine = AdvancedPacingEngine(
            trigger_settings=pacing_config["trigger_settings"]
        )
        # VectorStore für semantische Auswahl injizieren
        pacing_engine.clip_selector.vector_store = vstore
        pacing_engine.clip_selector.use_semantic = semantic_enabled

        target_duration = duration_limit or total_duration

        # Gecachte Beats aus vorheriger Audio-Analyse extrahieren
        pre_cached_beats: List[float] = []
        pre_cached_beat_strengths: List[float] = []
        has_real_beat_strengths = False
        pre_cached_bpm: float | None = None
        if cached_analysis:
            for b in cached_analysis.get("beats", []):
                if isinstance(b, dict):
                    pre_cached_beats.append(b.get("time", 0.0))
                    # Audit L-N8: per-beat strength as trigger-weight multiplier
                    s = b.get("strength")
                    if s is None:
                        pre_cached_beat_strengths.append(1.0)
                    else:
                        pre_cached_beat_strengths.append(float(s))
                        has_real_beat_strengths = True
                else:
                    pre_cached_beats.append(float(b))
                    pre_cached_beat_strengths.append(1.0)
            pre_cached_bpm = cached_analysis.get("bpm") or None
            if pre_cached_beats:
                logger.info(
                    f"Gecachte Analyse: {len(pre_cached_beats)} Beats, "
                    f"BPM={pre_cached_bpm}"
                )

        # C1/HIGH: Read min_cut_interval from config (was hardcoded to 0.5)
        min_cut_interval = float(pacing_config.get("min_cut_interval", 0.5))

        logger.info(
            f"Cut-Liste für {target_duration:.2f}s generieren "
            f"(Motion={pacing_config.get('use_motion_matching', False)}, "
            f"Semantic={semantic_enabled})"
        )

        # Pre-cached Beats + Dauer + Kurven injizieren
        self._inject_cached_into_engine(pacing_engine, audio_path, cached_analysis)
        self._configure_brain_selector(
            pacing_engine,
            pacing_config,
            cached_analysis,
            clips,
            total_duration,
            song_mood,
        )

        # Audit E1 + L-K4: use_key_matching — Camelot-Wheel key compatibility scoring.
        if pacing_config.get("use_key_matching", False):
            pacing_engine.clip_selector.use_key_matching = True
            cached_audio_key = cached_analysis.get("key") if cached_analysis else None
            pacing_engine.clip_selector.audio_key = cached_audio_key
            video_keys_map: Dict[Any, str] = {}
            for c in clips:
                cid = c.get("id")
                ak = c.get("audio_key")
                if cid is not None and ak:
                    video_keys_map[cid] = ak
            pacing_engine.clip_selector.video_keys = video_keys_map
            logger.info(
                "Audit E1 + L-K4: use_key_matching aktiviert (audio_key=%r, "
                "%d/%d video_keys verfuegbar) — Camelot-Wheel Score in "
                "clip_selector._key_compatibility_score wirksam",
                cached_audio_key, len(video_keys_map), len(clips),
            )
        else:
            pacing_engine.clip_selector.use_key_matching = False
            pacing_engine.clip_selector.audio_key = None
            pacing_engine.clip_selector.video_keys = {}

        try:
            # Entscheide welche Generierungsmethode genutzt wird
            use_advanced = _uses_advanced_pacing(pacing_config, semantic_enabled)

            if use_advanced:
                if pacing_config.get("use_motion_matching", False):
                    pacing_engine.enable_motion_matching(True)
                
                if pacing_config.get("use_structure_awareness", False):
                    # Audit A3: structure_segments wird in audio_router persistiert
                    # (state.update_audio_analysis(...structure_segments=...)) — wenn
                    # vorhanden, direkt in Engine injizieren statt redundanter librosa-
                    # Re-Analyse (~5s Overhead bei generate_cut_list_with_structure).
                    cached_segments = (
                        cached_analysis.get("structure_segments")
                        if cached_analysis else None
                    )
                    if cached_segments and len(cached_segments) > 0:
                        # Direct-inject: generate_cut_list_with_structure liest
                        # self.song_structure und überspringt analyze_song_structure.
                        pacing_engine.song_structure = cached_segments
                        self._last_skipped_structure_reanalyze = True
                        logger.info(
                            "Audit A3: Cached structure_segments injiziert "
                            f"({len(cached_segments)} Sektionen) — librosa-Re-Analyse skipped"
                        )
                    else:
                        # Fallback: keine cached_segments verfügbar → normale Analyse.
                        # generate_cut_list_with_structure ruft analyze_song_structure
                        # selbst auf, also ist hier kein doppelter Call nötig.
                        self._last_skipped_structure_reanalyze = False
                    pacing_cuts = pacing_engine.generate_cut_list_with_structure(
                        audio_path=audio_path,
                        expected_bpm=pacing_config.get("expected_bpm", 120),
                        min_cut_interval=min_cut_interval,
                        on_progress=on_progress,
                    )
                else:
                    pacing_cuts_raw = pacing_engine.generate_cut_list(
                        audio_track=audio_path,
                        expected_bpm=pacing_config.get("expected_bpm", 120),
                        min_cut_interval=min_cut_interval,
                        on_progress=on_progress,
                    )
                    # Konvertiere rohe CutPoints in das erwartete Format für die weitere Verarbeitung
                    pacing_cuts = pacing_cuts_raw

                # Stufe 3: Kapitel segmentieren
                pre_cached_beats_adv = []
                if cached_analysis:
                    for b in cached_analysis.get("beats", []):
                        if isinstance(b, dict):
                            pre_cached_beats_adv.append(b.get("time", 0.0))
                        else:
                            pre_cached_beats_adv.append(float(b))

                chapters = self.segment_timeline_into_chapters(
                    pacing_engine._pre_cached_energy if hasattr(pacing_engine, "_pre_cached_energy") else None,
                    pre_cached_beats_adv,
                    pacing_config.get("expected_bpm", 120),
                    target_duration
                )

                # Stimmung ermitteln für semantisches Matching
                # Stufe 4: Obsidian Canvas & manuelle Anker einlesen
                canvas_path = pacing_config.get("canvas_path")
                manual_anchors = self.load_canvas_manual_anchors(canvas_path, clips) if canvas_path else []

                cut_with_clips = []
                last_manual_end = 0.0
                last_manual_clip = None

                for cut_index, cut in enumerate(pacing_cuts):
                    # Prüfen, ob wir uns in einem reservierten manuellen Storyboard-Clip-Intervall befinden
                    active_anchor = None
                    for ma in manual_anchors:
                        if ma["mix_start"] <= cut.time < ma["mix_end"]:
                            active_anchor = ma
                            break
                            
                    if active_anchor:
                        # Verwende den manuellen Storyboard-Clip
                        cut_with_clips.append((cut, active_anchor["file_path"], f"clip_{active_anchor['id']}"))
                        last_manual_end = active_anchor["mix_end"]
                        last_manual_clip = active_anchor
                        continue

                    prompt = song_mood if semantic_enabled else None
                    # Falls Struktur aktiv, prompt verfeinern
                    if prompt and hasattr(cut, "segment_type") and cut.segment_type:
                        prompt = f"{cut.segment_type} {prompt}"
                    
                    # Finde das aktive Kapitelthema für diesen Schnitt
                    active_theme = None
                    for ch in chapters:
                        if ch["start"] <= cut.time < ch["end"]:
                            active_theme = ch["theme"]
                            break

                    # Stufe 4: Bridge-Berechnung für anstehende und gerade verlassene manuelle Clips
                    next_manual = None
                    for ma in manual_anchors:
                        if ma["mix_start"] > cut.time:
                            next_manual = ma
                            break
                            
                    bridging_in_to = None
                    if next_manual and (next_manual["mix_start"] - cut.time) <= 8.0:
                        bridging_in_to = next_manual
                        
                    bridging_out_of = None
                    if last_manual_end and abs(cut.time - last_manual_end) < 0.2:
                        bridging_out_of = last_manual_clip
                        
                    pacing_engine.clip_selector.bridging_in_to = bridging_in_to
                    pacing_engine.clip_selector.bridging_out_of = bridging_out_of

                    sel = pacing_engine.clip_selector.select_clip(
                        clips,
                        cut.strength,
                        cut.trigger_type,
                        prompt=prompt,
                        current_time=cut.time,
                        active_theme=active_theme,
                        cut_duration_sec=(
                            pacing_cuts[cut_index + 1].time - cut.time
                            if cut_index + 1 < len(pacing_cuts)
                            else 1.0
                        ),
                    )
                    cut_with_clips.append((cut, sel.clip_path, sel.clip_id))

                    # Zurücksetzen der Bridge-Variablen
                    pacing_engine.clip_selector.bridging_in_to = None
                    pacing_engine.clip_selector.bridging_out_of = None
                
                if not cut_with_clips:
                    logger.warning("Advanced generation delivered 0 cuts, falling back to simple mode.")
                    cut_list = self._generate_simple_round_robin(
                        pacing_engine, audio_path, clips,
                        pacing_config.get("expected_bpm", 120), target_duration,
                        min_cut_interval=min_cut_interval,
                        on_progress=on_progress,
                    )
                    return self._finalize_cut_list(cut_list, duration_limit or total_duration)

                cut_list = self._process_pacing_cuts_to_cutlist(cut_with_clips, target_duration)
                return self._finalize_cut_list(cut_list, duration_limit or total_duration)
            else:
                cut_list = self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    pacing_config.get("expected_bpm", 120), target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
                return self._finalize_cut_list(cut_list, duration_limit or total_duration)
        except Exception as e:
            logger.error(f"Cut-List-Generierung fehlgeschlagen: {e}", exc_info=True)
            # Letzter Rettungsanker: Einfaches Round-Robin statt Absturz
            try:
                cut_list = self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    pacing_config.get("expected_bpm", 120), target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
                return self._finalize_cut_list(cut_list, duration_limit or total_duration)
            except Exception as final_e:
                raise RuntimeError(f"Cut-List-Generierung endgültig fehlgeschlagen: {final_e}") from e

    def _generate_simple_round_robin(
        self, engine, audio_path, clips, bpm, target_duration,
        min_cut_interval: float = 0.5,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> List[CutListEntry]:
        """Einfache Round-Robin Clip-Zuweisung."""
        if not clips:
            raise ValueError("Mindestens ein Clip erforderlich.")

        pacing_cuts = engine.generate_cut_list(
            audio_track=audio_path, expected_bpm=bpm,
            min_cut_interval=min_cut_interval,
            on_progress=on_progress,
        )

        cut_list = []
        idx = 0
        for i in range(len(pacing_cuts) - 1):
            cur, nxt = pacing_cuts[i], pacing_cuts[i + 1]
            if target_duration and cur.time >= target_duration:
                break
            dur = nxt.time - cur.time
            if dur < 0.5:
                continue

            clip = clips[idx % len(clips)]
            fp = clip.get("file_path", "")
            if not fp:
                idx += 1
                continue
            fp = str(Path(fp).absolute())
            cs = self._get_random_clip_start(fp, dur)

            # Prüfe ob out_point die tatsächliche Clip-Dauer überschreitet
            actual_clip_dur = self._get_clip_duration(fp)
            if actual_clip_dur > 0 and (cs + dur) > actual_clip_dur:
                cs = 0.0
                dur = min(dur, actual_clip_dur)

            cut_list.append(CutListEntry(
                clip_id=f"clip_{clip['id']}",
                start_time=cur.time,
                end_time=cur.time + dur,
                metadata={
                    "file_path": fp,
                    "clip_name": clip.get("name", "Unknown"),
                    "clip_start": cs,
                    "trigger_type": cur.trigger_type,
                    "trigger_strength": cur.strength,
                    **(
                        {"trigger_provenance": dict(cur.provenance)}
                        if getattr(cur, "provenance", None)
                        else {}
                    ),
                },
            ))
            idx += 1

        logger.info(f"Cut-Liste: {len(cut_list)} Cuts generiert.")
        return cut_list
