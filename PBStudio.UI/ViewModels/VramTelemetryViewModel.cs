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
/// Zeigt pro <c>model_id</c> Aggregate (count / success / failure / avg+peak duration / avg+peak VRAM)
/// plus zwei einfache Histogramme (Duration in ms, VRAM-Peak in MB).
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

        // Vorherigen Lauf abbrechen, neuen Token aufsetzen.
        _loadCts?.Cancel();
        _loadCts = new CancellationTokenSource();
        var token = _loadCts.Token;

        IsLoading = true;
        try
        {
            var resp = await _api.GetVramTelemetryAsync(modelId: null, ct: token).ConfigureAwait(true);
            if (token.IsCancellationRequested) return;

            if (resp?.Telemetry == null)
            {
                StatusText = "VRAM-Telemetrie nicht verfügbar.";
                return;
            }

            var summary = resp.Telemetry.Summary;
            var modelsDict = resp.Telemetry.Models ?? new Dictionary<string, VramTelemetryEntry>();

            ModelsTracked = summary?.ModelsTracked ?? modelsDict.Count;
            TotalObservations = summary?.Observations ?? modelsDict.Values.Sum(m => m.Count);
            TotalSuccess = summary?.Success ?? modelsDict.Values.Sum(m => m.SuccessCount);
            TotalFailure = summary?.Failure ?? modelsDict.Values.Sum(m => m.FailureCount);
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
            IsLoading = false;
        }
    }

    /// <summary>
    /// Übernimmt die Budget-Felder aus <c>resp.Budget</c> (VRAMBudgetManager.get_stats).
    /// Setzt <see cref="HasBudget"/> auf false wenn das Backend keine Budget-Daten lieferte
    /// (z.B. wenn der VRAM-Manager nicht verfügbar ist).
    /// </summary>
    private void ApplyBudget(IReadOnlyDictionary<string, System.Text.Json.JsonElement>? budget)
    {
        if (budget == null || budget.Count == 0)
        {
            HasBudget = false;
            return;
        }

        BudgetMaxMb = ReadInt(budget, "max_vram_mb");
        BudgetUsableMb = ReadInt(budget, "usable_vram_mb");
        BudgetReservedMb = ReadInt(budget, "reserved_mb");
        BudgetCommittedMb = ReadInt(budget, "committed_mb");
        BudgetAvailableMb = ReadInt(budget, "available_mb");
        BudgetLoadedModels = ReadInt(budget, "loaded_models");
        BudgetReservedModels = ReadInt(budget, "reserved_models");
        // Safety-Reserve = Hardware-VRAM minus nutzbares Budget.
        BudgetSafetyMb = Math.Max(0, BudgetMaxMb - BudgetUsableMb);
        BudgetUsedPercent = BudgetUsableMb > 0
            ? Math.Min(100.0, (double)BudgetCommittedMb / BudgetUsableMb * 100.0)
            : 0.0;
        HasBudget = BudgetMaxMb > 0 || BudgetUsableMb > 0;
    }

    private static int ReadInt(IReadOnlyDictionary<string, System.Text.Json.JsonElement> dict, string key)
    {
        if (!dict.TryGetValue(key, out var el)) return 0;
        return el.ValueKind switch
        {
            System.Text.Json.JsonValueKind.Number => el.TryGetInt32(out var i) ? i : (int)Math.Round(el.GetDouble()),
            System.Text.Json.JsonValueKind.String => int.TryParse(el.GetString(), out var s) ? s : 0,
            _ => 0,
        };
    }

    /// <summary>
    /// Synchronisiert die Cards mit dem aktuellen Backend-Snapshot. Bestehende Cards werden
    /// in-place aktualisiert, neue hinzugefügt, entfallene rausgeworfen — damit das ItemsControl
    /// nicht bei jedem Refresh komplett neu gebaut wird.
    /// </summary>
    private void ApplyModelEntries(IReadOnlyDictionary<string, VramTelemetryEntry> entries)
    {
        // Sortierung: höchste Beobachtungszahl zuerst, danach alphabetisch.
        var sorted = entries
            .OrderByDescending(kv => kv.Value.Count)
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
    [ObservableProperty] private string _lastObservedText = "nie";
    [ObservableProperty] private string? _lastErrorText;
    [ObservableProperty] private bool _hasError;

    public ObservableCollection<VramHistogramBar> DurationHistogram { get; } = new();
    public ObservableCollection<VramHistogramBar> VramHistogram { get; } = new();

    public VramTelemetryModelCardViewModel(VramTelemetryEntry entry)
    {
        ModelId = entry.ModelId;
        Update(entry);
    }

    public void Update(VramTelemetryEntry entry)
    {
        Count = entry.Count;
        SuccessCount = entry.SuccessCount;
        FailureCount = entry.FailureCount;

        DurationSummary = FormatDurationSummary(entry.DurationMs);
        VramSummary = FormatVramSummary(entry.VramPeakMb);
        LastObservedText = FormatTimestamp(entry.LastObservedAt);
        LastErrorText = ExtractErrorMessage(entry.LastError);
        HasError = !string.IsNullOrWhiteSpace(LastErrorText);

        ReplaceBars(DurationHistogram, entry.DurationMs?.Histogram);
        ReplaceBars(VramHistogram, entry.VramPeakMb?.Histogram);
    }

    private static void ReplaceBars(ObservableCollection<VramHistogramBar> target,
                                    IReadOnlyDictionary<string, int>? histogram)
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
        return $"avg {stats.Avg:F1} ms · peak {max:F0} ms · min {min:F0} ms";
    }

    private static string FormatVramSummary(VramPeakStats? stats)
    {
        if (stats == null) return "—";
        var min = stats.Min ?? 0.0;
        var max = stats.Max ?? 0.0;
        return $"avg {stats.Avg:F0} MB · peak {max:F0} MB · min {min:F0} MB";
    }

    private static string FormatTimestamp(double? unixSeconds)
    {
        if (unixSeconds == null) return "nie";
        try
        {
            var ts = DateTimeOffset.FromUnixTimeMilliseconds((long)(unixSeconds.Value * 1000.0)).LocalDateTime;
            return ts.ToString("HH:mm:ss");
        }
        catch
        {
            return "—";
        }
    }

    private static string? ExtractErrorMessage(IReadOnlyDictionary<string, System.Text.Json.JsonElement>? error)
    {
        if (error == null || error.Count == 0) return null;
        // Bevorzugt "message" oder "type", sonst die ersten zwei key=value Paare.
        if (error.TryGetValue("message", out var msg))
            return msg.ValueKind == System.Text.Json.JsonValueKind.String ? msg.GetString() : msg.ToString();
        if (error.TryGetValue("type", out var type))
            return type.ValueKind == System.Text.Json.JsonValueKind.String ? type.GetString() : type.ToString();
        return string.Join(", ", error.Take(2).Select(kv => $"{kv.Key}={kv.Value}"));
    }
}

/// <summary>Ein einzelner Balken im Histogram (Bucket-Label, Anzahl, gerenderte Breite).</summary>
public record VramHistogramBar(string Label, int Count, double BarWidth);
