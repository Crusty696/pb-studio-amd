from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "PBStudio.UI" / "Models" / "AudioClip.cs"
VM = ROOT / "PBStudio.UI" / "ViewModels" / "AudioLibraryViewModel.cs"
VIEW = ROOT / "PBStudio.UI" / "Views" / "AudioLibraryView.xaml"
API = ROOT / "PBStudio.UI" / "Services" / "ApiClient.cs"


RECEIPT_FIELDS = (
    "ReceiptVersion",
    "StageId",
    "Requested",
    "Status",
    "InputFingerprint",
    "ConfigFingerprint",
    "ArtifactRef",
    "ArtifactSha256",
    "ArtifactValid",
    "StartedAtUtc",
    "FinishedAtUtc",
    "ErrorCode",
    "ErrorMessage",
    "Provider",
    "ModelId",
    "Attempts",
    "CorrelationId",
)

ATTEMPT_FIELDS = (
    "Provider",
    "ModelId",
    "Task",
    "Mode",
    "RequiredCapabilities",
    "VerifiedCapabilities",
    "Source",
    "Reason",
    "SelectedAt",
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _record_body(source: str, record_name: str) -> str:
    match = re.search(
        rf"public\s+(?:sealed\s+)?record\s+{record_name}\s*\((.*?)\)\s*;",
        source,
        flags=re.DOTALL,
    )
    assert match, f"typed record {record_name} fehlt"
    return match.group(1)


def test_typed_receipt_and_attempt_transport_is_complete_and_deserialized():
    api = _source(API)
    contracts = api + "\n" + _source(MODEL)

    receipt = _record_body(contracts, "StageReceipt")
    attempt = _record_body(contracts, "StageAttemptReceipt")
    for field in RECEIPT_FIELDS:
        assert re.search(rf"\b{field}\b", receipt), f"StageReceipt.{field} fehlt"
    for field in ATTEMPT_FIELDS:
        assert re.search(rf"\b{field}\b", attempt), f"StageAttemptReceipt.{field} fehlt"

    assert "Dictionary<string, StageReceipt>? StageReceipts" in api
    assert "AudioClipInfo" in api and "StageReceipts" in _record_body(api, "AudioClipInfo")
    assert "AudioAnalysisResult" in api and "StageReceipts" in api
    assert "PBStudio.UI.Generated.AudioAnalysisResult" not in api
    assert re.search(
        r"PostAsync<AudioAnalysisResult>\s*\(\s*\"/audio/analyze\"",
        api,
        flags=re.DOTALL,
    ), "Analyze muss stage_receipts in den projekt-eigenen typisierten DTO lesen"


def test_clip_model_derives_retry_and_stage_rows_from_receipt_truth():
    model = _source(MODEL)

    assert "Dictionary<string, StageReceipt>? _stageReceipts" in model
    assert "ObservableCollection<AudioStageStatusItem> StageItems" in model
    assert "public bool CanRetryAnalysis" in model
    assert 'receipt.Requested' in model
    assert '"missing" or "failed" or "interrupted" or "unavailable"' in model
    assert "receipt.ErrorMessage" in model
    assert "StageErrors" in model
    assert "OnPropertyChanged(nameof(CanRetryAnalysis))" in model
    assert "HasPersistedStageTruth" in model
    assert "RetryRequestStageIds" in model
    assert "return !receipt.Requested" in model

    # No accidental broad retry for partial/running/skipped/completed.
    eligibility = re.search(
        r"private bool IsRetryEligibleForDefaultRequest\(string stageId\)\s*\{(.*?)\n\s*\}",
        model,
        flags=re.DOTALL,
    )
    assert eligibility
    assert '"unavailable"' in eligibility.group(1)
    assert '"partial"' not in eligibility.group(1)
    assert '"running"' not in eligibility.group(1)
    assert '"skipped"' not in eligibility.group(1)
    assert '"completed"' not in eligibility.group(1)


def test_reload_and_analysis_mapping_carry_all_stage_truth():
    vm = _source(VM)

    for assignment in (
        "StageStatus = clipInfo.StageStatus",
        "StageErrors = clipInfo.StageErrors",
        "StageReceipts = clipInfo.StageReceipts",
        "StageStatus = result.StageStatus",
        "StageErrors = result.StageErrors",
        "StageReceipts = result.StageReceipts",
    ):
        assert assignment in vm

    assert 'result.AnalysisStatus == "completed"' in vm
    assert "RetrySelectedCommand" in vm
    assert "CanRetrySelected" in vm
    assert "AnalyzeAudioAsync(clip.Id" in vm


def test_terminal_analysis_sse_reloads_persisted_truth_for_correlated_clip():
    vm = _source(VM)

    assert "IsTerminalAnalysisStatus" in vm
    for status in ("completed", "partial", "failed", "interrupted", "unavailable"):
        assert f'"{status}"' in vm
    assert "RefreshClipFromPersistenceAsync" in vm
    assert "_projectService.IsCurrent" in vm
    assert "IsEventForKnownAudioClip" in vm
    assert "_audioLibraryState.Clear()" in vm
    assert "await LoadAudioClipsAsync()" in vm


def test_xaml_renders_requested_stage_status_reason_and_single_retry_action():
    xaml = _source(VIEW)
    ET.parse(VIEW)

    assert 'ItemsSource="{Binding SelectedClip.StageItems}"' in xaml
    assert 'Text="{Binding StageId}"' in xaml
    assert 'Text="{Binding Status}"' in xaml
    assert 'Text="{Binding Reason}"' in xaml
    assert xaml.count('Command="{Binding RetrySelectedCommand}"') == 1
    assert 'Visibility="{Binding SelectedClip.CanRetryAnalysis' in xaml
    assert 'AutomationProperties.Name="Fehlende oder fehlgeschlagene Analyse-Stufen erneut ausführen"' in xaml
