"""Focused launcher/runtime contracts for OBJ-76 T004-T005."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort

from pb_studio.core.directml_adapter import (
    enumerate_dxgi_adapters,
    get_directml_adapter,
    get_directml_provider,
)
from pb_studio.core.system_monitor import SystemMonitor


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / ".agents" / "skills" / "run-pb-studio" / "driver.ps1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def test_agent_driver_uses_canonical_runtime_and_owner_scripts():
    source = DRIVER.read_text(encoding="utf-8-sig")

    assert "runtime_contract.ps1" in source
    assert "Get-PBStudioRuntimeContract" in source
    assert "-RequirePython" in source
    assert "-RequireFFmpeg" in source
    assert "-ApplyEnvironment" in source
    assert "owner_capability.ps1" in source
    assert "RandomNumberGenerator" not in source
    assert 'Log "Owner capability' not in source


def test_agent_driver_checks_locked_runtime_and_adapter_identity():
    source = DRIVER.read_text(encoding="utf-8-sig")

    assert "1.26.4" in source
    assert "DmlExecutionProvider" in source
    assert "adapter_index" in source
    assert "adapter_luid" in source
    assert "adapter_name" in source
    assert "adapter_vendor_id" in source
    assert "adapter_discrete" in source
    assert "adapter_high_performance" in source
    assert "max_amd_vram_bytes" in source
    assert "provider_device_id" in source
    assert "monitor_selected_luid" in source
    assert "monitor_adapter_luid" in source
    assert "monitoring_status" in source
    assert "monitoring_error" in source
    assert "$BackendStartupDeadlineSeconds = 90" in source
    assert "directml-model-assets.json" not in source
    assert "LhmManifestSha256" in source
    assert "LhmLibrarySha256" in source
    assert {"h264_amf", "hevc_amf", "av1_amf"} <= set(source.split("'"))


def test_locked_python_numpy_directml_and_amf_are_available():
    assert sys.version_info[:2] == (3, 11)
    assert np.__version__ == "1.26.4"
    assert "DmlExecutionProvider" in ort.get_available_providers()

    manifest = json.loads(
        (ROOT / "config" / "ffmpeg-runtime.json").read_text(encoding="utf-8")
    )
    ffmpeg = ROOT / manifest["stable_bin"] / "ffmpeg.exe"
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = result.stdout + result.stderr
    for encoder in ("h264_amf", "hevc_amf", "av1_amf"):
        assert encoder in output


def test_lhm_runtime_manifest_binds_the_active_files_by_sha256():
    contract = json.loads(
        (ROOT / "config" / "lhm-runtime.json").read_text(encoding="utf-8")
    )
    active = contract["active"]
    bundle = ROOT / active["bundle_dir"]

    assert contract["schema_version"] == 1
    assert _sha256(bundle / active["manifest"]) == active["manifest_sha256"]
    assert _sha256(bundle / active["library"]) == active["library_sha256"]


def test_live_directml_selection_and_lhm_identity_use_current_dxgi_truth(monkeypatch):
    contract = json.loads(
        (ROOT / "config" / "lhm-runtime.json").read_text(encoding="utf-8")
    )
    active = contract["active"]
    monkeypatch.setenv("PBSTUDIO_LHM_MANIFEST_SHA256", active["manifest_sha256"])
    monkeypatch.setenv("PBSTUDIO_LHM_SHA256", active["library_sha256"])

    adapter = get_directml_adapter(refresh=True)
    amd_hardware = [
        candidate
        for candidate in enumerate_dxgi_adapters()
        if candidate.vendor_id == 0x1002 and not candidate.is_software
    ]
    assert amd_hardware
    assert adapter.vendor_id == 0x1002
    assert adapter.is_discrete
    assert adapter.high_performance_preferred
    assert adapter.dedicated_vram_bytes == max(
        candidate.dedicated_vram_bytes for candidate in amd_hardware
    )
    assert get_directml_provider() == (
        "DmlExecutionProvider",
        {"device_id": adapter.device_id},
    )

    previous = SystemMonitor._instance
    monitor = None
    try:
        SystemMonitor._instance = None
        monitor = SystemMonitor()
        stats = monitor.get_stats(force_refresh=True)
        assert monitor.selected_adapter_luid == adapter.luid
        assert stats["adapter_luid"] == adapter.luid
        if stats["monitoring_status"] == "ready":
            assert stats["gpu_name"] == adapter.name
            assert stats["monitoring_error"] is None
        else:
            assert stats["monitoring_status"] == "degraded"
            assert stats["monitoring_error"]
    finally:
        if monitor is not None:
            monitor.close()
        SystemMonitor._instance = previous
