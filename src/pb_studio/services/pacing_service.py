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
from typing import Any, List, Dict, Optional

from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import CutListEntry

logger = logging.getLogger(__name__)


class PacingService:
    """Service-Layer für Cut-List-Generierung."""

    def _get_clip_duration(self, clip_path: str) -> float:
        """Ermittelt Clip-Dauer via ffprobe (kein ffmpeg-python)."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(clip_path),
        ]
        try:
            res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            return float(json.loads(res)["format"]["duration"])
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
    ) -> List[CutListEntry]:
        """Haupteinstiegspunkt für Cut-List-Generierung."""
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
                    cut.metadata.update(
                        {
                            "file_path": fp,
                            "clip_name": cd.get("name", "Unknown"),
                        }
                    )
                    if "clip_start" not in cut.metadata:
                        cut.metadata["clip_start"] = self._get_random_clip_start(
                            fp, cut.duration
                        )
                    final_cuts.append(cut)
            return final_cuts

        # 2. Rule Engine (mittlere Priorität)
        if rule_engine and hasattr(rule_engine, "rules") and rule_engine.rules:
            logger.info(f"Rule Engine mit {len(rule_engine.rules)} Regeln.")
            rule_engine.available_clips = clips
            target = duration_limit or total_duration
            return rule_engine.apply_rules(duration=target)

        # 3. Automatisches Pacing (Standard)
        pacing_engine = AdvancedPacingEngine(
            trigger_settings=pacing_config["trigger_settings"]
        )
        target_duration = duration_limit or total_duration

        # Gecachte Beats aus vorheriger Audio-Analyse extrahieren
        pre_cached_beats: List[float] = []
        pre_cached_bpm: float | None = None
        if cached_analysis:
            for b in cached_analysis.get("beats", []):
                if isinstance(b, dict):
                    pre_cached_beats.append(b.get("time", 0.0))
                else:
                    pre_cached_beats.append(float(b))
            pre_cached_bpm = cached_analysis.get("bpm") or None
            if pre_cached_beats:
                logger.info(
                    f"Gecachte Analyse: {len(pre_cached_beats)} Beats, "
                    f"BPM={pre_cached_bpm}"
                )

        logger.info(
            f"Cut-Liste für {target_duration:.2f}s generieren "
            f"(Motion={pacing_config.get('use_motion_matching', False)})"
        )

        # Pre-cached Beats in Engine injizieren (vermeidet Re-Analyse langer Dateien)
        if pre_cached_beats:
            pacing_engine._cached_audio_path = audio_path
            pacing_engine._pre_cached_beats = pre_cached_beats
            if pre_cached_bpm:
                pacing_engine._pre_cached_bpm = pre_cached_bpm

        try:
            if pacing_config.get("use_motion_matching", False):
                pacing_engine.enable_motion_matching(True)
                if pacing_config.get("use_structure_awareness", False):
                    pacing_engine.analyze_song_structure(audio_path)
                    pacing_cuts = pacing_engine.generate_cut_list_with_structure(
                        audio_path=audio_path,
                        expected_bpm=pacing_config.get("expected_bpm", 120),
                        min_cut_interval=0.5,
                    )
                    cut_with_clips = []
                    for cut in pacing_cuts:
                        sel = pacing_engine.clip_selector.select_clip(
                            clips, cut.strength, cut.trigger_type
                        )
                        cut_with_clips.append((cut, sel.clip_path, sel.clip_id))
                else:
                    raw = pacing_engine.generate_cut_list_with_clips(
                        audio_path=audio_path,
                        available_clips=clips,
                        expected_bpm=pacing_config.get("expected_bpm", 120),
                        min_cut_interval=0.5,
                    )
                    cut_with_clips = [
                        (c, cl.get("file_path", ""), cl.get("id", "unknown"))
                        for c, cl in raw
                    ]
                return self._process_pacing_cuts_to_cutlist(
                    cut_with_clips, target_duration
                )
            else:
                return self._generate_simple_round_robin(
                    pacing_engine,
                    audio_path,
                    clips,
                    pacing_config.get("expected_bpm", 120),
                    target_duration,
                )
        except Exception as e:
            logger.error(f"Cut-List-Generierung fehlgeschlagen: {e}", exc_info=True)
            raise RuntimeError(f"Cut-List-Generierung fehlgeschlagen: {e}") from e

    def _generate_simple_round_robin(
        self, engine, audio_path, clips, bpm, target_duration
    ) -> List[CutListEntry]:
        """Einfache Round-Robin Clip-Zuweisung."""
        if not clips:
            raise ValueError("Mindestens ein Clip erforderlich.")

        pacing_cuts = engine.generate_cut_list(
            audio_track=audio_path, expected_bpm=bpm, min_cut_interval=0.5
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

            cut_list.append(
                CutListEntry(
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
                )
            )
            idx += 1

        logger.info(f"Cut-Liste: {len(cut_list)} Cuts generiert.")
        return cut_list
