"""Reproducible T363 DirectML hardware-load probe.

Each workload runs in a dedicated process so Windows GPU Engine and GPU
Process Memory counters can be attributed to the emitted PID.
"""

from __future__ import annotations

import argparse
import json
import os
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
        frame_a = np.zeros((384, 512, 3), dtype=np.uint8)
        frame_b = np.full((384, 512, 3), 127, dtype=np.uint8)
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
        image = Image.fromarray(
            np.full((384, 384, 3), 127, dtype=np.uint8),
            mode="RGB",
        )
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
            ready=analyzer.is_ready,
            active_provider=analyzer.active_provider,
        )
        if not analyzer.is_ready:
            result["error"] = "Moondream DirectML ONNX assets/session unavailable"
            _emit(result)
            return 2
        _emit_ready(result)
        image = Image.fromarray(
            np.full((384, 384, 3), 127, dtype=np.uint8),
            mode="RGB",
        )
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
        session = analyzer.combined_session or analyzer.audio_encoder_session
        if session is None:
            result["error"] = "CLAP has no runnable audio session"
            _emit(result)
            return 2
        _emit_ready(result)
        input_meta = session.get_inputs()[0]
        shape = [
            dimension if isinstance(dimension, int) and dimension > 0 else 1
            for dimension in input_meta.shape
        ]
        tensor = np.zeros(shape, dtype=np.float32)
        result["iterations"] = _run_loop(
            lambda: session.run(None, {input_meta.name: tensor}),
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
