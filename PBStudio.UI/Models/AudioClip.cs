using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using CommunityToolkit.Mvvm.ComponentModel;

namespace PBStudio.UI.Models;

public sealed record StageAttemptReceipt(
    string Provider = "",
    string ModelId = "",
    string Task = "",
    string Mode = "",
    List<string>? RequiredCapabilities = null,
    List<string>? VerifiedCapabilities = null,
    string Source = "",
    string Reason = "",
    string SelectedAt = "");

public sealed record StageReceipt(
    int ReceiptVersion = 0,
    string StageId = "",
    bool Requested = false,
    string Status = "unavailable",
    string? InputFingerprint = null,
    string? ConfigFingerprint = null,
    string? ArtifactRef = null,
    string? ArtifactSha256 = null,
    bool? ArtifactValid = null,
    string? StartedAtUtc = null,
    string? FinishedAtUtc = null,
    string? ErrorCode = null,
    string? ErrorMessage = null,
    string? Provider = null,
    string? ModelId = null,
    List<StageAttemptReceipt>? Attempts = null,
    string? CorrelationId = null);

public sealed record AudioStageStatusItem(
    string StageId,
    string Status,
    string Reason);

/// <summary>Audio-Clip Model für die UI-Darstellung.</summary>
public partial class AudioClipModel : ObservableObject
{
    private static readonly string[] RetryRequestStageIds =
        ["beats", "structure", "spectral", "key"];

    [ObservableProperty] private int _id;
    [ObservableProperty] private string _name = "";
    [ObservableProperty] private string _path = "";
    [ObservableProperty] private double _durationSeconds;
    [ObservableProperty] private int _sampleRate = 44100;
    [ObservableProperty] private int _channels = 2;
    [ObservableProperty] private string _format = "mp3";
    [ObservableProperty] private double _bpm;
    [ObservableProperty] private string _key = "";
    [ObservableProperty] private int _beatCount;
    [ObservableProperty] private bool _isAnalyzed;
    [ObservableProperty] private string _analysisStatus = "unavailable";
    [ObservableProperty] private Dictionary<string, string>? _stageStatus;
    [ObservableProperty] private Dictionary<string, string>? _stageErrors;
    [ObservableProperty] private Dictionary<string, StageReceipt>? _stageReceipts;
    // L-N2: Content-Hash vom Backend; HasCacheHash treibt CACHED-Badge im View.
    [ObservableProperty] private string? _audioHash;
    // L-N4: Stem-Separation Outputs vom Backend (vocals/drums/bass/other -> path).
    // HasStems treibt STEMS-Badge + Open-Folder-Button im View.
    [ObservableProperty] private Dictionary<string, string>? _stemsPaths;

    public ObservableCollection<AudioStageStatusItem> StageItems { get; } = [];

    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public bool HasCacheHash => !string.IsNullOrWhiteSpace(AudioHash);
    public bool HasStems => StemsPaths != null && StemsPaths.Count > 0;
    public bool HasAnalysisIssue => AnalysisStatus is
        "partial" or "failed" or "interrupted" or "unavailable";
    public bool CanRetryAnalysis => HasPersistedStageTruth
        && RetryRequestStageIds.Any(IsRetryEligibleForDefaultRequest);
    public string AnalysisStatusText => AnalysisStatus switch
    {
        "partial" => "PARTIAL",
        "failed" => "FAILED",
        "interrupted" => "INTERRUPTED",
        "unavailable" => "UNAVAILABLE",
        "running" => "RUNNING",
        "completed" => "COMPLETED",
        _ => AnalysisStatus.ToUpperInvariant(),
    };
    public string? StemsFolderPath
    {
        get
        {
            if (!HasStems) return null;
            var rawPath = StemsPaths!.Values.First();
            if (string.IsNullOrEmpty(rawPath)) return null;
            var normalized = rawPath.Replace('/', '\\');
            return System.IO.Path.GetDirectoryName(normalized);
        }
    }

    partial void OnDurationSecondsChanged(double value) => OnPropertyChanged(nameof(DurationText));
    partial void OnAudioHashChanged(string? value) => OnPropertyChanged(nameof(HasCacheHash));
    partial void OnAnalysisStatusChanged(string value)
    {
        if (value != "completed")
            IsAnalyzed = false;
        OnPropertyChanged(nameof(HasAnalysisIssue));
        OnPropertyChanged(nameof(AnalysisStatusText));
        RefreshStageTruth();
    }
    partial void OnStageStatusChanged(Dictionary<string, string>? value) =>
        RefreshStageTruth();
    partial void OnStageErrorsChanged(Dictionary<string, string>? value) =>
        RefreshStageTruth();
    partial void OnStageReceiptsChanged(Dictionary<string, StageReceipt>? value) =>
        RefreshStageTruth();
    partial void OnStemsPathsChanged(Dictionary<string, string>? value)
    {
        OnPropertyChanged(nameof(HasStems));
        OnPropertyChanged(nameof(StemsFolderPath));
    }

    private bool HasPersistedStageTruth =>
        StageReceipts?.Count > 0 || StageStatus?.Count > 0;

    private bool IsRetryEligibleForDefaultRequest(string stageId)
    {
        if (StageReceipts is null || !StageReceipts.TryGetValue(stageId, out var receipt))
        {
            return StageStatus is null
                || !StageStatus.TryGetValue(stageId, out var legacyStatus)
                || legacyStatus is "missing" or "failed" or "interrupted" or "unavailable";
        }

        return !receipt.Requested
            || receipt.Status is "missing" or "failed" or "interrupted" or "unavailable";
    }

    private void RefreshStageTruth()
    {
        var stageIds = (StageReceipts?.Keys ?? Enumerable.Empty<string>())
            .Concat(StageStatus?.Keys ?? Enumerable.Empty<string>())
            .Distinct(StringComparer.Ordinal);

        StageItems.Clear();
        foreach (var stageId in stageIds)
        {
            StageReceipt? receipt = null;
            if (StageReceipts is not null)
                StageReceipts.TryGetValue(stageId, out receipt);
            if (receipt is not null && !receipt.Requested)
                continue;

            var status = receipt?.Status
                ?? (StageStatus?.TryGetValue(stageId, out var legacyStatus) == true
                    ? legacyStatus
                    : "missing");
            if (receipt is null && status is "skipped" or "not_requested")
                continue;
            var reason = !string.IsNullOrWhiteSpace(receipt?.ErrorMessage)
                ? receipt.ErrorMessage!
                : StageErrors?.TryGetValue(stageId, out var legacyError) == true
                    ? legacyError
                    : status == "missing"
                        ? "StageReceipt fehlt"
                        : string.Empty;
            StageItems.Add(new AudioStageStatusItem(stageId, status, reason));
        }

        OnPropertyChanged(nameof(CanRetryAnalysis));
    }
}
