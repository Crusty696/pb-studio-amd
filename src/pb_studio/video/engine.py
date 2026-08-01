import logging
import random
import subprocess
import uuid
import numpy as np
import shutil
from pathlib import Path
from ..audio.analyzer import AudioAnalyzer
from .encoder_utils import (
    get_preview_encoder,
    get_export_encoder,
    build_ffmpeg_encode_args,
    check_amf_available,
    get_encoder_info,
    get_amf_device_args,
    _get_ffmpeg_path,
    _get_ffprobe_path,
)

logger = logging.getLogger(__name__)

class VideoGenerator:
    def __init__(self):
        self.analyzer = AudioAnalyzer()
        self.cancel_flag = False

        # Log encoder availability at init
        encoder_info = get_encoder_info()
        if encoder_info["amf_available"]:
            logger.info("AMD AMF hardware encoding enabled")
        else:
            logger.error("AMD AMF hardware encoding unavailable; rendering will fail")

    def generate(self, config: dict, callback=None):
        """
        Main generation loop.
        config: {
            "master_audio": str,
            "source_videos": list,
            "output_path": str,
            "pacing": int, # 1-5
            "min_dur": float,
            "max_dur": float,
            "precision": int, # 1-10
            "energy_react": int, # 0-10
            "chaos": int, # 0-10
            "temp_dir": str,
            "output_codec": str,  # 'h264', 'hevc', or 'av1'
            "output_quality": str  # 'speed', 'balanced', 'quality'
        }
        """
        master_audio = config["master_audio"]
        source_videos = config["source_videos"]
        output_path = config["output_path"]

        if self.cancel_flag:
            return {"output_path": output_path, "cancelled": True}

        temp_base = Path(config.get("temp_dir", "./data/temp_render"))
        temp_dir = temp_base / f"render_{uuid.uuid4().hex[:8]}"

        # Encoding settings
        if config.get("use_hardware_encoding", True) is False:
            raise ValueError("Software encoding is prohibited; AMD AMF is required")
        self.use_hardware = True
        self.output_codec = config.get("output_codec", "h264")
        self.output_quality = config.get("output_quality", "balanced")

        # 1. Validation
        if not Path(master_audio).exists():
            raise FileNotFoundError(f"Master audio not found: {master_audio}")
        if not source_videos:
            raise ValueError("No video sources selected.")

        # Ensure temp dir (unique per render, safe for parallel execution)
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 2. Analyze Audio (Beats & Energy)
            if callback: callback("Analyzing Audio...", 0)
            analysis = self.analyzer.analyze_file(master_audio)
            if self.cancel_flag:
                return {"output_path": output_path, "cancelled": True}

            # Get Energy Profile (Librosa)
            import librosa
            try:
                # BUG-088 FIX: Handle potential librosa load errors
                y, sr = librosa.load(master_audio, sr=22050, mono=True)
            except Exception as e:
                logger.error(f"Failed to load master audio {master_audio}: {e}")
                raise RuntimeError(f"Audio loading failed: {e}")
                
            duration = librosa.get_duration(y=y, sr=sr)
            rms = librosa.feature.rms(y=y)[0]
            # Normalize RMS
            rms = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
            times = librosa.times_like(rms, sr=sr)

            # 3. Plan Cuts
            if callback: callback("Planning Cuts...", 10)
            cut_list = self._plan_cuts(config, analysis, rms, times, duration)
            logger.info(f"Planned {len(cut_list)} cuts.")
            if self.cancel_flag:
                return {"output_path": output_path, "cancelled": True}

            # 4. Process Segments (Render)
            if callback: callback("Rendering Segments...", 20)
            processed_segments = self._render_segments(cut_list, source_videos, temp_dir, callback)
            if self.cancel_flag:
                return {"output_path": output_path, "cancelled": True}

            # 5. Concat
            if callback: callback("Finalizing...", 90)
            self._concat_segments(processed_segments, master_audio, output_path)

            if callback: callback("Done!", 100)

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise
        finally:
            # Cleanup temp? Maybe keep for debug if chaos high?
            # For now, cleanup.
            if temp_dir.exists() and not config.get("keep_temp", False):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.debug(f"Could not clean temp dir: {e}")

    def _plan_cuts(self, config, analysis, rms, times, total_duration):
        """Generates a list of (start_time, duration) for the final video."""
        cuts = []
        current_time = 0.0

        beats = [b[0] for b in analysis.get("beat_data", [])]
        bpm = analysis.get("bpm", 120)

        # Settings
        min_dur = config.get("min_dur", 2.0)
        max_dur = config.get("max_dur", 8.0)
        precision = config.get("precision", 8) / 10.0 # 0.1 to 1.0
        energy_factor = config.get("energy_react", 5) / 10.0
        chaos = config.get("chaos", 2) / 10.0
        pacing_lvl = config.get("pacing", 3)

        # Base duration scale based on Pacing settings
        # Level 1 (Slow) -> favor max_dur
        # Level 5 (Fast) -> favor min_dur

        while current_time < total_duration:
            # 1. Determine Target Duration
            # Get local energy
            if len(rms) == 0:
                local_energy = 0.5
            else:
                idx = int((current_time / total_duration) * len(rms))
                idx = min(idx, len(rms) - 1)
                local_energy = rms[idx]

            # Calculate target duration
            # High energy -> Shorter clips
            # Low energy -> Longer clips

            # Bias: 0.0 (Fast) to 1.0 (Slow)
            # Pacing 5 -> Bias 0.0
            # Pacing 1 -> Bias 1.0
            pacing_bias = 1.0 - ((pacing_lvl - 1) / 4.0)

            # Energy influence
            # If high energy (1.0), we want to reduce bias towards 0 (Fast)
            # intensity = local_energy * energy_factor

            # Combined Factor (0=Fast, 1=Slow)
            speed_factor = pacing_bias - (local_energy * energy_factor * 0.5)
            speed_factor = max(0.0, min(1.0, speed_factor))

            target_dur = min_dur + (max_dur - min_dur) * speed_factor

            # Apply Chaos (Random variance)
            if chaos > 0:
                jitter = (random.random() - 0.5) * 2 * chaos * (max_dur - min_dur)
                target_dur += jitter

            target_dur = max(min_dur, min(max_dur, target_dur))

            # 2. Align to Beat (Precision)
            proposed_end = current_time + target_dur

            if beats and precision > 0:
                # Find nearest beat to proposed_end
                nearest_beat = min(beats, key=lambda x: abs(x - proposed_end))
                distance = abs(nearest_beat - proposed_end)

                # If close enough (based on precision), snap it
                # Precision 1.0 -> Snap if within 2.0s?
                # Precision 0.1 -> Snap only if very close
                snap_window = 2.0 * precision

                if distance < snap_window:
                    proposed_end = nearest_beat

            final_dur = proposed_end - current_time
            if final_dur < 0.5: # Hard limit, don't make 0s clips
                final_dur = 0.5
                proposed_end = current_time + final_dur

            cuts.append({
                "time": current_time,
                "duration": final_dur,
                "energy": local_energy
            })
            current_time = proposed_end

        return cuts

    def _render_segments(self, cut_list, video_sources, temp_dir, callback):
        processed = []
        total_cuts = len(cut_list)

        # We need to know duration of sources to avoid seeking past end
        source_durations = {}

        for i, cut in enumerate(cut_list):
            if self.cancel_flag: return []

            # Progress (20 -> 90)
            prog = 20 + int((i / total_cuts) * 70)
            if callback: callback(f"Rendering Clip {i+1}/{total_cuts}...", prog)

            # 1. Pick Source
            # Clip-Auswahl: random.choice als Fallback.
            # Wenn cut["clip_id"] gesetzt ist (SmartDirector-Output), sollte das
            # jeweilige source-File direkt verwendet werden (ADR-002 Backlog).
            src = random.choice(video_sources)

            # Get duration if unknown
            if src not in source_durations:
                source_durations[src] = self._get_video_duration(src)

            src_dur = source_durations.get(src, 100)

            # 2. Pick In-Point
            required_dur = cut["duration"]
            if src_dur <= required_dur:
                in_point = 0
            else:
                in_point = random.uniform(0, src_dur - required_dur)

            # 3. Render Segment
            out_name = temp_dir / f"seg_{i:04d}.mp4"
            # BUGFIX H3: only append a segment that actually encoded. A failed
            # segment must be skipped (with a logged reason), never fed as a
            # 0-byte file into the concat step.
            try:
                self._ffmpeg_extract(src, in_point, required_dur, out_name)
            except Exception as e:
                logger.error("Skipping segment %d (%s): %s", i, src, e)
                continue
            processed.append(out_name)

        return processed

    def _get_video_duration(self, path):
        try:
            cmd = [_get_ffprobe_path(), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            stdout = result.stdout.strip()
            if not stdout or result.returncode != 0:
                logger.debug(f"FFprobe returned no duration for {path}")
                return 60.0
            return float(stdout)
        except Exception as e:
            logger.debug(f"Could not get duration for {path}: {e}")
            return 60.0 # Fallback

    def _ffmpeg_extract(self, input_path, start, duration, output_path):
        """
        Extracts and standardizes a clip using AMD AMF hardware encoding.
        Fails explicitly if AMD AMF is unavailable.
        """
        # Get encoder config - preview mode for segment rendering (fast)
        encoder_config = get_preview_encoder()

        logger.debug(f"Using encoder: {encoder_config.description}")

        # Build FFmpeg command
        # Standardize: 1080p, 30fps, no audio (we use master track)
        cmd = [
            _get_ffmpeg_path(), "-y",
            *get_amf_device_args(),
            "-ss", str(start),
            "-i", str(input_path),
            "-t", str(duration),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30",
        ]

        # Add encoder-specific arguments
        cmd.extend(build_ffmpeg_encode_args(encoder_config))

        # No audio from clip
        cmd.extend(["-an", str(output_path)])

        # Run FFmpeg
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)

        # BUGFIX H3: the encode result was previously never checked, so a failed
        # segment (bad -ss past EOF, disk full, unsupported source) produced a
        # missing/0-byte file that was then appended to the concat list -> opaque
        # "concat failed" or a corrupt/short video, with the real error lost.
        # Fail loudly instead: the caller must not append an unverified segment.
        out = Path(output_path)
        if result.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            stderr_tail = (result.stderr or b"").decode("utf-8", "replace")[-1200:]
            raise RuntimeError(
                f"FFmpeg segment encode failed for {input_path} "
                f"(rc={result.returncode}, output_ok={out.exists() and out.stat().st_size > 0}). "
                f"stderr tail:\n{stderr_tail}"
            )

    def _concat_segments(self, segments, audio_path, output_path):
        """
        Concatenates segments and adds master audio.
        Uses high-quality encoding for final output.
        """
        if not segments:
            raise ValueError("No segments to concatenate")

        # Create concat file
        list_path = segments[0].parent / "list.txt"
        with open(list_path, "w", encoding="utf-8") as f:
            for seg in segments:
                # BUG-055 FIX: Nutze absolute Pfade
                safe_path = str(seg.absolute()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        # Get export encoder for final output
        encoder_config = get_export_encoder(
            codec=getattr(self, 'output_codec', 'h264'),
            quality=getattr(self, 'output_quality', 'balanced')
        )

        logger.info(f"Final encoding: {encoder_config.description}")

        # Concat with re-encoding for consistent output
        cmd = [
            _get_ffmpeg_path(), "-y",
            *get_amf_device_args(),
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-i", str(audio_path),
        ]

        # Add encoder arguments
        cmd.extend(build_ffmpeg_encode_args(encoder_config))

        # Audio and mapping
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v",
            "-map", "1:a",
            "-shortest",
            str(output_path)
        ])

        logger.info(f"Running Final Encode: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
            if result.returncode != 0:
                stderr_text = result.stderr.decode()[:500] if result.stderr else 'no stderr'
                logger.error(f"Final encode failed (code {result.returncode}): {stderr_text}")
                raise RuntimeError(f"FFmpeg concat failed with code {result.returncode}")
        finally:
            # Cleanup list.txt - verhindert File Handle Leak
            try:
                if list_path.exists():
                    list_path.unlink()
            except Exception:
                pass

    def generate_from_timeline(self, config: dict, timeline, callback=None):
        """Generate video from a SmartDirector Timeline.

        Uses the pre-computed timeline (with AI-selected clips, cut points,
        and transition types) instead of the basic random-selection logic.

        Args:
            config: Generation config dict (paths, encoder settings).
            timeline: SmartDirector Timeline object.
            callback: Progress callback(step_str, percent_int).

        Returns:
            dict with output_path on success, or cancelled flag.
        """
        master_audio = config["master_audio"]
        output_path = config["output_path"]

        if self.cancel_flag:
            return {"output_path": output_path, "cancelled": True}

        temp_base = Path(config.get("temp_dir", "./data/temp_render"))
        temp_dir = temp_base / f"render_{uuid.uuid4().hex[:8]}"

        # Encoding settings
        if config.get("use_hardware_encoding", True) is False:
            raise ValueError("Software encoding is prohibited; AMD AMF is required")
        self.use_hardware = True
        self.output_codec = config.get("output_codec", "h264")
        self.output_quality = config.get("output_quality", "balanced")

        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Render each timeline clip as a segment
            if callback:
                callback("Rendering Segments...", 35)

            processed_segments = []
            total_clips = len(timeline.clips)

            for i, tclip in enumerate(timeline.clips):
                if self.cancel_flag:
                    return {"output_path": output_path, "cancelled": True}

                prog = 35 + int((i / max(total_clips, 1)) * 55)
                if callback:
                    callback(f"Rendering Clip {i+1}/{total_clips}...", prog)

                out_name = temp_dir / f"seg_{i:04d}.mp4"

                # Use source_start/source_end from SmartDirector timeline
                segment_duration = tclip.source_end - tclip.source_start
                # BUGFIX H3: skip a segment that fails to encode instead of
                # appending a missing/0-byte file to the concat list.
                try:
                    self._ffmpeg_extract(
                        tclip.source_path,
                        tclip.source_start,
                        segment_duration,
                        out_name,
                    )
                except Exception as e:
                    logger.error("Skipping timeline clip %d (%s): %s", i, tclip.source_path, e)
                    continue
                processed_segments.append(out_name)

            if self.cancel_flag:
                return {"output_path": output_path, "cancelled": True}

            # Concatenate all segments with master audio
            if callback:
                callback("Finalizing...", 92)
            self._concat_segments(processed_segments, master_audio, output_path)

            if callback:
                callback("Done!", 100)

            return {"output_path": output_path}

        except Exception as e:
            logger.error(f"Timeline generation failed: {e}")
            raise
        finally:
            if temp_dir.exists() and not config.get("keep_temp", False):
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.debug(f"Could not clean temp dir: {e}")

    def reset_cancel(self):
        """Prepare this reusable generator for a newly accepted job."""
        self.cancel_flag = False

    def cancel(self):
        self.cancel_flag = True
