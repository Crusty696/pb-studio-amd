"""Reproducible T363 DirectML hardware-load probe.

Each workload runs in a dedicated process so Windows GPU Engine and GPU
Process Memory counters can be attributed to the emitted PID.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import numpy as np

from pb_studio.core.directml_adapter import (
    get_directml_adapter,
    get_directml_provider,
)


MODELS_DIR = Path("models")
PROJECT_DIR = Path(
    os.environ.get(
        "PBSTUDIO_T363_PROJECT_DIR",
        r"C:\Users\david\Documents\PBStudio\New_test_juli",
    )
)
PROJECT_DB = Path("data") / "pb_studio.db"
ASSETS = (
    "raft_small.onnx",
    "siglip_vision.onnx",
    "UVR-MDX-NET-Inst_HQ_3.onnx",
    "moondream_encoder.onnx",
    "moondream_decoder.onnx",
    "moondream.onnx",
    "clap_combined.onnx",
    "clap_audio_encoder.onnx",
    "clap_text_encoder.onnx",
)


def _base(workload: str) -> dict[str, Any]:
    adapter = get_directml_adapter(refresh=True)
    return {
        "workload": workload,
        "pid": os.getpid(),
        "adapter": asdict(adapter),
        "provider": get_directml_provider(),
    }


def _emit(result: dict[str, Any]) -> None:
    print("T363_RESULT=" + json.dumps(result, sort_keys=True, default=str), flush=True)


def _emit_ready(result: dict[str, Any]) -> None:
    print("T363_READY=" + json.dumps(result, sort_keys=True, default=str), flush=True)


def _run_loop(action: Callable[[], Any], seconds: float) -> int:
    deadline = time.monotonic() + seconds
    iterations = 0
    while time.monotonic() < deadline:
        value = action()
        if value is None:
            raise RuntimeError("workload returned no inference result")
        iterations += 1
    return iterations


def _project_media() -> tuple[Path, Path]:
    project_data = json.loads((PROJECT_DIR / "project.json").read_text("utf-8"))
    project_id = int(project_data["db_project_id"])
    with sqlite3.connect(PROJECT_DB) as connection:
        paths = [
            Path(row[0])
            for row in connection.execute(
                "SELECT file_path FROM media WHERE project_id = ? ORDER BY id",
                (project_id,),
            )
        ]
    audio_extensions = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
    video_extensions = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
    audio_path = next(
        path
        for path in paths
        if path.suffix.lower() in audio_extensions and path.is_file()
    )
    video_path = next(
        path
        for path in paths
        if path.suffix.lower() in video_extensions and path.is_file()
    )
    return audio_path, video_path


def _real_video_frames() -> tuple[Path, np.ndarray, np.ndarray]:
    import cv2

    _, video_path = _project_media()
    capture = cv2.VideoCapture(str(video_path))
    try:
        ok_a, frame_a = capture.read()
        capture.set(cv2.CAP_PROP_POS_MSEC, 1000.0)
        ok_b, frame_b = capture.read()
    finally:
        capture.release()
    if not ok_a or not ok_b or frame_a is None or frame_b is None:
        raise RuntimeError(f"Could not decode real project video: {video_path}")
    return video_path, frame_a, frame_b


def probe_inventory(_: float) -> int:
    result = _base("inventory")
    result["assets"] = {
        name: {
            "exists": (MODELS_DIR / name).is_file(),
            "bytes": (MODELS_DIR / name).stat().st_size
            if (MODELS_DIR / name).is_file()
            else 0,
        }
        for name in ASSETS
    }
    _emit(result)
    return 0


def probe_raft(seconds: float) -> int:
    from pb_studio.video.raft import MotionAnalyzer

    result = _base("raft")
    analyzer = MotionAnalyzer(lazy_load=False)
    try:
        result.update(
            ready=analyzer.is_ready,
            active_provider=analyzer.active_provider,
        )
        if not analyzer.is_ready:
            result["error"] = "RAFT DirectML session initialization failed"
            _emit(result)
            return 2
        _emit_ready(result)
        video_path, frame_a, frame_b = _real_video_frames()
        result["source_media"] = str(video_path)
        result["iterations"] = _run_loop(
            lambda: analyzer.calculate_flow(frame_a, frame_b),
            seconds,
        )
        _emit(result)
        return 0
    finally:
        analyzer.unload()


def probe_siglip(seconds: float) -> int:
    from PIL import Image

    from pb_studio.ai.siglip_wrapper import SigLIPWrapper

    result = _base("siglip")
    wrapper = SigLIPWrapper(lazy_load=False)
    try:
        result.update(
            ready=wrapper.is_ready,
            active_provider=wrapper.active_provider,
        )
        if not wrapper.is_ready:
            result["error"] = "SigLIP DirectML session initialization failed"
            _emit(result)
            return 2
        _emit_ready(result)
        import cv2

        video_path, frame, _ = _real_video_frames()
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        result["source_media"] = str(video_path)
        result["iterations"] = _run_loop(
            lambda: wrapper.encode_image(image),
            seconds,
        )
        _emit(result)
        return 0
    finally:
        wrapper.unload()


def probe_moondream(seconds: float) -> int:
    from PIL import Image

    from pb_studio.video.moondream import MoondreamAnalyzer

    result = _base("moondream")
    analyzer = MoondreamAnalyzer(lazy_load=False)
    try:
        result.update(
            ready=analyzer.is_vision_ready,
            caption_ready=analyzer.is_ready,
            active_provider=analyzer.active_provider,
        )
        if not analyzer.is_vision_ready:
            result["error"] = "Moondream DirectML ONNX assets/session unavailable"
            _emit(result)
            return 2
        _emit_ready(result)
        import cv2

        video_path, frame, _ = _real_video_frames()
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        result["source_media"] = str(video_path)
        result["iterations"] = _run_loop(
            lambda: analyzer.encode_image(image),
            seconds,
        )
        _emit(result)
        return 0
    finally:
        analyzer.unload()


def probe_clap(seconds: float) -> int:
    from pb_studio.ai.clap_wrapper import CLAPAnalyzer

    result = _base("clap")
    analyzer = CLAPAnalyzer(lazy_load=False)
    try:
        result.update(
            ready=analyzer.is_ready,
            semantic_ready=analyzer.is_semantic_ready,
            active_provider=analyzer.active_provider,
            unavailable_reason=analyzer.unavailable_reason,
        )
        if not analyzer.is_ready:
            result["error"] = "CLAP DirectML ONNX assets/session unavailable"
            _emit(result)
            return 2
        audio_session = analyzer.combined_session or analyzer.audio_encoder_session
        text_session = analyzer.text_encoder_session
        if audio_session is None or text_session is None:
            result["error"] = "CLAP has no runnable audio/text sessions"
            _emit(result)
            return 2
        audio_path, _ = _project_media()
        audio_tensor = analyzer.preprocess_audio(analyzer.load_audio(audio_path))
        tokens = analyzer._processor(
            text=["psytrance"],
            padding="max_length",
            truncation=True,
            max_length=77,
            return_tensors="np",
        )
        text_inputs = {
            meta.name: np.asarray(tokens[meta.name], dtype=np.int64)
            for meta in text_session.get_inputs()
        }
        result["source_media"] = str(audio_path)
        result["audio_input_shape"] = list(audio_tensor.shape)
        _emit_ready(result)

        def run_clap() -> Any:
            audio_output = audio_session.run(
                None,
                {audio_session.get_inputs()[0].name: audio_tensor},
            )
            text_output = text_session.run(None, text_inputs)
            return audio_output, text_output

        result["iterations"] = _run_loop(
            run_clap,
            seconds,
        )
        _emit(result)
        return 0
    finally:
        analyzer.unload()


def probe_audio(seconds: float) -> int:
    from pb_studio.core.model_loader import ModelLoader

    result = _base("audio")
    loader = ModelLoader()
    session = loader.load_model("mdx_net_inst", force=True)
    try:
        if session is None:
            result.update(
                ready=False,
                error="Audio separator DirectML session initialization failed",
            )
            _emit(result)
            return 2
        result.update(
            ready=True,
            active_providers=session.get_providers(),
        )
        _emit_ready(result)
        input_meta = session.get_inputs()[0]
        shape = [
            dimension if isinstance(dimension, int) and dimension > 0 else 1
            for dimension in input_meta.shape
        ]
        tensor = np.zeros(shape, dtype=np.float32)
        result["input_shape"] = shape
        result["iterations"] = _run_loop(
            lambda: session.run(None, {input_meta.name: tensor}),
            seconds,
        )
        _emit(result)
        return 0
    finally:
        loader.unload_model("mdx_net_inst")


PROBES: dict[str, Callable[[float], int]] = {
    "inventory": probe_inventory,
    "raft": probe_raft,
    "siglip": probe_siglip,
    "moondream": probe_moondream,
    "clap": probe_clap,
    "audio": probe_audio,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workload", choices=sorted(PROBES))
    parser.add_argument("--seconds", type=float, default=20.0)
    args = parser.parse_args()
    try:
        return PROBES[args.workload](max(0.1, args.seconds))
    except Exception as exc:
        result = _base(args.workload)
        result.update(
            ready=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        _emit(result)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
