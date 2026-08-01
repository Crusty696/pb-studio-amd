using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

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
    private int _statsLoadVersion;
    private int _learningLoadVersion;
    private int _loadingVersion;
    private int _feedbackVersion;

    [ObservableProperty] private int _totalClicks;
    [ObservableProperty] private int _coldStartAxes = 17;
    [ObservableProperty] private int _learnedAxes;
    [ObservableProperty] private string _status = "";
    [ObservableProperty] private int _selectedCutId;
    [ObservableProperty] private BrainSuggestion? _selectedLearningSessionCut;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isResetPending;

    public ObservableCollection<BrainStatsBucket> TopPositive { get; } = new();
    public ObservableCollection<BrainStatsBucket> TopNegative { get; } = new();
    public ObservableCollection<string> ColdStartAxesList { get; } = new();
    public ObservableCollection<BrainSuggestion> LearningSessionCuts { get; } = new();

    partial void OnSelectedLearningSessionCutChanged(BrainSuggestion? value)
    {
        SelectedCutId = value?.CutId ?? 0;
    }

    public BrainViewModel(IApiClient api, ProjectService? projectService = null, TimelineStateService? timelineState = null)
    {
        _api = api;
        _projectService = projectService;
        _timelineState = timelineState;
        if (_projectService != null)
            _projectService.ProjectTransitionStarted += OnProjectTransitionStarted;
        _ = RefreshStatsAsync();

        // Audit-Fix 2026-07-10 (Sweep-Finding HIGH-11): BrainViewModel abonnierte
        // weder ProjectOpenedMessage noch ProjectClosedMessage, obwohl Backend den
        // Brain-State pro Projekt bindet/entbindet — Tab zeigte Confidence/
        // Suggestions vom vorherigen Projekt bis zum manuellen Reload. Muster
        // uebernommen von TimelineViewModel.
        // AUDIT-FIX C#-1: Messages koennen vom Background-Thread gesendet werden (ProjectService).
        // RefreshStatsAsync/ResetForProjectClose mutieren an die UI gebundene ObservableCollections
        // → auf den Dispatcher marshallen, sonst NotSupportedException (Cross-Thread-Collection).
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(() => _ = RefreshStatsAsync()));
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetForProjectClose));
    }

    /// <summary>Setzt alle projektgebundenen Anzeigen auf Leerzustand zurueck (Audit-Fix 2026-07-10).</summary>
    private void ResetForProjectClose()
    {
        Interlocked.Increment(ref _statsLoadVersion);
        Interlocked.Increment(ref _learningLoadVersion);
        Interlocked.Increment(ref _loadingVersion);
        Interlocked.Increment(ref _feedbackVersion);
        IsLoading = false;
        TotalClicks = 0;
        ColdStartAxes = 17;
        LearnedAxes = 0;
        TopPositive.Clear();
        TopNegative.Clear();
        ColdStartAxesList.Clear();
        LearningSessionCuts.Clear();
        SelectedLearningSessionCut = null;
        SelectedCutId = 0;
        IsResetPending = false;
        _pendingResetToken = null;
        Status = "Kein Projekt geladen.";
    }

    private void OnProjectTransitionStarted(object? sender, EventArgs e)
    {
        Interlocked.Increment(ref _statsLoadVersion);
        Interlocked.Increment(ref _learningLoadVersion);
        Interlocked.Increment(ref _loadingVersion);
        Interlocked.Increment(ref _feedbackVersion);
        IsLoading = false;
    }

    [RelayCommand]
    public async Task RefreshStatsAsync()
    {
        if (_disposed)
            return;

        var statsVersion = Interlocked.Increment(ref _statsLoadVersion);
        var loadVersion = Interlocked.Increment(ref _loadingVersion);
        IsLoading = true;
        try
        {
            var stats = await _api.BrainStatsAsync();
            if (_disposed || statsVersion != Volatile.Read(ref _statsLoadVersion))
                return;

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
            if (!_disposed && loadVersion == Volatile.Read(ref _loadingVersion))
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
        var feedbackVersion = Interlocked.Increment(ref _feedbackVersion);
        var resp = await _api.BrainFeedbackAsync(cutId, rating);
        if (_disposed || feedbackVersion != Volatile.Read(ref _feedbackVersion))
            return;
        if (resp == null)
        {
            Status = "Feedback fehlgeschlagen.";
            return;
        }
        if (!resp.Status.Equals("ok", StringComparison.OrdinalIgnoreCase))
        {
            Status = string.IsNullOrWhiteSpace(resp.Message)
                ? "Feedback wurde nicht angewendet."
                : resp.Message;
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
        if (_disposed)
            return;

        var learningVersion = Interlocked.Increment(ref _learningLoadVersion);
        var loadVersion = Interlocked.Increment(ref _loadingVersion);
        IsLoading = true;
        try
        {
            var resp = await _api.BrainLearningSessionAsync();
            if (_disposed || learningVersion != Volatile.Read(ref _learningLoadVersion))
                return;

            LearningSessionCuts.Clear();
            if (resp?.Cuts != null)
            {
                foreach (var c in resp.Cuts) LearningSessionCuts.Add(c);
            }
            SelectedLearningSessionCut = LearningSessionCuts.FirstOrDefault();
            Status = $"Lern-Session: {LearningSessionCuts.Count} unsichere Cuts geladen.";
        }
        finally
        {
            if (!_disposed && loadVersion == Volatile.Read(ref _loadingVersion))
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
            var (audioPath, videoPaths) = await ResolveSessionPathsAsync();
            await vm.LoadAsync(audioPath, videoPaths);

            dialog.Owner = System.Windows.Application.Current.MainWindow;
            dialog.ShowDialog();
            await RefreshStatsAsync();
        }
    }

    private async Task<(
        string? audioPath,
        IReadOnlyDictionary<string, string> videoPaths)> ResolveSessionPathsAsync()
    {
        var timeline = _timelineState?.CurrentTimeline;
        if (timeline == null)
        {
            try
            {
                timeline = _timelineState != null
                    ? await _timelineState.RefreshAsync()
                    : await _api.GetTimelineAsync();
            }
            catch
            {
                // Best-effort -- Walkthrough remains available without preview.
            }
        }

        var videoPaths = new Dictionary<string, string>(
            StringComparer.OrdinalIgnoreCase);
        if (timeline?.Entries != null)
        {
            foreach (var entry in timeline.Entries)
            {
                if (!string.IsNullOrWhiteSpace(entry.ClipId)
                    && !string.IsNullOrWhiteSpace(entry.FilePath))
                {
                    videoPaths[entry.ClipId] = entry.FilePath;
                }
            }
        }
        return (timeline?.AudioPath, videoPaths);
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
        Interlocked.Increment(ref _statsLoadVersion);
        Interlocked.Increment(ref _learningLoadVersion);
        Interlocked.Increment(ref _loadingVersion);
        Interlocked.Increment(ref _feedbackVersion);
        if (_projectService != null)
            _projectService.ProjectTransitionStarted -= OnProjectTransitionStarted;
        WeakReferenceMessenger.Default.UnregisterAll(this);
        GC.SuppressFinalize(this);
    }
}
