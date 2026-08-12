from __future__ import annotations

import json
import re
from pathlib import Path


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
    r"\bport\s+8765\b|\bBackendPort\s*=\s*8765\b)",
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
