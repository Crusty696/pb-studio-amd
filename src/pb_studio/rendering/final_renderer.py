"""
BatchRenderer - Finaler Export mit Batch-Chunking-Strategie (AMD Version).

Löst das Windows-Zeichenlimit-Problem (8191 Zeichen) durch
Zerlegung der Timeline in 30-Clip-Chunks.

Kein ffmpeg-python — nutzt subprocess direkt.
Kein CUDA/torch.cuda — AMD DirectML Version.
AMF Hardware-Encoding statt NVENC.
"""

import gc
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RenderProgress:
    """Fortschritts-Information für das Rendering."""
    current_chunk: int
    total_chunks: int
    current_phase: str
    progress_percent: float


class BatchRenderer:
    """
    Batch-basierter Renderer für lange Projekte (AMD Version).

    Strategie:
    - Timeline in Chunks von 30 Clips
    - Jeder Chunk wird einzeln gerendert (Windows CMD-Limit-sicher)
    - Chunks via Concat-Demuxer zusammengefügt
    - Master-Audio am Ende gemerged
    """

    CHUNK_SIZE = 30
    OUTPUT_WIDTH = 1920
    OUTPUT_HEIGHT = 1080

    def __init__(self, temp_dir: str | Path | None = None, fps: float = 30.0) -> None:
        self.temp_dir = Path(temp_dir) if temp_dir else Path("data/temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._output_fps: float = float(fps)
        self._progress_callback: Any = None
        self._encoder = self._detect_encoder()

    def _detect_encoder(self) -> str:
        """Testet AMD AMF Encoder Verfügbarkeit."""
        for enc in ["hevc_amf", "h264_amf", "h264_mf", "libx264"]:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
                "-c:v", enc, "-f", "null", "-"
            ]
            try:
                r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                if r.returncode == 0:
                    logger.info(f"BatchRenderer Encoder: {enc}")
                    return enc
            except Exception:
                continue
        return "libx264"

    def set_progress_callback(self, callback: Any) -> None:
        self._progress_callback = callback

    def _report_progress(self, progress: RenderProgress) -> None:
        if self._progress_callback:
            self._progress_callback(progress)

    def render_project(
        self,
        timeline: list,
        output_path: str | Path,
        master_audio_path: str | Path | None = None,
    ) -> bool:
        """Rendert das komplette Projekt."""

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not timeline:
            logger.error("Timeline ist leer")
            return False

        logger.info(f"Starte Rendering: {len(timeline)} Clips")

        # Phase 1: Cleanup
        gc.collect()

        # Phase 2: Chunks aufteilen
        chunks = self._split_into_chunks(timeline)
        total_chunks = len(chunks)
        logger.info(f"Timeline: {total_chunks} Chunks à {self.CHUNK_SIZE} Clips")

        # Phase 3: Chunks einzeln rendern
        chunk_files: list[Path] = []
        for i, chunk in enumerate(chunks):
            self._report_progress(RenderProgress(
                current_chunk=i + 1, total_chunks=total_chunks,
                current_phase="Chunk Rendering",
                progress_percent=(i / total_chunks) * 70
            ))

            chunk_path = self.temp_dir / f"chunk_{i:04d}.mp4"
            success = self._render_chunk(chunk, chunk_path)

            if not success:
                logger.error(f"Chunk {i + 1} fehlgeschlagen")
                self._cleanup_temp_files(chunk_files)
                return False

            chunk_files.append(chunk_path)
            gc.collect()

        # Phase 4: Concat
        self._report_progress(RenderProgress(
            current_chunk=total_chunks, total_chunks=total_chunks,
            current_phase="Concatenation", progress_percent=75
        ))

        concat_output = self.temp_dir / "concat_output.mp4"
        if not self._concatenate_chunks(chunk_files, concat_output):
            logger.error("Chunk-Concatenation fehlgeschlagen")
            self._cleanup_temp_files(chunk_files)
            return False

        # Phase 5: Audio Merge
        if master_audio_path:
            self._report_progress(RenderProgress(
                current_chunk=total_chunks, total_chunks=total_chunks,
                current_phase="Audio Merge", progress_percent=90
            ))
            success = self._merge_audio(concat_output, Path(master_audio_path), output_path)
        else:
            shutil.move(str(concat_output), str(output_path))
            success = True

        # Cleanup
        self._cleanup_temp_files(chunk_files)
        if concat_output.exists():
            concat_output.unlink()

        self._report_progress(RenderProgress(
            current_chunk=total_chunks, total_chunks=total_chunks,
            current_phase="Fertig", progress_percent=100
        ))

        if success:
            logger.info(f"Export erfolgreich: {output_path}")
        return success

    def _split_into_chunks(self, timeline: list) -> list[list]:
        return [timeline[i:i + self.CHUNK_SIZE] for i in range(0, len(timeline), self.CHUNK_SIZE)]

    def _render_chunk(self, chunk: list, output_path: Path) -> bool:
        """Rendert einen einzelnen Chunk via subprocess."""
        try:
            # Concat-File für den Chunk erstellen (eindeutiger Name verhindert Race Conditions)
            chunk_suffix = output_path.stem  # z.B. "chunk_0001"
            concat_file = self.temp_dir / f"chunk_concat_{chunk_suffix}_{int(time.time()*1000)}.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for entry in chunk:
                    vpath = entry.video_path if hasattr(entry, "video_path") else entry.get("video_path", "")
                    start = entry.start_time if hasattr(entry, "start_time") else entry.get("start_time", 0)
                    dur = entry.duration if hasattr(entry, "duration") else entry.get("duration", 2.0)

                    # BUG-069 FIX: Correct FFmpeg concat escaping
                    safe_path = str(Path(vpath).absolute()).replace("\\", "/")
                    p_escaped = safe_path.replace("'", "'\\''")
                    f.write(f"file '{p_escaped}'\n")
                    f.write(f"inpoint {start:.3f}\n")
                    f.write(f"outpoint {start + dur:.3f}\n")

            vf = (
                f"scale={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}"
                f":force_original_aspect_ratio=decrease,"
                f"pad={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
                f"fps={self._output_fps:.3f}"
            )

            # Encoder-Args
            if self._encoder == "hevc_amf":
                enc_args = ["-c:v", "hevc_amf", "-quality", "balanced", "-b:v", "12M"]
            elif self._encoder == "h264_amf":
                enc_args = ["-c:v", "h264_amf", "-quality", "balanced", "-b:v", "12M"]
            elif self._encoder == "h264_mf":
                enc_args = ["-c:v", "h264_mf", "-b:v", "10M"]
            else:
                enc_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-vf", vf,
                *enc_args,
                "-pix_fmt", "yuv420p",
                "-an",
                str(output_path)
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=3600
            )

            concat_file.unlink(missing_ok=True)
            ok = result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
            if not ok:
                # R14/CRITICAL-003: Ungültige (0-Byte) Output-Datei aufräumen, damit
                # kein beschädigter Chunk in der Concat-Phase verwendet wird.
                if result.returncode != 0 and result.stderr:
                    logger.error(f"FFmpeg Chunk stderr: {result.stderr[-500:]}")
                output_path.unlink(missing_ok=True)
            return ok

        except Exception as e:
            logger.error(f"Chunk-Rendering Fehler: {e}")
            output_path.unlink(missing_ok=True)
            return False

    def _concatenate_chunks(self, chunk_files: list[Path], output_path: Path) -> bool:
        try:
            concat_list = self.temp_dir / "final_concat_list.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for chunk_file in chunk_files:
                    safe_path = str(chunk_file.absolute()).replace("\\", "/")
                    f.write(f'file "{safe_path}"\n')

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=3600
            )
            concat_list.unlink(missing_ok=True)
            ok = result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
            if not ok:
                # R14/CRITICAL-003: Ungültige concat-Ausgabe löschen.
                if result.returncode != 0 and result.stderr:
                    logger.error(f"FFmpeg Concat stderr: {result.stderr[-500:]}")
                output_path.unlink(missing_ok=True)
            return ok

        except Exception as e:
            logger.error(f"Concatenation Fehler: {e}")
            output_path.unlink(missing_ok=True)
            return False

    def _merge_audio(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0",
                str(output_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=3600
            )
            ok = result.returncode == 0 and output_path.exists()
            if not ok and result.returncode != 0 and result.stderr:
                logger.error(f"FFmpeg Audio-Merge stderr: {result.stderr[-500:]}")
            return ok
        except Exception as e:
            logger.error(f"Audio-Merge Fehler: {e}")
            return False

    def _cleanup_temp_files(self, files: list[Path]) -> None:
        for file in files:
            try:
                if file.exists():
                    file.unlink()
            except Exception:
                pass

    def cleanup_temp_dir(self) -> None:
        try:
            for pattern in ["chunk_*.mp4", "concat_*.mp4", "*.txt"]:
                for file in self.temp_dir.glob(pattern):
                    file.unlink()
        except Exception as e:
            logger.warning(f"Cleanup-Fehler: {e}")

    def get_chunk_count(self, timeline: list) -> int:
        if not timeline:
            return 0
        return (len(timeline) + self.CHUNK_SIZE - 1) // self.CHUNK_SIZE
