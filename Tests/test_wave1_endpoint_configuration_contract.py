from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

import pb_studio.runtime_contract as runtime_contract
from pb_studio.runtime_contract import validate_backend_url


ROOT = Path(__file__).resolve().parents[1]
APPSETTINGS = ROOT / "appsettings.json"

RUNTIME_ENDPOINT_SOURCES = (
    "PBStudio.UI/App.xaml.cs",
    "PBStudio.UI/Services/OwnerCapabilityRequestHandler.cs",
    "PBStudio.UI/Services/PythonBridgeService.cs",
    "PBStudio.UI/Services/SSEClient.cs",
    "PBStudio.UI/Views/SettingsView.xaml",
    "PBStudio.UI/run.ps1",
    "backend/config.py",
    "src/pb_studio/ai/tool_registry.py",
    "launch.ps1",
    "verify_release_smoke.ps1",
    "SSE-RECOVERY-TEST.bat",
    "setup_pb_studio.ps1",
    "LOW-VRAM-STRESS.bat",
    "scripts/diagnostics/verify_video_resume_live.ps1",
    "scripts/owned_runtime_process.ps1",
    "scripts/runtime_contract.ps1",
    "scripts/qa/check_stress.bat",
    "scripts/qa/stress_4h.bat",
    "scripts/qa/verify_model_manager.bat",
    "scripts/qa/verify_model_manager_to_file.bat",
)

ENDPOINT_LITERAL = re.compile(
    r"(?:https?://(?:127\.0\.0\.1|localhost):8765\b|\bPort\s*[=:]\s*8765\b|"
    r"\bport\s+8765\b|\bBackendPort\s*=\s*8765\b|"
    r"\bport\s*:\s*int\s*=\s*8765\b|\bport\s*!=\s*8765\b|"
    r"Online\s*\(Port\s+8765\))",
    re.IGNORECASE,
)


def _without_line_comments(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".cs":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
    if suffix == ".py":
        text = re.sub(r"(?:'''|\"\"\").*?(?:'''|\"\"\")", "", text, flags=re.DOTALL)
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    if suffix == ".ps1":
        text = re.sub(r"<#.*?#>", "", text, flags=re.DOTALL)
        return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    if suffix == ".bat":
        return "\n".join(
            line
            for line in text.splitlines()
            if not line.lstrip().lower().startswith(("rem ", "::"))
        )
    if suffix == ".xaml":
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text


def test_root_appsettings_is_the_single_loopback_endpoint_contract():
    assert APPSETTINGS.is_file(), "Root appsettings.json is missing"
    payload = json.loads(APPSETTINGS.read_text(encoding="utf-8-sig"))
    backend = payload.get("Backend")

    assert isinstance(backend, dict)
    assert set(backend) == {"Scheme", "Host", "Port"}
    assert backend["Scheme"] == "http"
    assert backend["Host"] in {"127.0.0.1", "localhost", "::1"}
    assert isinstance(backend["Port"], int) and 1 <= backend["Port"] <= 65535


def test_active_runtime_sources_have_no_hardcoded_default_endpoint():
    offenders: list[str] = []
    for relative in RUNTIME_ENDPOINT_SOURCES:
        path = ROOT / relative
        assert path.is_file(), f"Endpoint inventory source disappeared: {relative}"
        source = _without_line_comments(path, path.read_text(encoding="utf-8-sig"))
        if ENDPOINT_LITERAL.search(source):
            offenders.append(relative)

    assert offenders == [], (
        "Active endpoint sources must consume root appsettings.json; hardcoded "
        f"127.0.0.1/localhost:8765 remains in: {offenders}"
    )


def test_wpf_build_and_publish_copy_the_root_contract():
    project = (ROOT / "PBStudio.UI" / "PBStudio.UI.csproj").read_text(
        encoding="utf-8-sig"
    )
    assert 'Include="..\\appsettings.json" Link="appsettings.json"' in project
    assert "<CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>" in project
    assert "<CopyToPublishDirectory>PreserveNewest</CopyToPublishDirectory>" in project


def test_python_consumers_use_the_shared_backend_contract():
    runtime = (ROOT / "src" / "pb_studio" / "runtime_contract.py").read_text(
        encoding="utf-8-sig"
    )
    backend = (ROOT / "backend" / "config.py").read_text(encoding="utf-8-sig")
    tools = (ROOT / "src" / "pb_studio" / "ai" / "tool_registry.py").read_text(
        encoding="utf-8-sig"
    )
    assert "def backend_endpoint()" in runtime
    assert "validate_backend_url" in runtime
    assert "backend_endpoint()" in backend
    assert "validate_backend_url" in tools


@pytest.mark.parametrize(
    "value",
    [
        "https://127.0.0.1:8765",
        "http://192.168.1.2:8765",
        "http://user@127.0.0.1:8765",
        "http://127.0.0.1:0",
        "http://127.0.0.1:8765/api",
        "http://127.0.0.1:8765?owner=secret",
    ],
)
def test_python_backend_override_rejects_non_origin_or_non_loopback(value: str):
    with pytest.raises(RuntimeError):
        validate_backend_url(value)


def test_python_backend_override_accepts_canonical_loopback_origin():
    assert validate_backend_url("http://localhost:43127") == "http://localhost:43127"


def test_python_shared_host_and_port_environment_overrides(monkeypatch):
    monkeypatch.setenv("PBSTUDIO_HOST", "localhost")
    monkeypatch.setenv("PBSTUDIO_PORT", "43127")
    runtime_contract.backend_endpoint.cache_clear()
    try:
        endpoint = runtime_contract.backend_endpoint()
        assert endpoint.base_url == "http://localhost:43127"
    finally:
        runtime_contract.backend_endpoint.cache_clear()


def test_chat_backend_override_must_match_effective_contract(monkeypatch):
    from pb_studio.ai import tool_registry

    monkeypatch.setattr(
        tool_registry,
        "DEFAULT_BACKEND_BASE_URL",
        "http://localhost:43127",
    )
    monkeypatch.setenv("PBSTUDIO_BACKEND_URL", "http://localhost:43127")
    assert tool_registry._get_backend_base_url() == "http://localhost:43127"
    monkeypatch.setenv("PBSTUDIO_BACKEND_URL", "http://127.0.0.1:43127")
    with pytest.raises(RuntimeError):
        tool_registry._get_backend_base_url()


@pytest.mark.parametrize(
    "payload",
    [
        {"Backend": {"Scheme": "HTTP", "Host": "127.0.0.1", "Port": 8765}},
        {"Backend": {"Scheme": "http", "Host": " localhost", "Port": 8765}},
        {
            "Backend": {"Scheme": "http", "Host": "127.0.0.1", "Port": 8765},
            "Other": True,
        },
    ],
)
def test_python_and_powershell_reject_same_noncanonical_settings(
    monkeypatch, tmp_path: Path, payload: dict
):
    settings = tmp_path / "appsettings.json"
    settings.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runtime_contract, "APPSETTINGS_PATH", settings)
    runtime_contract.backend_endpoint.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            runtime_contract.backend_endpoint()
    finally:
        runtime_contract.backend_endpoint.cache_clear()

    script = ROOT / "scripts" / "runtime_contract.ps1"
    command = (
        f". '{script}'; "
        f"Get-PBStudioBackendEndpoint -ProjectRoot '{tmp_path}' | Out-Null"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_ui_bound_namespaces_do_not_suppress_dispatcher_context():
    sources = [
        *sorted((ROOT / "PBStudio.UI" / "ViewModels").rglob("*.cs")),
        *sorted((ROOT / "PBStudio.UI" / "Views").rglob("*.xaml.cs")),
        ROOT / "PBStudio.UI" / "MainWindow.xaml.cs",
    ]
    offenders: list[str] = []
    for path in sources:
        source = _without_line_comments(path, path.read_text(encoding="utf-8-sig"))
        if "ConfigureAwait(false)" in source:
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == [], (
        "UI-bound continuations must remain on the WPF Dispatcher context; "
        f"ConfigureAwait(false) remains in: {offenders}"
    )
