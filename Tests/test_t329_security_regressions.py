"""T329 security regressions. Implemented before the T332 execution gate."""

from __future__ import annotations

import inspect
import importlib.util
from pathlib import Path
import sys

import pytest

from backend.media_path_policy import (
    MediaPathPolicyError,
    canonical_local_media_file,
    validate_media_catalog,
    validate_timeline_media_paths,
)
from pb_studio.core import system_monitor


@pytest.mark.parametrize(
    "untrusted_path",
    [
        r"\\server\share\clip.mp4",
        r"\\?\C:\outside\clip.mp4",
        r"\\.\PIPE\pb-studio",
        "https://example.invalid/clip.mp4",
        r"C:\outside\clip.mp4:stream",
    ],
)
def test_media_policy_rejects_external_device_and_stream_paths(untrusted_path):
    with pytest.raises(MediaPathPolicyError):
        canonical_local_media_file(untrusted_path)


def test_timeline_path_is_rebound_from_registered_clip_id(tmp_path: Path):
    clip = tmp_path / "registered.mp4"
    clip.write_bytes(b"local")
    timeline = [{
        "clip_id": "clip_7",
        "start_time": 0.0,
        "end_time": 1.0,
        "metadata": {"file_path": r"\\attacker\share\clip.mp4"},
    }]

    validated = validate_timeline_media_paths(
        timeline,
        {7: {"path": str(clip)}},
    )

    assert validated[0]["metadata"]["file_path"] == str(clip.resolve())
    assert timeline[0]["metadata"]["file_path"] == r"\\attacker\share\clip.mp4"


def test_timeline_rejects_unknown_registered_clip(tmp_path: Path):
    with pytest.raises(MediaPathPolicyError):
        validate_timeline_media_paths(
            [{
                "clip_id": "clip_99",
                "start_time": 0.0,
                "end_time": 1.0,
                "metadata": {"file_path": str(tmp_path / "outside.mp4")},
            }],
            {},
        )


def test_restored_catalog_rejects_network_but_keeps_missing_local_reference(
    tmp_path: Path,
):
    missing_local = tmp_path / "offline.mp4"
    validated = validate_media_catalog(
        {1: {"path": str(missing_local)}},
        label="Video-Katalog",
    )
    assert validated[1]["path"] == str(missing_local.absolute())

    with pytest.raises(MediaPathPolicyError):
        validate_media_catalog(
            {1: {"path": r"\\attacker\share\clip.mp4"}},
            label="Video-Katalog",
        )


def test_lhm_hash_gate_precedes_dotnet_load():
    verifier = inspect.getsource(system_monitor._load_verified_lhm_bundle)
    loader = inspect.getsource(system_monitor.SystemMonitor._initialize_lhm)
    assert "PBSTUDIO_LHM_MANIFEST_SHA256" in verifier
    assert "PBSTUDIO_LHM_SHA256" in verifier
    assert "hmac.compare_digest" in verifier
    assert "app_domain.AssemblyResolve += resolve_verified_assembly" in loader
    resolver_registration = loader.index("AssemblyResolve +=")
    assert loader.find("Assembly.Load", resolver_registration) > resolver_registration
    assert "Assembly.Load(Array[Byte](assembly_bytes))" in loader
    assert "if key not in verified_assemblies" in loader
    assert "clr.AddReference" not in loader


def test_setup_has_no_unverified_installer_fallbacks():
    root = Path(__file__).resolve().parents[1]
    setup = (root / "setup_pb_studio.ps1").read_text(encoding="utf-8")
    wrapper = (root / "setup.bat").read_text(encoding="utf-8")
    forbidden = (
        "aka.ms/vs/17/release",
        "python.org/ftp",
        "dot.net/v1/dotnet-install.ps1",
        "LibreHardwareMonitor/releases",
        "MinGit-2.45.1-64-bit.zip",
    )
    assert all(value not in setup for value in forbidden)
    assert "-Command" not in "\n".join(
        line for line in wrapper.splitlines() if "%*" in line and not line.startswith("REM")
    )


def test_design_system_rejects_project_and_page_traversal():
    root = Path(__file__).resolve().parents[1]
    scripts_dir = root / ".shared" / "ui-ux-pro-max" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "t329_design_system",
            scripts_dir / "design_system.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts_dir))

    for label in ("../escape", r"..\escape", "page/name", r"page\name"):
        with pytest.raises(ValueError):
            module.slugify_label(label, "label")
