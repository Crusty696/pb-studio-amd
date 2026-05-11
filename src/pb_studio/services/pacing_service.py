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
from pathlib import Path
from typing import Any, List, Dict, Callable, Optional

from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import CutListEntry

logger = logging.getLogger(__name__)


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

    def _get_clip_duration(self, clip_path: str) -> float:
        """Ermittelt Clip-Dauer via ffprobe (kein ffmpeg-python). Cached per Pfad."""
        key = str(clip_path)
        if key in self._duration_cache:
            return self._duration_cache[key]
        cmd = [
            "ffprobe", "-v", "error",
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

            cut = CutListEntry(
                clip_id=f"clip_{clip_id}",
                start_time=current_cut.time,
                end_time=next_cut.time,
                metadata=metadata,
            )
            cut_list.append(cut)
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
        has_real_strengths = False
        for b in cached_analysis.get("beats", []):
            if isinstance(b, dict):
                pre_cached_beats.append(b.get("time", 0.0))
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
            pacing_engine._cached_audio_path = audio_path
            pacing_engine._pre_cached_beats = pre_cached_beats
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
        vstore = VectorStore()

        if (not total_duration or total_duration <= 0) and audio_path:
            try:
                total_duration = self._get_clip_duration(audio_path)
            except Exception as e:
                logger.warning(f"Ad-hoc Probe fehlgeschlagen: {e}")
                total_duration = 30.0

        pacing_engine = AdvancedPacingEngine(
            trigger_settings=pacing_config["trigger_settings"]
        )
        pacing_engine.clip_selector.vector_store = vstore
        pacing_engine.clip_selector.use_semantic = pacing_config.get("use_semantic_matching", False)

        # Brain reranker hook (gleich wie generate_cut_list)
        if pacing_config.get("use_brain", False):
            try:
                from pb_studio.brain.brain_service import BrainService
                svc = BrainService.get()
                pacing_engine.clip_selector.brain_reranker = svc.reranker
                pacing_engine.clip_selector.brain_context_keys = [""]
            except Exception as e:
                logger.warning(f"Brain deep-hook bind fehlgeschlagen: {e}")

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

            # Clip-Zuweisung via clip_selector (mit semantic prompt falls aktiv)
            song_mood = "energetic music"
            if pacing_config.get("use_semantic_matching", False):
                try:
                    from pb_studio.ai.smart_director import SmartDirector
                    director = SmartDirector.get_instance()
                    song_mood = director.get_dominant_mood(audio_path)
                except Exception as e:
                    logger.warning(f"SmartDirector mood-detection failed: {e}")

            cut_with_clips = []
            for cut in pacing_cuts:
                prompt = song_mood if pacing_config.get("use_semantic_matching", False) else None
                if prompt and hasattr(cut, "segment_type") and cut.segment_type:
                    prompt = f"{cut.segment_type} {prompt}"
                sel = pacing_engine.clip_selector.select_clip(
                    clips, cut.strength, cut.trigger_type, prompt=prompt
                )
                cut_with_clips.append((cut, sel.clip_path, sel.clip_id))

            if not cut_with_clips:
                logger.warning("L-K5 Stem-generation lieferte 0 Cuts -> fallback round-robin.")
                return self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    expected_bpm, target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )

            return self._process_pacing_cuts_to_cutlist(cut_with_clips, target_duration)
        except Exception as e:
            logger.error(f"L-K5 Stem-Cut-Generierung fehlgeschlagen: {e}", exc_info=True)
            try:
                return self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    expected_bpm, target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
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
            return final_cuts

        # 2. Rule Engine (mittlere Priorität)
        if rule_engine and hasattr(rule_engine, "rules") and rule_engine.rules:
            logger.info(f"Rule Engine mit {len(rule_engine.rules)} Regeln.")
            rule_engine.available_clips = clips
            target = duration_limit or total_duration
            return rule_engine.apply_rules(duration=target)

        # 3. Automatisches Pacing (Standard)
        from pb_studio.data.vector_store import VectorStore
        vstore = VectorStore()
        
        # S01/CRITICAL: Ensure total_duration is valid. If 0.0, probe it now.
        if (not total_duration or total_duration <= 0) and audio_path:
            logger.info(f"Audio-Dauer fehlt in Snapshot, starte Ad-hoc Probe: {audio_path}")
            try:
                total_duration = self._get_clip_duration(audio_path)
            except Exception as e:
                logger.warning(f"Ad-hoc Probe fehlgeschlagen: {e}")
                total_duration = 30.0 # Absoluter Notfall-Fallback
        
        pacing_engine = AdvancedPacingEngine(
            trigger_settings=pacing_config["trigger_settings"]
        )
        # VectorStore für semantische Auswahl injizieren
        pacing_engine.clip_selector.vector_store = vstore
        pacing_engine.clip_selector.use_semantic = pacing_config.get("use_semantic_matching", False)

        # Plan Phase 4 deep hook: BrainReranker an clip_selector binden, wenn use_brain=true.
        # Pro Cut wird vom Caller context_keys + audio/video features gesetzt.
        if pacing_config.get("use_brain", False):
            try:
                from pb_studio.brain.brain_service import BrainService
                svc = BrainService.get()
                pacing_engine.clip_selector.brain_reranker = svc.reranker
                # Default-Kontext (level-0 only, übersteuert pro Cut wenn vorhanden):
                pacing_engine.clip_selector.brain_context_keys = [""]
                logger.info("Brain reranker an clip_selector gebunden (deep hook)")
            except Exception as e:
                logger.warning(f"Brain deep-hook bind fehlgeschlagen: {e}")
        
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
            f"Semantic={pacing_config.get('use_semantic_matching', False)})"
        )

        # Pre-cached Beats + Dauer in Engine injizieren
        if pre_cached_beats:
            pacing_engine._cached_audio_path = audio_path
            pacing_engine._pre_cached_beats = pre_cached_beats
            # Audit L-N8: per-beat strength als trigger-weight multiplier
            if has_real_beat_strengths:
                pacing_engine._pre_cached_beat_strengths = pre_cached_beat_strengths
            if pre_cached_bpm:
                pacing_engine._pre_cached_bpm = pre_cached_bpm
            cached_dur = float(cached_analysis.get("duration_seconds", 0.0) or 0.0)
            if cached_dur > 0:
                pacing_engine._pre_cached_duration = cached_dur

        # Audit A2: inject cached energy_curve damit Engine RMS-Neuberechnung skippen kann.
        # cached_analysis["energy_curve"] wird in audio_router.py persistiert
        # (state.update_audio_analysis(...energy_curve=...)) — pacing_service liest es
        # ab jetzt und injiziert in pacing_engine._pre_cached_energy.
        cached_energy = cached_analysis.get("energy_curve") if cached_analysis else None
        if cached_energy:
            import numpy as _np
            pacing_engine._pre_cached_energy = _np.array(cached_energy, dtype=_np.float32)
            self._last_used_cached_energy = True
        else:
            self._last_used_cached_energy = False

        # Audit E2: inject cached bass_curve fuer drop-section trigger weighting.
        # cached_analysis["spectral_data"]["bands"]["low"] enthaelt das Bass-Frequenzband
        # (vom SpectralAnalyzer 3-Band Output). Engine nutzt es ueber
        # _bass_weight_at_time() als Multiplikator (1.0..2.0) auf Trigger-Strengths
        # in Drop-Sektionen — verstaerkt Cuts an basslastigen Momenten.
        spectral = cached_analysis.get("spectral_data") if cached_analysis else None
        if spectral and isinstance(spectral, dict):
            bands = spectral.get("bands", {})
            low_band = bands.get("low") if isinstance(bands, dict) else None
            if low_band and len(low_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_bass_curve = _np.array(low_band, dtype=_np.float32)
                # Duration sicherstellen (fuer time->index mapping in _bass_weight_at_time)
                if not hasattr(pacing_engine, "_pre_cached_duration") or \
                        getattr(pacing_engine, "_pre_cached_duration", 0.0) <= 0:
                    cached_dur = float(cached_analysis.get("duration_seconds", 0.0) or 0.0)
                    if cached_dur > 0:
                        pacing_engine._pre_cached_duration = cached_dur
                self._last_used_cached_bass = True
            else:
                self._last_used_cached_bass = False

            # Audit L-M2: inject mid + high curves analog bass.
            # spectral_data.bands.mid + .high werden vom SpectralAnalyzer 3-Band
            # Output gleich neben .low persistiert. Engine nutzt sie via
            # _mid_weight_at_time() / _high_weight_at_time() — Helper-API ready
            # fuer Strength-Multiplikator-Anwendung in Cut-Selection.
            mid_band = bands.get("mid") if isinstance(bands, dict) else None
            if mid_band and len(mid_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_mid_curve = _np.array(
                    mid_band, dtype=_np.float32
                )
                logger.info(
                    "Audit L-M2: mid_curve injiziert (%d Werte) — "
                    "Helper _mid_weight_at_time(t) verfuegbar",
                    len(mid_band),
                )
            high_band = bands.get("high") if isinstance(bands, dict) else None
            if high_band and len(high_band) > 0:
                import numpy as _np
                pacing_engine._pre_cached_high_curve = _np.array(
                    high_band, dtype=_np.float32
                )
                logger.info(
                    "Audit L-M2: high_curve injiziert (%d Werte) — "
                    "Helper _high_weight_at_time(t) verfuegbar",
                    len(high_band),
                )
        else:
            self._last_used_cached_bass = False

        # Audit E3: inject cached subtrack_segments fuer subtrack-aware cut generation.
        # SubtrackDetector erzeugt Segmente fuer Mixe >60s mit start_time/end_time/
        # confidence; tempo_curve ergaenzt das Bild. Engine nutzt
        # _subtrack_boundary_anchors() um cut-anchors an subtrack-grenzen zu
        # platzieren (snap-to-subtrack). Heute reicht: Liste injizieren + Flag
        # setzen, Helper-API ist ready fuer cut-selection-Integration.
        subtracks = cached_analysis.get("subtrack_segments") if cached_analysis else None
        if subtracks and isinstance(subtracks, list) and len(subtracks) > 0:
            pacing_engine._pre_cached_subtracks = subtracks
            self._last_used_cached_subtracks = True
            logger.info(
                "Audit E3: %d cached subtrack_segments injiziert "
                "(boundary-anchors verfuegbar via _subtrack_boundary_anchors())",
                len(subtracks),
            )
        else:
            self._last_used_cached_subtracks = False

        # Audit L-M1: inject cached tempo_curve fuer varying-BPM-Mixe.
        # cached_analysis["tempo_curve"] kommt vom SubtrackDetector (DJ-Tempo-
        # Variation pro Subtrack). Engine nutzt es via _tempo_at_time(t) ->
        # liefert lokale BPM zum Zeitpunkt t (lineares mapping). Heute reicht:
        # Curve injizieren + Flag setzen, Helper-API ist ready.
        tempo_curve = cached_analysis.get("tempo_curve") if cached_analysis else None
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
            logger.info(
                "Audit L-M1: tempo_curve injiziert (%d Werte) — "
                "Helper _tempo_at_time(t) verfuegbar fuer varying-BPM-Pacing",
                len(tempo_curve),
            )
        else:
            self._last_used_cached_tempo = False

        # Audit E1 + L-K4: use_key_matching — Camelot-Wheel key compatibility scoring.
        # cached_analysis["key"] wird in audio_router persistiert; pacing_engine.clip_selector
        # nutzt _key_compatibility_score(audio_key, video_key) zur Score-Anpassung.
        # L-K4: Video-Clips haben jetzt audio_key Feld (via audio_key_detector) -> echter
        # Effekt statt 0.5-Neutral. video_keys: {clip_id: audio_key_str} pro Clip.
        if pacing_config.get("use_key_matching", False):
            pacing_engine.clip_selector.use_key_matching = True
            cached_audio_key = cached_analysis.get("key") if cached_analysis else None
            pacing_engine.clip_selector.audio_key = cached_audio_key
            # L-K4: Map clip_id -> audio_key fuer Per-Clip Compatibility-Score.
            # Nur Clips mit nicht-leerem audio_key — None/missing wirkt im Score
            # als neutral (0.5) statt Penalty.
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
            use_advanced = (
                pacing_config.get("use_motion_matching", False) or 
                pacing_config.get("use_semantic_matching", False) or
                pacing_config.get("use_structure_awareness", False)
            )

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

                # Stimmung ermitteln für semantisches Matching
                song_mood = "energetic music"
                if pacing_config.get("use_semantic_matching", False):
                    from pb_studio.ai.smart_director import SmartDirector
                    director = SmartDirector.get_instance()
                    song_mood = director.get_dominant_mood(audio_path)

                cut_with_clips = []
                for cut in pacing_cuts:
                    prompt = song_mood if pacing_config.get("use_semantic_matching", False) else None
                    # Falls Struktur aktiv, prompt verfeinern
                    if prompt and hasattr(cut, "segment_type") and cut.segment_type:
                        prompt = f"{cut.segment_type} {prompt}"
                    
                    sel = pacing_engine.clip_selector.select_clip(
                        clips, cut.strength, cut.trigger_type, prompt=prompt
                    )
                    cut_with_clips.append((cut, sel.clip_path, sel.clip_id))
                
                if not cut_with_clips:
                    logger.warning("Advanced generation delivered 0 cuts, falling back to simple mode.")
                    return self._generate_simple_round_robin(
                        pacing_engine, audio_path, clips,
                        pacing_config.get("expected_bpm", 120), target_duration,
                        min_cut_interval=min_cut_interval,
                        on_progress=on_progress,
                    )

                return self._process_pacing_cuts_to_cutlist(cut_with_clips, target_duration)
            else:
                return self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    pacing_config.get("expected_bpm", 120), target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
        except Exception as e:
            logger.error(f"Cut-List-Generierung fehlgeschlagen: {e}", exc_info=True)
            # Letzter Rettungsanker: Einfaches Round-Robin statt Absturz
            try:
                return self._generate_simple_round_robin(
                    pacing_engine, audio_path, clips,
                    pacing_config.get("expected_bpm", 120), target_duration,
                    min_cut_interval=min_cut_interval,
                    on_progress=on_progress,
                )
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
                end_time=nxt.time,
                metadata={
                    "file_path": fp,
                    "clip_name": clip.get("name", "Unknown"),
                    "clip_start": cs,
                    "trigger_type": cur.trigger_type,
                    "trigger_strength": cur.strength,
                },
            ))
            idx += 1

        logger.info(f"Cut-Liste: {len(cut_list)} Cuts generiert.")
        return cut_list
