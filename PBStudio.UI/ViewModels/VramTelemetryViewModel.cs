using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel für das VRAM-Telemetry-Panel.
///
/// Zeigt pro <c>model_id</c> Aggregate (count / success / failure / avg+peak duration / peak VRAM)
/// plus zwei einfache Histogramme (Duration in ms, VRAM-Peak in MB).
///
/// T5c (S-H1b Audit V2 2026-05-19): Migration auf NSwag-generated DTOs.
/// Backend response_model = VramHealthResponse (Budget + Telemetry.Models/Summary).
/// Property-Namen sind snake-preserving (Model_id, Duration_ms, Vram_peak_mb, ...).
/// Backend liefert kein LastObservedAt mehr und kein Avg auf VramPeakStats —
/// VM zeigt diese Felder einfach nicht mehr.
///
/// Auto-Refresh via <see cref="DispatcherTimer"/> (Interval ~5s) ist nur aktiv solange
/// <see cref="IsActive"/> wahr ist — die View setzt das Flag im Loaded/Unloaded-Event.
/// </summary>
public partial class VramTelemetryViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly ILogger<VramTelemetryViewModel>? _logger;
    private readonly DispatcherTimer _refreshTimer;
    private CancellationTokenSource? _loadCts;
    private bool _disposed;

    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isActive;
    [ObservableProperty] private string _statusText = "Noch nicht geladen.";
    [ObservableProperty] private int _modelsTracked;
    [ObservableProperty] private int _totalObservations;
    [ObservableProperty] private int _totalSuccess;
    [ObservableProperty] private int _totalFailure;
    [ObservableProperty] private DateTime? _lastFetchedAt;

    // VRAM-Budget-Snapshot aus VRAMBudgetManager.get_stats() (Backend /health/vram).
    [ObservableProperty] private bool _hasBudget;
    [ObservableProperty] private int _budgetMaxMb;
    [ObservableProperty] private int _budgetUsableMb;
    [ObservableProperty] private int _budgetReservedMb;
    [ObservableProperty] private int _budgetCommittedMb;
    [ObservableProperty] private int _budgetAvailableMb;
    [ObservableProperty] private int _budgetSafetyMb;
    [ObservableProperty] private int _budgetLoadedModels;
    [ObservableProperty] private int _budgetReservedModels;
    [ObservableProperty] private double _budgetUsedPercent;

    /// <summary>Karten pro <c>model_id</c> für das Item-Repeater-Binding.</summary>
    public ObservableCollection<VramTelemetryModelCardViewModel> Models { get; } = new();

    public VramTelemetryViewModel(IApiClient api, ILogger<VramTelemetryViewModel>? logger = null)
    {
        _api = api;
        _logger = logger;

        _refreshTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(5),
        };
        _refreshTimer.Tick += OnRefreshTick;
    }

    /// <summary>
    /// Wird von der View über Loaded/Unloaded gesteuert. Aktiviert/deaktiviert den Auto-Refresh-Timer.
    /// </summary>
    partial void OnIsActiveChanged(bool value)
    {
        if (value)
        {
            _refreshTimer.Start();
            _ = LoadAsync();
        }
        else
        {
            _refreshTimer.Stop();
            _loadCts?.Cancel();
        }
    }

    private async void OnRefreshTick(object? sender, EventArgs e)
    {
        if (!IsActive) return;
        await LoadAsync().ConfigureAwait(false);
    }

    [RelayCommand]
    public Task RefreshAsync() => LoadAsync();

    public async Task LoadAsync()
    {
        if (_disposed) return;

        // Vorherigen Lauf abbrechen; jede Ausführung besitzt und disposed ihre CTS.
        var previous = _loadCts;
        var current = new CancellationTokenSource();
        _loadCts = current;
        previous?.Cancel();
        var token = current.Token;

        IsLoading = true;
        try
        {
            var resp = await _api.GetVramTelemetryAsync(modelId: null, ct: token).ConfigureAwait(true);
            if (token.IsCancellationRequested) return;

            if (resp == null)
            {
                StatusText = "VRAM-Telemetrie nicht verfügbar.";
                return;
            }

            var summary = resp.Telemetry?.Summary;
            var modelsDict = resp.Telemetry?.Models ?? new Dictionary<string, VramTelemetryEntry>();

            ModelsTracked = summary?.Models_tracked ?? modelsDict.Count;
            TotalObservations = summary?.Observations ?? modelsDict.Values.Sum(m => m.Count ?? 0);
            // T5c: Backend-Summary liefert success/failure nicht mehr — aus Per-Model-Aggregaten errechnen.
            TotalSuccess = modelsDict.Values.Sum(m => m.Success_count ?? 0);
            TotalFailure = modelsDict.Values.Sum(m => m.Failure_count ?? 0);
            LastFetchedAt = DateTime.Now;

            ApplyBudget(resp.Budget);
            ApplyModelEntries(modelsDict);

            StatusText = ModelsTracked == 0
                ? "Noch keine GPU-Tasks beobachtet."
                : $"{ModelsTracked} Modelle, {TotalObservations} Beobachtungen ({TotalSuccess} ok, {TotalFailure} Fehler).";
        }
        catch (OperationCanceledException)
        {
            // Erwarteter Pfad bei IsActive=false oder Reload.
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "VRAM-Telemetry laden fehlgeschlagen");
            StatusText = $"Fehler beim Laden: {ex.Message}";
        }
        finally
        {
            if (ReferenceEquals(_loadCts, current))
            {
                _loadCts = null;
                if (!_disposed)
                    IsLoading = false;
            }
            current.Dispose();
        }
    }

    /// <summary>
    /// Übernimmt die Budget-Felder aus <c>resp.Budget</c> (VRAMBudgetManager.get_stats).
    /// Setzt <see cref="HasBudget"/> auf false wenn das Backend keine Budget-Daten lieferte
    /// (z.B. wenn der VRAM-Manager nicht verfügbar ist).
    /// </summary>
    private void ApplyBudget(VramBudgetStats? budget)
    {
        if (budget == null)
        {
            HasBudget = false;
            return;
        }

        BudgetMaxMb = (int)Math.Round(budget.Max_vram_mb);
        BudgetUsableMb = (int)Math.Round(budget.Usable_vram_mb);
        BudgetReservedMb = (int)Math.Round(budget.Reserved_mb);
        BudgetCommittedMb = (int)Math.Round(budget.Committed_mb);
        BudgetAvailableMb = (int)Math.Round(budget.Available_mb);
        BudgetLoadedModels = budget.Loaded_models;
        BudgetReservedModels = budget.Reserved_models;
        // Safety-Reserve = Hardware-VRAM minus nutzbares Budget.
        BudgetSafetyMb = Math.Max(0, BudgetMaxMb - BudgetUsableMb);
        BudgetUsedPercent = BudgetUsableMb > 0
            ? Math.Min(100.0, (double)BudgetCommittedMb / BudgetUsableMb * 100.0)
            : 0.0;
        HasBudget = BudgetMaxMb > 0 || BudgetUsableMb > 0;
    }

    /// <summary>
    /// Synchronisiert die Cards mit dem aktuellen Backend-Snapshot. Bestehende Cards werden
    /// in-place aktualisiert, neue hinzugefügt, entfallene rausgeworfen — damit das ItemsControl
    /// nicht bei jedem Refresh komplett neu gebaut wird.
    /// </summary>
    private void ApplyModelEntries(IDictionary<string, VramTelemetryEntry> entries)
    {
        // Sortierung: höchste Beobachtungszahl zuerst, danach alphabetisch.
        var sorted = entries
            .OrderByDescending(kv => kv.Value.Count ?? 0)
            .ThenBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase)
            .ToList();

        // Fehlende Modelle entfernen.
        var keepKeys = sorted.Select(kv => kv.Key).ToHashSet(StringComparer.Ordinal);
        for (int i = Models.Count - 1; i >= 0; i--)
        {
            if (!keepKeys.Contains(Models[i].ModelId))
                Models.RemoveAt(i);
        }

        // Hinzufügen / aktualisieren.
        for (int targetIndex = 0; targetIndex < sorted.Count; targetIndex++)
        {
            var (key, entry) = sorted[targetIndex];
            var existing = Models.FirstOrDefault(m => m.ModelId == key);
            if (existing == null)
            {
                Models.Insert(targetIndex, new VramTelemetryModelCardViewModel(entry));
            }
            else
            {
                existing.Update(entry);
                int currentIndex = Models.IndexOf(existing);
                if (currentIndex != targetIndex)
                    Models.Move(currentIndex, targetIndex);
            }
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _refreshTimer.Stop();
        _refreshTimer.Tick -= OnRefreshTick;
        _loadCts?.Cancel();
        _loadCts?.Dispose();
    }
}

/// <summary>Eine Telemetry-Karte pro <c>model_id</c>.</summary>
public partial class VramTelemetryModelCardViewModel : ObservableObject
{
    public string ModelId { get; }

    [ObservableProperty] private int _count;
    [ObservableProperty] private int _successCount;
    [ObservableProperty] private int _failureCount;
    [ObservableProperty] private string _durationSummary = "—";
    [ObservableProperty] private string _vramSummary = "—";
    [ObservableProperty] private string? _lastErrorText;
    [ObservableProperty] private bool _hasError;

    public ObservableCollection<VramHistogramBar> DurationHistogram { get; } = new();
    public ObservableCollection<VramHistogramBar> VramHistogram { get; } = new();

    public VramTelemetryModelCardViewModel(VramTelemetryEntry entry)
    {
        ModelId = entry.Model_id;
        Update(entry);
    }

    public void Update(VramTelemetryEntry entry)
    {
        Count = entry.Count ?? 0;
        SuccessCount = entry.Success_count ?? 0;
        FailureCount = entry.Failure_count ?? 0;

        DurationSummary = FormatDurationSummary(entry.Duration_ms);
        VramSummary = FormatVramSummary(entry.Vram_peak_mb);
        LastErrorText = ExtractErrorMessage(entry.Last_error);
        HasError = !string.IsNullOrWhiteSpace(LastErrorText);

        ReplaceBars(DurationHistogram, entry.Duration_ms?.Histogram);
        ReplaceBars(VramHistogram, entry.Vram_peak_mb?.Histogram);
    }

    private static void ReplaceBars(ObservableCollection<VramHistogramBar> target,
                                    IDictionary<string, int>? histogram)
    {
        target.Clear();
        if (histogram == null || histogram.Count == 0) return;

        // Maximum für relative Skalierung (mind. 1 um Division durch 0 zu vermeiden).
        var max = Math.Max(1, histogram.Values.DefaultIfEmpty(0).Max());
        const double maxBarWidth = 180.0;

        foreach (var kv in histogram)
        {
            var width = kv.Value <= 0 ? 0.0 : Math.Max(1.0, (double)kv.Value / max * maxBarWidth);
            target.Add(new VramHistogramBar(kv.Key, kv.Value, width));
        }
    }

    private static string FormatDurationSummary(VramDurationStats? stats)
    {
        if (stats == null) return "—";
        var min = stats.Min ?? 0.0;
        var max = stats.Max ?? 0.0;
        var avg = stats.Avg ?? 0.0;
        return $"avg {avg:F1} ms · peak {max:F0} ms · min {min:F0} ms";
    }

    private static string FormatVramSummary(VramPeakStats? stats)
    {
        if (stats == null) return "—";
        var min = stats.Min ?? 0.0;
        var max = stats.Max ?? 0.0;
        // T5c: Backend liefert kein Avg auf VramPeakStats (TelemetryEntry.to_dict()
        // expliziert nur min/max/histogram für vram_peak_mb).
        return $"peak {max:F0} MB · min {min:F0} MB";
    }

    private static string? ExtractErrorMessage(object? error)
    {
        // T5c: Backend liefert last_error jetzt als generic dict[str, Any] (object?).
        // Common pattern: {message: "...", type: "..."}. Wir extrahieren message bevorzugt.
        if (error == null) return null;
        try
        {
            var json = error is System.Text.Json.JsonElement el
                ? el
                : System.Text.Json.JsonSerializer.SerializeToElement(error);
            if (json.ValueKind != System.Text.Json.JsonValueKind.Object) return null;
            if (json.TryGetProperty("message", out var msg))
                return msg.ValueKind == System.Text.Json.JsonValueKind.String ? msg.GetString() : msg.ToString();
            if (json.TryGetProperty("type", out var type))
                return type.ValueKind == System.Text.Json.JsonValueKind.String ? type.GetString() : type.ToString();
            return json.ToString();
        }
        catch
        {
            return null;
        }
    }
}

/// <summary>Ein einzelner Balken im Histogram (Bucket-Label, Anzahl, gerenderte Breite).</summary>
public record VramHistogramBar(string Label, int Count, double BarWidth);
