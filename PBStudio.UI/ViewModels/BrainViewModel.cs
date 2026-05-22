using System;
using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// Hirn-Stats-Panel + 4-Klick-Feedback (Plan Phase 5).
/// L-FE-7: IDisposable, da AddTransient-Registrierung sonst nach jedem
/// Dialog-Open keinen Dispose-Hook hat -> WeakReferenceMessenger-Subscriptions
/// + Event-Handler bleiben gegen GC liegen.
/// </summary>
public partial class BrainViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly ProjectService? _projectService;
    private readonly TimelineStateService? _timelineState;
    private string? _pendingResetToken;
    private bool _disposed;

    [ObservableProperty] private int _totalClicks;
    [ObservableProperty] private int _coldStartAxes = 17;
    [ObservableProperty] private int _learnedAxes;
    [ObservableProperty] private string _status = "";
    [ObservableProperty] private int _selectedCutId;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isResetPending;

    public ObservableCollection<BrainStatsBucket> TopPositive { get; } = new();
    public ObservableCollection<BrainStatsBucket> TopNegative { get; } = new();
    public ObservableCollection<string> ColdStartAxesList { get; } = new();
    public ObservableCollection<BrainSuggestion> LearningSessionCuts { get; } = new();

    public BrainViewModel(IApiClient api, ProjectService? projectService = null, TimelineStateService? timelineState = null)
    {
        _api = api;
        _projectService = projectService;
        _timelineState = timelineState;
        _ = RefreshStatsAsync();
    }

    [RelayCommand]
    public async Task RefreshStatsAsync()
    {
        IsLoading = true;
        try
        {
            var stats = await _api.BrainStatsAsync();
            if (stats == null)
            {
                Status = "Hirn-Stats nicht verfügbar.";
                return;
            }
            TotalClicks = stats.TotalClicks;
            ColdStartAxes = stats.ColdStartAxes;
            LearnedAxes = stats.LearnedAxes;
            TopPositive.Clear();
            foreach (var b in stats.TopPositive) TopPositive.Add(b);
            TopNegative.Clear();
            foreach (var b in stats.TopNegative) TopNegative.Add(b);
            ColdStartAxesList.Clear();
            if (stats.ColdStartAxesList != null)
            {
                foreach (var ax in stats.ColdStartAxesList) ColdStartAxesList.Add(ax);
            }
            Status = $"{TotalClicks} Klicks gesamt, {LearnedAxes}/{LearnedAxes + ColdStartAxes} Achsen gelernt.";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public Task RatePerfectAsync() => SendFeedbackAsync("perfect");
    [RelayCommand]
    public Task RateFitsAsync() => SendFeedbackAsync("fits");
    [RelayCommand]
    public Task RateNotQuiteAsync() => SendFeedbackAsync("not_quite");
    [RelayCommand]
    public Task RateNoMatchAsync() => SendFeedbackAsync("no_match");

    private async Task SendFeedbackAsync(string rating)
    {
        if (SelectedCutId <= 0)
        {
            Status = "Bitte zuerst einen Cut auswählen.";
            return;
        }
        var cutId = SelectedCutId;
        var resp = await _api.BrainFeedbackAsync(cutId, rating);
        if (resp == null)
        {
            Status = "Feedback fehlgeschlagen.";
            return;
        }
        Status = $"OK — {resp.UpdatedBuckets} Buckets aktualisiert (Total: {resp.TotalClicks}).";
        // Cross-VM-Refresh: TimelineViewModel laedt Confidence + Tooltip fuer diesen Cut neu.
        WeakReferenceMessenger.Default.Send(new BrainFeedbackAppliedMessage(cutId));
        await RefreshStatsAsync();
    }

    [RelayCommand]
    public async Task LoadLearningSessionAsync()
    {
        IsLoading = true;
        try
        {
            var resp = await _api.BrainLearningSessionAsync();
            LearningSessionCuts.Clear();
            if (resp?.Cuts != null)
            {
                foreach (var c in resp.Cuts) LearningSessionCuts.Add(c);
            }
            Status = $"Lern-Session: {LearningSessionCuts.Count} unsichere Cuts geladen.";
        }
        finally
        {
            IsLoading = false;
        }
    }

    [RelayCommand]
    public async Task OpenLearningSessionDialogAsync()
    {
        using (var scope = CommunityToolkit.Mvvm.DependencyInjection.Ioc.Default
            .GetRequiredService<IServiceScopeFactory>().CreateScope())
        {
            var vm = scope.ServiceProvider.GetRequiredService<LearningSessionViewModel>();
            var dialog = new Views.LearningSessionDialog(vm);

            // Pfade aus aktuellem Projekt + Timeline ableiten, sonst bleibt der Walkthrough
            // ohne Audio-/Video-Preview (siehe Audit C3).
            var (audioPath, videoBase) = await ResolveSessionPathsAsync();
            await vm.LoadAsync(audioPath, videoBase);

            dialog.Owner = System.Windows.Application.Current.MainWindow;
            dialog.ShowDialog();
            await RefreshStatsAsync();
        }
    }

    private async Task<(string? audioPath, string? videoBase)> ResolveSessionPathsAsync()
    {
        // Audio: aktuelle Timeline-Response liefert audio_path.
        string? audioPath = _timelineState?.CurrentTimeline?.AudioPath;
        if (string.IsNullOrEmpty(audioPath))
        {
            try
            {
                var refreshed = _timelineState != null
                    ? await _timelineState.RefreshAsync()
                    : await _api.GetTimelineAsync();
                audioPath = refreshed?.AudioPath;
            }
            catch
            {
                // Best-effort — Walkthrough fällt auf "kein Audio" zurück.
            }
        }

        // Video-Base: Projekt-Root\videos\ falls vorhanden, sonst Projekt-Root.
        string? videoBase = null;
        var projectPath = _projectService?.CurrentProjectPath;
        if (!string.IsNullOrEmpty(projectPath))
        {
            var videosDir = System.IO.Path.Combine(projectPath, "videos");
            videoBase = System.IO.Directory.Exists(videosDir) ? videosDir : projectPath;
        }
        return (audioPath, videoBase);
    }

    [RelayCommand]
    public async Task ResetRequestAsync()
    {
        var resp = await _api.BrainResetRequestAsync();
        if (resp?.ConfirmationToken != null)
        {
            _pendingResetToken = resp.ConfirmationToken;
            IsResetPending = true;
            Status = "Reset bestätigen? Klicke nochmal um auszuführen.";
        }
    }

    [RelayCommand]
    public async Task ResetConfirmAsync()
    {
        if (string.IsNullOrEmpty(_pendingResetToken))
        {
            await ResetRequestAsync();
            return;
        }
        var resp = await _api.BrainResetConfirmAsync(_pendingResetToken!);
        _pendingResetToken = null;
        IsResetPending = false;
        Status = resp?.Status == "reset_complete" ? "Hirn-Reset abgeschlossen." : "Reset fehlgeschlagen.";
        await RefreshStatsAsync();
    }

    /// <summary>
    /// L-FE-7: Subscriptions aufloesen damit GC die VM freigeben kann.
    /// AddTransient erzeugt pro Resolve eine neue Instanz; ohne IDisposable
    /// haengt sie an WeakReferenceMessenger-/Event-Listenern fest.
    /// </summary>
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        WeakReferenceMessenger.Default.UnregisterAll(this);
        GC.SuppressFinalize(this);
    }
}
