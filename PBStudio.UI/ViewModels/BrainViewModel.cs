using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// Hirn-Stats-Panel + 4-Klick-Feedback (Plan Phase 5).
/// </summary>
public partial class BrainViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private string? _pendingResetToken;

    [ObservableProperty] private int _totalClicks;
    [ObservableProperty] private int _coldStartAxes = 17;
    [ObservableProperty] private int _learnedAxes;
    [ObservableProperty] private string _status = "";
    [ObservableProperty] private int _selectedCutId;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isResetPending;

    public ObservableCollection<BrainStatsBucket> TopPositive { get; } = new();
    public ObservableCollection<BrainStatsBucket> TopNegative { get; } = new();
    public ObservableCollection<BrainSuggestion> LearningSessionCuts { get; } = new();

    public BrainViewModel(IApiClient api)
    {
        _api = api;
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
        var resp = await _api.BrainFeedbackAsync(SelectedCutId, rating);
        if (resp == null)
        {
            Status = "Feedback fehlgeschlagen.";
            return;
        }
        Status = $"OK — {resp.UpdatedBuckets} Buckets aktualisiert (Total: {resp.TotalClicks}).";
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
        var vm = CommunityToolkit.Mvvm.DependencyInjection.Ioc.Default
            .GetRequiredService<LearningSessionViewModel>();
        var dialog = new Views.LearningSessionDialog(vm);
        await vm.LoadAsync();
        dialog.Owner = System.Windows.Application.Current.MainWindow;
        dialog.ShowDialog();
        await RefreshStatsAsync();
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
}
