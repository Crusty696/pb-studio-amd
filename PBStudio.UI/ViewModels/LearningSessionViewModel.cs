using System;
using System.Collections.Concurrent;
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
    private IReadOnlyDictionary<string, string> _projectVideoPaths =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    private bool _disposed;
    private bool _isRating;

    public event Action? RequestClose;
    public event Action<double, double>? PlayRequested;
    public event Action? PauseRequested;
    public event Action<double, double>? RestartRequested;

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
    [ObservableProperty] private bool _isPlaying;

    public string CurrentIndexDisplay => (CurrentIndex + 1).ToString();
    public string PlayPauseLabel => IsPlaying ? "⏸ Pause" : "▶ Play";

    partial void OnIsPlayingChanged(bool value) =>
        OnPropertyChanged(nameof(PlayPauseLabel));

    public LearningSessionViewModel(IApiClient api)
    {
        _api = api;
    }

    public async Task LoadAsync(
        string? audioPath = null,
        IReadOnlyDictionary<string, string>? videoPaths = null)
    {
        _projectAudioPath = audioPath;
        _projectVideoPaths = videoPaths
            ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
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

        // Medienpfade stammen aus dem Projektkatalog und werden lokal validiert.
        CurrentVideoUri = ResolveVideoUri(c.ClipId);
        CurrentAudioUri = LocalMediaPathPolicy.TryCreateFileUri(
            _projectAudioPath,
            out var audioUri)
            ? audioUri
            : null;
        IsPlaying = false;

        Status = $"Cut {CurrentIndex + 1}/{TotalCount}: {c.ClipId} @ {c.StartTime:F2}s";
        OnPropertyChanged(nameof(CurrentIndexDisplay));
        NotifyRatingCommandsCanExecuteChanged();
    }

    private Uri? ResolveVideoUri(string? clipId)
    {
        if (string.IsNullOrEmpty(clipId)
            || !_projectVideoPaths.TryGetValue(clipId, out var path))
            return null;
        return LocalMediaPathPolicy.TryCreateFileUri(path, out var videoUri)
            ? videoUri
            : null;
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

    [RelayCommand(CanExecute = nameof(CanRateCurrentCut))]
    public Task RatePerfectAsync() => RateAsync("perfect");
    [RelayCommand(CanExecute = nameof(CanRateCurrentCut))]
    public Task RateFitsAsync() => RateAsync("fits");
    [RelayCommand(CanExecute = nameof(CanRateCurrentCut))]
    public Task RateNotQuiteAsync() => RateAsync("not_quite");
    [RelayCommand(CanExecute = nameof(CanRateCurrentCut))]
    public Task RateNoMatchAsync() => RateAsync("no_match");

    private async Task RateAsync(string rating)
    {
        if (_disposed || _cuts.Count == 0)
            return;
        var c = _cuts[CurrentIndex];
        var ratedIndex = CurrentIndex;
        var cutId = c.CutId;
        if (cutId == null)
        {
            Status = "Kein cut_id verfügbar.";
            return;
        }
        if (!CutRatingGate.TryEnter(cutId.Value))
            return;

        SetRatingState(true);
        try
        {
            var resp = await _api.BrainFeedbackAsync(cutId.Value, rating);
            if (_disposed || CurrentIndex != ratedIndex || CurrentCutId != cutId.Value)
                return;
            if (resp == null)
            {
                Status = "Feedback fehlgeschlagen.";
                return;
            }
            if (!string.Equals(resp.Status, "ok", StringComparison.OrdinalIgnoreCase))
            {
                Status = resp.Message ?? "Feedback wurde abgelehnt.";
                return;
            }
            Status = $"OK — {resp.UpdatedBuckets} buckets, total={resp.TotalClicks}. → next";
            // Cross-VM-Refresh: TimelineViewModel laedt Confidence + Tooltip fuer diesen Cut neu.
            WeakReferenceMessenger.Default.Send(new BrainFeedbackAppliedMessage(cutId.Value));
            Next();
        }
        finally
        {
            SetRatingState(false);
            CutRatingGate.Exit(cutId.Value);
        }
    }

    private bool CanRateCurrentCut() =>
        !_disposed && !_isRating && CurrentCutId > 0;

    private void SetRatingState(bool value)
    {
        _isRating = value;
        NotifyRatingCommandsCanExecuteChanged();
    }

    private void NotifyRatingCommandsCanExecuteChanged()
    {
        RatePerfectCommand.NotifyCanExecuteChanged();
        RateFitsCommand.NotifyCanExecuteChanged();
        RateNotQuiteCommand.NotifyCanExecuteChanged();
        RateNoMatchCommand.NotifyCanExecuteChanged();
    }

    [RelayCommand]
    public void PlayPause()
    {
        if (IsPlaying)
        {
            PauseRequested?.Invoke();
            IsPlaying = false;
            return;
        }

        IsPlaying = true;
        PlayRequested?.Invoke(CurrentStartTime, CurrentEndTime);
    }

    // B5-Fix (2026-05-19): PauseRequested event wurde in Dispose auf null gesetzt
    // (line 177) aber nie raised → CS0414. Explizite Pause()-Methode komplettiert
    // das Play/Pause/Restart-Event-Trio, LearningSessionDialog hat den Subscriber
    // bereits (LearningSessionDialog.xaml.cs:22).
    [RelayCommand]
    public void Pause()
    {
        PauseRequested?.Invoke();
        IsPlaying = false;
    }

    [RelayCommand]
    public void Restart()
    {
        IsPlaying = true;
        RestartRequested?.Invoke(CurrentStartTime, CurrentEndTime);
    }

    public void NotifyPlaybackCompleted()
    {
        IsPlaying = false;
        Status = $"Cut {CurrentIndex + 1}/{TotalCount} abgespielt.";
    }

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

internal static class CutRatingGate
{
    private static readonly ConcurrentDictionary<int, byte> ActiveCuts = new();

    public static bool TryEnter(int cutId) => ActiveCuts.TryAdd(cutId, 0);

    public static void Exit(int cutId) => ActiveCuts.TryRemove(cutId, out _);
}
