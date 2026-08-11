"""Bounded LM Studio VLM load/inference receipts for OBJ-76."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOAD_TIMEOUT_SECONDS = 180
INFERENCE_TIMEOUT_SECONDS = 180
POLL_SECONDS = 1.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="pb-lms-cli-") as directory:
        stdout_path = Path(directory) / "stdout.log"
        stderr_path = Path(directory) / "stderr.log"
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                creationflags=CREATE_NO_WINDOW,
            )
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=CREATE_NO_WINDOW,
                )
                process.wait(timeout=10)
                raise
        return subprocess.CompletedProcess(
            command,
            return_code,
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )


def _lms_json(lms: str, *arguments: str) -> Any:
    result = _run([lms, *arguments])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def _loaded_models(lms: str) -> list[dict[str, Any]]:
    return list(_lms_json(lms, "ps", "--json"))


def _wait_loaded(lms: str, identifier: str, expected: bool) -> dict[str, Any] | None:
    deadline = time.monotonic() + LOAD_TIMEOUT_SECONDS
    seen = False
    while time.monotonic() < deadline:
        match = next(
            (
                item
                for item in _loaded_models(lms)
                if item.get("identifier") == identifier
            ),
            None,
        )
        seen = seen or match is not None
        ready = match is not None and match.get("status") == "idle"
        if expected and ready:
            return match
        if expected and seen and match is None:
            raise RuntimeError(f"LM Studio engine disappeared while loading {identifier}")
        if not expected and match is None:
            return None
        time.sleep(POLL_SECONDS)
    state = "load" if expected else "unload"
    raise TimeoutError(f"LM Studio did not {state} {identifier} within deadline")


def _unload(lms: str, identifier: str) -> None:
    result = _run([lms, "unload", identifier], timeout=LOAD_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    _wait_loaded(lms, identifier, False)


def _load(
    lms: str,
    model_key: str,
    identifier: str,
    context_length: int,
    parallel: int = 1,
) -> dict[str, Any]:
    result = _run(
        [
            lms,
            "load",
            model_key,
            "--identifier",
            identifier,
            "--gpu",
            "max",
            "--context-length",
            str(context_length),
            "--parallel",
            str(parallel),
            "--yes",
        ],
        timeout=LOAD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    loaded = _wait_loaded(lms, identifier, True)
    return {
        "cli_exit_code": result.returncode,
        "state": {
            "identifier": loaded.get("identifier"),
            "model_key": loaded.get("modelKey"),
            "status": loaded.get("status"),
            "context_length": loaded.get("contextLength"),
            "size_bytes": loaded.get("sizeBytes"),
            "vision": loaded.get("vision"),
        },
    }


def _vision_body(identifier: str, image_bytes: bytes) -> bytes:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    value = {
        "model": identifier,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Return exactly three short English visual tags separated by commas.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 64,
        "stream": True,
    }
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _stream_inference(body: bytes) -> dict[str, Any]:
    request = urllib.request.Request(
        "http://127.0.0.1:1234/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    first_data: float | None = None
    chunks = 0
    response_id = None
    stream_error = None
    done = False
    try:
        with urllib.request.urlopen(
            request,
            timeout=INFERENCE_TIMEOUT_SECONDS,
        ) as response:
            status = response.status
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    done = True
                    break
                if first_data is None:
                    first_data = time.monotonic()
                chunks += 1
                try:
                    chunk = json.loads(payload)
                    response_id = response_id or chunk.get("id")
                    if chunk.get("error"):
                        stream_error = json.dumps(
                            chunk["error"],
                            separators=(",", ":"),
                        )
                except json.JSONDecodeError:
                    continue
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"HTTP {exc.code}: {body_text}") from exc
    elapsed = time.monotonic() - started
    if stream_error is not None:
        raise RuntimeError(f"LM Studio SSE error: {stream_error[:1000]}")
    if not done:
        raise RuntimeError(
            f"LM Studio SSE ended without [DONE] after {chunks} data chunk(s)"
        )
    if chunks == 0 or response_id is None:
        raise RuntimeError("LM Studio SSE returned no attributable response")
    return {
        "http_status": status,
        "chunks": chunks,
        "done": done,
        "response_id": response_id,
        "ttft_seconds": None if first_data is None else first_data - started,
        "elapsed_seconds": elapsed,
    }


def _safe_error(exc: Exception) -> str:
    message = str(exc).replace("\r", " ").replace("\n", " ")[:1000]
    return re.sub(r"(?i)(?:[A-Z]:\\[^\s\"']+)", "<PRIVATE_PATH>", message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--raw-server-log", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--configured-model", required=True)
    parser.add_argument("--control-model", required=True)
    args = parser.parse_args()

    raw_log_path = args.raw_server_log.resolve()
    summary_path = args.summary.resolve()
    if raw_log_path == summary_path:
        raise ValueError("Raw server log and summary must use different paths")
    for output_path in (raw_log_path, summary_path):
        if output_path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing diagnostic receipt: {output_path}"
            )

    lms = shutil.which("lms")
    if not lms:
        raise RuntimeError("lms CLI is unavailable")
    image_bytes = args.image.read_bytes()
    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    started_at = _utc_now()
    initial = _loaded_models(lms)
    restored: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    log_process: subprocess.Popen[bytes] | None = None
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with raw_log_path.open("xb") as raw_log:
        try:
            log_process = subprocess.Popen(
                [lms, "log", "stream", "--source", "server", "--json"],
                stdout=raw_log,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
            for item in initial:
                identifier = str(item.get("identifier") or "")
                if identifier:
                    _unload(lms, identifier)

            targets = (
                (args.configured_model, "obj76-configured-vlm", 3),
                (args.control_model, "obj76-control-vlm", 1),
            )
            for model_key, identifier, attempts in targets:
                target_started = time.monotonic()
                load_receipt = None
                body = _vision_body(identifier, image_bytes)
                calls = []
                error = None
                try:
                    load_receipt = _load(lms, model_key, identifier, 8192)
                    for number in range(1, attempts + 1):
                        receipt = _stream_inference(body)
                        receipt["attempt"] = number
                        calls.append(receipt)
                except Exception as exc:
                    error = {
                        "type": type(exc).__name__,
                        "message": _safe_error(exc),
                    }
                finally:
                    try:
                        _unload(lms, identifier)
                    except Exception as exc:
                        cleanup_error = {
                            "type": type(exc).__name__,
                            "message": _safe_error(exc),
                        }
                        if error is None:
                            error = cleanup_error
                        else:
                            error["cleanup"] = cleanup_error
                results.append(
                    {
                        "model_key": model_key,
                        "identifier": identifier,
                        "request_sha256": hashlib.sha256(body).hexdigest(),
                        "load": load_receipt,
                        "calls": calls,
                        "error": error,
                        "total_elapsed_seconds": time.monotonic() - target_started,
                    }
                )
        finally:
            for item in initial:
                identifier = str(item.get("identifier") or "")
                model_key = str(item.get("modelKey") or "")
                if not identifier or not model_key:
                    continue
                try:
                    restored.append(
                        _load(
                            lms,
                            model_key,
                            identifier,
                            int(item.get("contextLength") or 8192),
                            int(item.get("parallel") or 1),
                        )["state"]
                    )
                except Exception as exc:
                    restored.append(
                        {
                            "identifier": identifier,
                            "model_key": model_key,
                            "restore_error": _safe_error(exc),
                        }
                    )
            if log_process is not None:
                subprocess.run(
                    [
                        "taskkill.exe",
                        "/PID",
                        str(log_process.pid),
                        "/T",
                        "/F",
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=CREATE_NO_WINDOW,
                )

    summary = {
        "schema_version": 1,
        "started_at": started_at,
        "image_sha256": image_sha256,
        "configured_model": args.configured_model,
        "control_model": args.control_model,
        "preexisting": [
            {
                "identifier": item.get("identifier"),
                "model_key": item.get("modelKey"),
                "context_length": item.get("contextLength"),
            }
            for item in initial
        ],
        "results": results,
        "restored": restored,
        "finished_at": _utc_now(),
        "raw_server_log": raw_log_path.name,
    }
    with summary_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
