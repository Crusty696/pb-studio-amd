using System;
using System.Collections.Generic;
using System.IO;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// Lern-Session — Walkthrough über 15 unsicherste Cuts mit Preview + 4-Klick (Plan Phase 5).
/// L-FE-7: IDisposable, da Event-Subscriptions in LearningSessionDialog.xaml.cs
/// die VM gegen GC haengen lassen (AddTransient — kein DI-Dispose-Hook).
/// </summary>
public partial class LearningSessionViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private List<BrainSuggestion> _cuts = new();
    private string? _projectAudioPath;
    private string? _projectVideoBasePath;
    private bool _disposed;

    public event Action? RequestClose;
    public event Action? PlayRequested;
    public event Action? PauseRequested;
    public event Action? RestartRequested;

    [ObservableProperty] private int _currentIndex;
    [ObservableProperty] private int _totalCount;
    [ObservableProperty] private int _currentCutId;
    [ObservableProperty] private string _currentClipId = "";
    [ObservableProperty] private double _currentStartTime;
    [ObservableProperty] private double _currentEndTime;
    [ObservableProperty] private double _currentFinalScore;
    [ObservableProperty] private Uri? _currentVideoUri;
    [ObservableProperty] private Uri? _currentAudioUri;
    [ObservableProperty] private string _status = "";

    public string CurrentIndexDisplay => (CurrentIndex + 1).ToString();

    public LearningSessionViewModel(IApiClient api)
    {
        _api = api;
    }

    public async Task LoadAsync(string? audioPath = null, string? videoBasePath = null)
    {
        _projectAudioPath = audioPath;
        _projectVideoBasePath = videoBasePath;
        var resp = await _api.BrainLearningSessionAsync();
        if (resp?.Cuts == null || resp.Cuts.Count == 0)
        {
            Status = "Keine Cuts in der aktuellen Lern-Session.";
            TotalCount = 0;
            return;
        }
        _cuts = resp.Cuts;
        TotalCount = _cuts.Count;
        CurrentIndex = 0;
        ApplyCurrent();
    }

    private void ApplyCurrent()
    {
        if (_cuts.Count == 0)
        {
            Status = "Keine Cuts geladen.";
            return;
        }
        var c = _cuts[CurrentIndex];
        CurrentCutId = c.CutId ?? 0;
        CurrentClipId = c.ClipId ?? "";
        CurrentStartTime = c.StartTime;
        CurrentEndTime = c.EndTime;
        CurrentFinalScore = c.FinalScore;

        // Best-effort Pfade — Vault-/Render-System löst real auf, hier reicht ClipId-Heuristik.
        CurrentVideoUri = ResolveVideoUri(c.ClipId);
        CurrentAudioUri = !string.IsNullOrEmpty(_projectAudioPath)
            ? new Uri(_projectAudioPath, UriKind.Absolute)
            : null;

        Status = $"Cut {CurrentIndex + 1}/{TotalCount}: {c.ClipId} @ {c.StartTime:F2}s";
        OnPropertyChanged(nameof(CurrentIndexDisplay));
    }

    private Uri? ResolveVideoUri(string? clipId)
    {
        if (string.IsNullOrEmpty(_projectVideoBasePath) || string.IsNullOrEmpty(clipId))
            return null;
        // try common file patterns: <base>/<clipId>.mp4 or <base>/clip_<id>.mp4
        var trimmed = clipId.StartsWith("clip_") ? clipId.Substring(5) : clipId;
        foreach (var name in new[] { clipId + ".mp4", $"clip_{trimmed}.mp4", trimmed + ".mp4" })
        {
            var p = Path.Combine(_projectVideoBasePath, name);
            if (File.Exists(p)) return new Uri(p, UriKind.Absolute);
        }
        return null;
    }

    [RelayCommand]
    public void Next()
    {
        if (CurrentIndex + 1 < _cuts.Count)
        {
            CurrentIndex++;
            ApplyCurrent();
        }
        else
        {
            Status = "Letzter Cut erreicht.";
        }
    }

    [RelayCommand]
    public void Prev()
    {
        if (CurrentIndex > 0)
        {
            CurrentIndex--;
            ApplyCurrent();
        }
    }

    [RelayCommand]
    public Task RatePerfectAsync() => RateAsync("perfect");
    [RelayCommand]
    public Task RateFitsAsync() => RateAsync("fits");
    [RelayCommand]
    public Task RateNotQuiteAsync() => RateAsync("not_quite");
    [RelayCommand]
    public Task RateNoMatchAsync() => RateAsync("no_match");

    private async Task RateAsync(string rating)
    {
        if (_cuts.Count == 0) return;
        var c = _cuts[CurrentIndex];
        if (c.CutId == null)
        {
            Status = "Kein cut_id verfügbar.";
            return;
        }
        var cutId = c.CutId.Value;
        var resp = await _api.BrainFeedbackAsync(cutId, rating);
        if (resp == null)
        {
            Status = "Feedback fehlgeschlagen.";
            return;
        }
        Status = $"OK — {resp.UpdatedBuckets} buckets, total={resp.TotalClicks}. → next";
        // Cross-VM-Refresh: TimelineViewModel laedt Confidence + Tooltip fuer diesen Cut neu.
        WeakReferenceMessenger.Default.Send(new BrainFeedbackAppliedMessage(cutId));
        Next();
    }

    [RelayCommand]
    public void PlayPause() => PlayRequested?.Invoke();

    [RelayCommand]
    public void Restart() => RestartRequested?.Invoke();

    [RelayCommand]
    public void Close() => RequestClose?.Invoke();

    /// <summary>
    /// L-FE-7: Event-Subscriptions aufloesen damit der LearningSessionDialog
    /// nach Close korrekt GCd werden kann (Lambdas in xaml.cs capturen sonst
    /// den Dialog via this-Reference und halten die VM lebendig).
    /// </summary>
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        RequestClose = null;
        PlayRequested = null;
        PauseRequested = null;
        RestartRequested = null;
        WeakReferenceMessenger.Default.UnregisterAll(this);
        GC.SuppressFinalize(this);
    }
}
