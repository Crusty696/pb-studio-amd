"""T357 contracts for GPU identity, model truth, and nullable video results.

The physical GPU/LHM probe is opt-in so the ordinary T361 suite cannot run
hardware work before the dedicated T363 gate.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ADAPTER_INDEX = 1
EXPECTED_ADAPTER_LUID = "0x00000000_0x00012a2a"
HARDWARE_PROBE_ENV = "PBSTUDIO_RUN_T357_HARDWARE"

DIRECTML_CONSUMERS = (
    ROOT / "src" / "pb_studio" / "core" / "model_loader.py",
    ROOT / "src" / "pb_studio" / "video" / "raft.py",
    ROOT / "src" / "pb_studio" / "video" / "moondream.py",
    ROOT / "src" / "pb_studio" / "ai" / "siglip_wrapper.py",
    ROOT / "src" / "pb_studio" / "ai" / "clap_wrapper.py",
    ROOT / "src" / "pb_studio" / "audio" / "separator.py",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _read_generated_dtos() -> str:
    """
    Liest die von NSwag generierten DTOs.

    Audit 2026-08-05: Zwei Tests lasen fest ``PBStudio.UI/Generated/ApiTypes.g.cs``.
    Dieses Verzeichnis ist eine Altlast — in git liegt dort nur ``.gitkeep``,
    ``nswag.json`` schreibt nach ``obj/Generated/ApiTypes.g.cs``, und die
    ``.csproj`` schliesst ``Generated\\*.g.cs`` ausdruecklich vom Kompilieren aus.
    Die Tests prueften also einen Stand, der nicht mehr gebaut wird. Jetzt wird
    der echte Output bevorzugt, der Legacy-Pfad bleibt Rueckfall.
    """
    for candidate in (
        "PBStudio.UI/obj/Generated/ApiTypes.g.cs",
        "PBStudio.UI/Generated/ApiTypes.g.cs",
    ):
        path = ROOT / candidate
        if path.is_file():
            return path.read_text(encoding="utf-8")
    pytest.skip(
        "ApiTypes.g.cs nicht gebaut — "
        "`dotnet build PBStudio.UI/PBStudio.UI.csproj` ausfuehren"
    )


def _method_block(source: str, marker: str, next_marker: str) -> str:
    start = source.index(marker)
    end = source.index(next_marker, start + len(marker))
    return source[start:end]


def _adapter(
    *,
    device_id: int,
    luid: str,
    name: str,
    dedicated_vram_mb: int,
    vendor_id: int = 0x1002,
    is_software: bool = False,
    is_discrete: bool = True,
):
    from pb_studio.core.directml_adapter import DirectMLAdapter

    return DirectMLAdapter(
        device_id=device_id,
        luid=luid,
        name=name,
        vendor_id=vendor_id,
        device_id_pci=0,
        dedicated_vram_bytes=dedicated_vram_mb * 1024 * 1024,
        shared_system_memory_bytes=0,
        is_software=is_software,
        is_discrete=is_discrete,
        high_performance_preferred=False,
        selection_policy="highest_vram_amd",
        selection_reason="test inventory",
    )


def test_default_policy_selects_discrete_amd_adapter_and_forwards_device_id():
    from pb_studio.core.directml_adapter import select_directml_adapter

    integrated = _adapter(
        device_id=0,
        luid="0x00000000_0x0000ffbc",
        name="AMD Radeon Graphics",
        dedicated_vram_mb=485,
        is_discrete=False,
    )
    discrete = _adapter(
        device_id=EXPECTED_ADAPTER_INDEX,
        luid=EXPECTED_ADAPTER_LUID,
        name="AMD Radeon RX 7800 XT",
        dedicated_vram_mb=16177,
    )
    software = _adapter(
        device_id=2,
        luid="0x00000000_0x00000000",
        name="Microsoft Basic Render Driver",
        dedicated_vram_mb=0,
        vendor_id=0x1414,
        is_software=True,
        is_discrete=False,
    )

    selected = select_directml_adapter(
        (integrated, discrete, software),
        {"hardware": {"directml_adapter_policy": "highest_vram_amd"}, "ai": {}},
    )

    assert selected.device_id == EXPECTED_ADAPTER_INDEX
    assert selected.luid == EXPECTED_ADAPTER_LUID
    assert selected.provider_tuple == (
        "DmlExecutionProvider",
        {"device_id": EXPECTED_ADAPTER_INDEX},
    )


def test_configured_integrated_adapter_fails_closed_when_discrete_amd_exists():
    from pb_studio.core.directml_adapter import (
        DirectMLAdapterError,
        select_directml_adapter,
    )

    adapters = (
        _adapter(
            device_id=0,
            luid="0x00000000_0x0000ffbc",
            name="AMD Radeon Graphics",
            dedicated_vram_mb=485,
            is_discrete=False,
        ),
        _adapter(
            device_id=EXPECTED_ADAPTER_INDEX,
            luid=EXPECTED_ADAPTER_LUID,
            name="AMD Radeon RX 7800 XT",
            dedicated_vram_mb=16177,
        ),
    )

    with pytest.raises(DirectMLAdapterError, match="integrated AMD adapter"):
        select_directml_adapter(
            adapters,
            {"hardware": {"directml_device_id": 0}, "ai": {}},
        )


def test_hardware_adapter_override_precedes_deprecated_ai_override():
    from pb_studio.core.directml_adapter import select_directml_adapter

    adapters = (
        _adapter(
            device_id=0,
            luid="0x00000000_0x0000ffbc",
            name="AMD Radeon Graphics",
            dedicated_vram_mb=485,
            is_discrete=False,
        ),
        _adapter(
            device_id=EXPECTED_ADAPTER_INDEX,
            luid=EXPECTED_ADAPTER_LUID,
            name="AMD Radeon RX 7800 XT",
            dedicated_vram_mb=16177,
        ),
    )

    selected = select_directml_adapter(
        adapters,
        {
            "hardware": {"directml_device_id": EXPECTED_ADAPTER_INDEX},
            "ai": {"dml_device_id": 0},
        },
    )

    assert selected.device_id == EXPECTED_ADAPTER_INDEX
    assert selected.selection_policy == "configured_device_id"
    assert selected.selection_reason == "hardware.directml_device_id"


def test_deprecated_ai_adapter_override_remains_readable(caplog):
    from pb_studio.core.directml_adapter import select_directml_adapter

    selected = select_directml_adapter(
        (
            _adapter(
                device_id=EXPECTED_ADAPTER_INDEX,
                luid=EXPECTED_ADAPTER_LUID,
                name="AMD Radeon RX 7800 XT",
                dedicated_vram_mb=16177,
            ),
        ),
        {
            "hardware": {"directml_adapter_policy": "highest_vram_amd"},
            "ai": {"dml_device_id": EXPECTED_ADAPTER_INDEX},
        },
    )

    assert selected.device_id == EXPECTED_ADAPTER_INDEX
    assert selected.selection_policy == "configured_device_id"
    assert selected.selection_reason == "ai.dml_device_id"
    assert "ai.dml_device_id is deprecated" in caplog.text


@pytest.mark.parametrize("consumer_path", DIRECTML_CONSUMERS, ids=lambda p: p.name)
def test_directml_consumers_share_provider_and_disable_both_session_flags(
    consumer_path: Path,
):
    source = consumer_path.read_text(encoding="utf-8")
    central = _read("src/pb_studio/core/directml_adapter.py")

    if consumer_path.name == "siglip_wrapper.py":
        assert "from pb_studio.core.model_loader import ModelLoader" in source
        assert 'loader.load_model("siglip_vision", force=True)' in source
        assert "ort.InferenceSession(" not in source
    else:
        assert "get_directml_provider" in source
        assert "get_directml_provider()" in source
    assert "enable_mem_pattern = False" in central
    assert "enable_cpu_mem_arena = False" in central
    assert '"session.disable_cpu_ep_fallback"' in central
    assert "get_session_options()" in central
    assert "get_session_config_entry" in central
    assert "disable_fallback()" in central
    assert 'providers[0] != "DmlExecutionProvider"' in central
    assert '["DmlExecutionProvider", "CPUExecutionProvider"]' not in source
    assert "ai.dml_device_id" not in source

    if consumer_path.name == "separator.py":
        assert "self.separator.onnx_execution_provider = [provider]" in source
        assert "configure_directml_session_options" in source
        assert "enforce_directml_session" in source
        assert "_directml_session_created" in source
        assert "PyTorch CPU conversion is disabled" in source
    elif consumer_path.name == "siglip_wrapper.py":
        assert "enforce_directml_session" in source
    elif consumer_path.name != "clap_wrapper.py":
        assert "providers=providers" in source
        assert "configure_directml_session_options" in source
        assert "enforce_directml_session" in source
    else:
        assert "enforce_directml_session" in source


@pytest.mark.skipif(
    os.environ.get(HARDWARE_PROBE_ENV) != "1",
    reason=f"Set {HARDWARE_PROBE_ENV}=1 only at the T363 hardware gate.",
)
def test_physical_directml_and_lhm_identity_is_rx7800xt(monkeypatch):
    from pb_studio.core import directml_adapter, system_monitor

    contract = json.loads(_read("config/lhm-runtime.json"))
    monkeypatch.setenv(
        "PBSTUDIO_LHM_MANIFEST_SHA256",
        contract["active"]["manifest_sha256"],
    )
    monkeypatch.setenv(
        "PBSTUDIO_LHM_SHA256",
        contract["active"]["library_sha256"],
    )

    adapter = directml_adapter.get_directml_adapter(refresh=True)
    assert adapter.device_id == EXPECTED_ADAPTER_INDEX
    assert adapter.luid == EXPECTED_ADAPTER_LUID
    assert "RX 7800 XT" in adapter.name
    assert directml_adapter.get_directml_provider() == (
        "DmlExecutionProvider",
        {"device_id": EXPECTED_ADAPTER_INDEX},
    )

    previous = system_monitor.SystemMonitor._instance
    monitor = None
    try:
        system_monitor.SystemMonitor._instance = None
        monitor = system_monitor.SystemMonitor()
        stats = monitor.get_stats()
        assert monitor.selected_adapter_luid == EXPECTED_ADAPTER_LUID
        assert stats["adapter_index"] == EXPECTED_ADAPTER_INDEX
        assert stats["adapter_luid"] == EXPECTED_ADAPTER_LUID
        assert stats["monitoring_status"] == "ready"
    finally:
        if monitor is not None:
            monitor.close()
        system_monitor.SystemMonitor._instance = previous


def test_gpu_status_api_reports_selected_identity_and_monitoring_truth(monkeypatch):
    import backend.main as backend_main
    from pb_studio.core import directml_adapter, system_monitor

    adapter = SimpleNamespace(
        name="AMD Radeon RX 7800 XT",
        device_id=EXPECTED_ADAPTER_INDEX,
        luid=EXPECTED_ADAPTER_LUID,
        selection_policy="highest_vram_amd",
        dedicated_vram_mb=16177,
    )
    monitor = SimpleNamespace(
        get_stats=lambda: {
            "gpu_memory_used": 3210.0,
            "gpu_temp": 47.0,
            "driver_version": "test-driver",
            "adapter_luid": EXPECTED_ADAPTER_LUID,
            "monitoring_status": "ready",
            "monitoring_error": None,
        }
    )
    monkeypatch.setattr(
        directml_adapter,
        "get_directml_adapter",
        lambda: adapter,
    )
    monkeypatch.setattr(system_monitor, "SystemMonitor", lambda: monitor)
    monkeypatch.setattr(backend_main, "_check_gpu_available", lambda: True)

    payload = asyncio.run(backend_main.gpu_status())

    assert payload == {
        "name": adapter.name,
        "vram_total_mb": 16177,
        "vram_used_mb": 3210.0,
        "temperature_c": 47.0,
        "driver_version": "test-driver",
        "adapter_index": EXPECTED_ADAPTER_INDEX,
        "adapter_luid": EXPECTED_ADAPTER_LUID,
        "adapter_name": adapter.name,
        "selection_policy": "highest_vram_amd",
        "dedicated_vram_total_mb": 16177,
        "directml_active": True,
        "monitoring_status": "ready",
        "monitoring_error": None,
    }


def test_settings_gui_binds_every_additive_gpu_truth_field():
    dto = _read("PBStudio.UI/Services/ApiClient.cs")
    view_model = _read("PBStudio.UI/ViewModels/SettingsViewModel.cs")
    view = _read("PBStudio.UI/Views/SettingsView.xaml")
    schema = json.loads(_read("PBStudio.UI/openapi.snapshot.json"))
    generated = _read_generated_dtos()

    for dto_field in (
        "AdapterIndex",
        "AdapterLuid",
        "AdapterName",
        "SelectionPolicy",
        "DedicatedVramTotalMb",
        "DirectmlActive",
        "MonitoringStatus",
        "MonitoringError",
    ):
        assert dto_field in dto

    for binding in (
        "GpuName",
        "GpuAdapterIndex",
        "GpuAdapterLuid",
        "GpuSelectionPolicy",
        "DirectmlStatus",
        "MonitoringStatus",
        "MonitoringError",
        "VramTotal",
        "VramUsed",
        "Temperature",
    ):
        assert f"{{Binding {binding}" in view

    assert "GpuName = gpu.AdapterName ?? gpu.Name;" in view_model
    assert "GpuAdapterIndex = gpu.AdapterIndex?.ToString()" in view_model
    assert "GpuAdapterLuid = gpu.AdapterLuid" in view_model
    assert "GpuSelectionPolicy = gpu.SelectionPolicy" in view_model
    assert "VramTotal = gpu.DedicatedVramTotalMb > 0" in view_model
    assert '"degraded" => "Eingeschr\u00e4nkt"' in view_model
    gpu_response = schema["paths"]["/gpu/status"]["get"]["responses"]["200"]
    assert gpu_response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/GpuStatusResponse"
    }
    gpu_properties = schema["components"]["schemas"]["GpuStatusResponse"][
        "properties"
    ]
    for field in (
        "adapter_index",
        "adapter_luid",
        "adapter_name",
        "selection_policy",
        "dedicated_vram_total_mb",
        "directml_active",
        "monitoring_status",
        "monitoring_error",
    ):
        assert field in gpu_properties
    assert "public partial class GpuStatusResponse" in generated


@pytest.mark.gpu
def test_lhm_runtime_contract_hashes_bundle_and_bridge_forwards_trust_anchors():
    contract = json.loads(_read("config/lhm-runtime.json"))
    active = contract["active"]
    bundle = (ROOT / active["bundle_dir"]).resolve(strict=True)
    assert bundle.is_relative_to(ROOT.resolve())

    manifest_path = bundle / active["manifest"]
    library_path = bundle / active["library"]
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == (
        active["manifest_sha256"].lower()
    )
    assert hashlib.sha256(library_path.read_bytes()).hexdigest() == (
        active["library_sha256"].lower()
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == active["version"] == "0.9.6"
    assert manifest["asset_sha256"] == contract["source"]["asset_sha256"].lower()
    assert manifest["assemblies"]
    for assembly in manifest["assemblies"]:
        assembly_path = (bundle / assembly["file"]).resolve(strict=True)
        assert assembly_path.parent == bundle
        assert hashlib.sha256(assembly_path.read_bytes()).hexdigest() == (
            assembly["sha256"].lower()
        )

    bridge = _read("PBStudio.UI/Services/PythonBridgeService.cs")
    assert 'Path.Combine(projectRoot, "config", "lhm-runtime.json")' in bridge
    assert 'startInfo.Environment["PBSTUDIO_LHM_MANIFEST_SHA256"]' in bridge
    assert 'startInfo.Environment["PBSTUDIO_LHM_SHA256"]' in bridge
    assert "SHA256.HashData(File.ReadAllBytes(manifestPath))" in bridge
    assert "SHA256.HashData(File.ReadAllBytes(libraryPath))" in bridge

    runtime_contract = _read("scripts/runtime_contract.ps1")
    assert "config\\lhm-runtime.json" in runtime_contract
    assert "$env:PBSTUDIO_LHM_MANIFEST_SHA256 = $lhmManifestHash" in (
        runtime_contract
    )
    assert "$env:PBSTUDIO_LHM_SHA256 = $lhmLibraryHash" in runtime_contract
    assert "Get-FileHash -LiteralPath $item.Path -Algorithm SHA256" in (
        runtime_contract
    )
    assert "LhmManifestSha256 = $lhmManifestHash" in runtime_contract
    assert "LhmLibrarySha256 = $lhmLibraryHash" in runtime_contract


@pytest.mark.gpu
def test_lhm_backup_restore_copy_reproduces_exact_file_set_and_hashes(tmp_path):
    inventory = json.loads(
        _read(
            "specs/00013-system-wide-bug-hunting-audit/"
            "evidence/T347-lhm-backup-sha256.json"
        )
    )
    backup_path = ROOT / inventory["backup_path"]
    if not backup_path.exists():
        pytest.skip("historical LHM backup is intentionally not versioned")
    backup = backup_path.resolve(strict=True)
    assert backup.is_relative_to(ROOT.resolve())

    restored = tmp_path / "LibreHardwareMonitor-restored"
    shutil.copytree(backup, restored)

    restored_files = {
        path.relative_to(restored).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in restored.rglob("*")
        if path.is_file()
    }
    assert len(restored_files) == inventory["file_count"] == 43
    assert restored_files == inventory["files"]


def test_model_manager_uses_live_truth_labels_without_static_ghost_cards():
    router = _read("backend/routers/models_router.py")
    inventory = _read("src/pb_studio/ai/model_inventory.py")
    view_model = _read("PBStudio.UI/ViewModels/ModelManagerViewModel.cs")
    view = _read("PBStudio.UI/Views/ModelManagerView.xaml")

    available_endpoint = _method_block(
        router,
        "async def list_available_models()",
        "# ----------------------------------------------------------------------\n# POST /models/pull",
    )
    assert "for model in snapshot.models" in available_endpoint
    assert "if model.downloadable and not model.installed" in available_endpoint
    assert "CURATED_VISION_MODELS" not in available_endpoint
    assert "downloadable_candidates or {}" in inventory

    apply_installed = _method_block(
        view_model,
        "private void ApplyInstalled",
        "private void ApplyAvailable",
    )
    assert "foreach (var entry in resp.Models" in apply_installed
    assert "CURATED" not in apply_installed.upper()
    assert "Loaded = entry.Loaded;" in view_model
    assert "Usable = entry.Usable;" in view_model
    assert '? "GELADEN"' in view_model
    assert '? "ON-DEMAND"' in view_model
    assert ': "NICHT NUTZBAR"' in view_model
    assert "Downloadable = entry.Downloadable;" in view_model
    assert "Downloadable && !Installed && !IsBusy" in view_model

    assert 'Text="{Binding StateText}"' in view
    assert 'Text="{Binding StatusReason}"' in view
    assert "keine statischen Modellkarten eingeblendet" in view
    assert 'ItemsSource="{Binding AvailableModels}"' in view


def test_model_provider_identity_is_forwarded_from_card_to_backend():
    interface = _read("PBStudio.UI/Services/IApiClient.cs")
    client = _read("PBStudio.UI/Services/ApiClient.cs")
    owner_handler = _read(
        "PBStudio.UI/Services/OwnerCapabilityRequestHandler.cs"
    )
    view_model = _read("PBStudio.UI/ViewModels/ModelManagerViewModel.cs")
    view = _read("PBStudio.UI/Views/ModelManagerView.xaml")
    settings = _read("PBStudio.UI/ViewModels/SettingsViewModel.cs")
    router = _read("backend/routers/models_router.py")
    schema = json.loads(_read("PBStudio.UI/openapi.snapshot.json"))

    assert "ActivateModelAsync(string name, string provider" in interface
    assert "TestModelAsync(string name, string provider" in interface
    assert "PostOwnerAuthorizedAsync<object>" in client
    assert '"/models/activate"' in client
    assert (
        "PostOwnerAuthorizedAsync<ModelTestResponse>"
        in client
    )
    assert '"/models/test"' in client
    # Audit 2026-08-05 (H-1): Die frühere Vorabprüfung auf
    # BackendOwnerCapability.Current lief ausserhalb des RevalidationGate und
    # brach jeden Request hart ab, der in das 10-Sekunden-Revalidierungsfenster
    # des Watchdogs fiel ("Button reagiert nicht"). Sie ist entfernt; die
    # fail-closed-Prüfung findet unter Lease im Handler statt. Der Contract ist
    # daher: ApiClient darf NICHT mehr vorab prüfen, der Handler MUSS es tun.
    assert "BackendOwnerCapability.Current" not in client
    assert "AcquireRequestLeaseAsync" in owner_handler
    assert "TryAddWithoutValidation" in owner_handler
    assert "BackendOwnerCapability.HeaderName" in owner_handler
    assert "ActivateModelAsync(card.Name, card.Provider)" in view_model
    assert "TestModelAsync(card.Name, card.Provider)" in view_model
    assert "provider: Optional[str]" in router
    assert "if not provider or model.provider == provider" in router
    assert "provider=requested_provider" in router
    assert "provider=provider" in router
    assert "get_llm_client(provider=selected.provider)" in router
    assert 'card.Provider.Equals("ollama"' in view_model
    assert "DownloadActionText" in view_model
    assert 'Text="{Binding ProviderLabel}"' in view
    assert 'Text="{Binding DownloadActionText}"' in view
    assert 'ToolTip="{Binding DownloadToolTip}"' in view
    assert "rec.Provider" in settings
    assert "rec.SelectionSource" in settings
    assert "rec.VerifiedCapabilities" in settings
    for method, path in (
        ("post", "/models/pull"),
        ("delete", "/models/{name}"),
        ("post", "/models/activate"),
        ("post", "/models/mode"),
        ("post", "/models/test"),
    ):
        parameter_names = {
            item["name"]
            for item in schema["paths"][path][method].get("parameters", [])
        }
        assert "X-PBStudio-Owner-Capability" in parameter_names


def test_sceneinfo_confidence_is_nullable_across_all_contract_artifacts():
    from backend.schemas.video_schemas import SceneInfo

    assert SceneInfo(start_time=0.0, end_time=1.0).confidence is None

    schema = json.loads(_read("PBStudio.UI/openapi.snapshot.json"))
    scene_schema = schema["components"]["schemas"]["SceneInfo"]
    confidence = scene_schema["properties"]["confidence"]
    assert confidence["type"] == "number"
    assert confidence["nullable"] is True
    assert "confidence" not in scene_schema["required"]

    generated = _read_generated_dtos()
    generated_scene = _method_block(
        generated,
        "public partial class SceneInfo",
        "public partial class SpectralData",
    )
    assert "SceneInfo(double? @confidence" in generated_scene
    assert "public double? Confidence { get; }" in generated_scene

    handwritten = _read("PBStudio.UI/Services/ApiClient.cs")
    assert (
        "record SceneInfo(double StartTime, double EndTime, "
        "string SceneType, double? Confidence)"
    ) in handwritten


@pytest.mark.parametrize(
    ("method_marker", "next_marker", "status_prefix"),
    (
        (
            "private async Task AnalyzeMarkedAsync()",
            "private void UpdateAnalyzedCounts()",
            "Markierte fertig:",
        ),
        (
            "private async Task AnalyzeAllAsync()",
            "private async Task LoadAllThumbnailsAsync(",
            "Batch fertig:",
        ),
    ),
)
def test_video_batch_retries_requested_stages_and_counts_success_only_after_non_null_analysis(
    method_marker: str,
    next_marker: str,
    status_prefix: str,
):
    source = _read("PBStudio.UI/ViewModels/VideoLibraryViewModel.cs")
    dto = _read("PBStudio.UI/Services/ApiClient.cs")
    method = _method_block(source, method_marker, next_marker)

    assert 'string Status = "completed"' in dto
    assert "Dictionary<string, string>? StageStatus = null" in dto
    assert "Dictionary<string, string>? StageErrors = null" in dto

    null_branch = method.index("if (result == null)")
    failure_increment = method.index("failed++;", null_branch)
    partial_branch = method.index(
        "else if (!IsCompleted(result))",
        failure_increment,
    )
    partial_failure = method.index("failed++;", partial_branch)
    else_branch = method.index("else", partial_failure)
    success_increment = method.index("succeeded++;", else_branch)
    apply_result = method.index("ApplyAnalysisResult(", failure_increment)

    assert null_branch < failure_increment < partial_branch < partial_failure
    assert partial_failure < else_branch
    assert apply_result < partial_branch < success_increment
    assert "clip.IsAnalyzed = IsCompleted(result);" in source
    assert method.count("failed++;") >= 3
    assert "if (target.IsAnalyzed)" not in method
    assert "skipped++" not in method
    assert status_prefix in method
    assert "{succeeded} erfolgreich" in method
    assert "{failed} fehlgeschlagen" in method
    assert "{skipped}" not in method
