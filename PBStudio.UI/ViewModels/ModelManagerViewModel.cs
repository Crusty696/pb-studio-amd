using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel fuer den MODELLE-Tab (Ollama Vision-Modelle).
/// Zeigt zwei Listen: installierte Modelle (mit Delete-Button) und kuratierte Verfuegbare
/// (mit Download-Button + Progress-Dialog). Nutzt <see cref="IApiClient"/>-Endpoints
/// <c>/models/list</c>, <c>/models/available</c>, <c>/models/pull</c>, <c>/models/{name}</c>.
/// </summary>
public partial class ModelManagerViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly ILogger<ModelManagerViewModel>? _logger;
    private CancellationTokenSource? _loadCts;
    private bool _disposed;

    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isActive;
    [ObservableProperty] private string _statusText = "Modelle werden geladen...";
    [ObservableProperty] private string? _errorText;
    [ObservableProperty] private string _baseUrl = "";
    [ObservableProperty] private bool _ollamaAvailable;
    [ObservableProperty] private DateTime? _lastFetchedAt;

    public ObservableCollection<InstalledModelCardViewModel> InstalledModels { get; } = new();
    public ObservableCollection<AvailableModelCardViewModel> AvailableModels { get; } = new();

    public ModelManagerViewModel(IApiClient api, ILogger<ModelManagerViewModel>? logger = null)
    {
        _api = api;
        _logger = logger;
    }

    /// <summary>Wird von der View ueber Loaded/Unloaded gesteuert. Triggert initialen Load.</summary>
    partial void OnIsActiveChanged(bool value)
    {
        if (value)
            _ = LoadAsync();
        else
            _loadCts?.Cancel();
    }

    [RelayCommand]
    public Task RefreshAsync() => LoadAsync();

    public async Task LoadAsync()
    {
        if (_disposed) return;

        _loadCts?.Cancel();
        _loadCts = new CancellationTokenSource();
        var token = _loadCts.Token;

        IsLoading = true;
        ErrorText = null;
        try
        {
            // Parallel installiert + verfuegbar laden — spart ~50% Wartezeit.
            var installedTask = _api.GetInstalledModelsAsync(token);
            var availableTask = _api.GetAvailableModelsAsync(token);
            await Task.WhenAll(installedTask, availableTask).ConfigureAwait(true);

            if (token.IsCancellationRequested) return;

            var installed = await installedTask.ConfigureAwait(true);
            var available = await availableTask.ConfigureAwait(true);

            ApplyInstalled(installed);
            ApplyAvailable(available);

            OllamaAvailable = (installed?.OllamaAvailable ?? false) || (available?.OllamaAvailable ?? false);
            BaseUrl = installed?.BaseUrl ?? available?.BaseUrl ?? "";
            LastFetchedAt = DateTime.Now;

            if (!OllamaAvailable)
            {
                var err = installed?.Error ?? "Ollama-Server nicht erreichbar.";
                StatusText = $"Ollama offline ({BaseUrl}): {err}";
                ErrorText = err;
            }
            else
            {
                StatusText = $"{InstalledModels.Count} installiert  ·  {AvailableModels.Count} verfuegbar  ·  Ollama @ {BaseUrl}";
            }
        }
        catch (OperationCanceledException) { /* erwartet */ }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "ModelManager Load fehlgeschlagen");
            ErrorText = ex.Message;
            StatusText = "Modelle konnten nicht geladen werden.";
        }
        finally
        {
            IsLoading = false;
        }
    }

    private void ApplyInstalled(ModelListResponse? resp)
    {
        InstalledModels.Clear();
        if (resp?.Models is null) return;
        foreach (var entry in resp.Models.OrderBy(m => m.Name, StringComparer.OrdinalIgnoreCase))
            InstalledModels.Add(new InstalledModelCardViewModel(entry, this));
    }

    private void ApplyAvailable(AvailableModelsResponse? resp)
    {
        AvailableModels.Clear();
        if (resp?.Available is null) return;
        // Reihenfolge: Speed → Balance → Quality, innerhalb nach Groesse aufsteigend.
        var modeOrder = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase)
        {
            ["speed"] = 0, ["balance"] = 1, ["quality"] = 2,
        };
        foreach (var entry in resp.Available
            .OrderBy(e => modeOrder.TryGetValue(e.SuggestedMode, out var v) ? v : 99)
            .ThenBy(e => e.SizeEstimateGb))
        {
            AvailableModels.Add(new AvailableModelCardViewModel(entry, this));
        }
    }

    /// <summary>Wird von einer InstalledModelCard aufgerufen.</summary>
    internal async Task DeleteInstalledAsync(InstalledModelCardViewModel card)
    {
        var confirm = MessageBox.Show(
            $"Modell '{card.Name}' wirklich loeschen?\n\nDie Dateien werden vom Ollama-Server entfernt.",
            "Modell loeschen",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirm != MessageBoxResult.Yes) return;

        card.IsBusy = true;
        try
        {
            var ok = await _api.DeleteModelAsync(card.Name).ConfigureAwait(true);
            if (ok)
                StatusText = $"Modell '{card.Name}' geloescht.";
            else
                ErrorText = $"Loeschen fehlgeschlagen fuer '{card.Name}'.";
        }
        finally
        {
            card.IsBusy = false;
        }
        await LoadAsync().ConfigureAwait(true);
    }

    /// <summary>Wird von einer AvailableModelCard aufgerufen. Oeffnet Progress-Dialog.</summary>
    internal async Task DownloadAvailableAsync(AvailableModelCardViewModel card)
    {
        if (card.Installed)
        {
            MessageBox.Show($"'{card.Name}' ist bereits installiert.", "PB Studio",
                MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var dialogVm = new DownloadProgressViewModel(card.Name, card.SizeEstimateGb);
        card.IsBusy = true;

        var dialog = new Views.DownloadProgressDialog
        {
            DataContext = dialogVm,
            Owner = Application.Current?.MainWindow,
        };

        var cts = new CancellationTokenSource();
        dialogVm.CancelRequested += (_, _) => cts.Cancel();

        var streamTask = StreamPullAsync(card.Name, dialogVm, cts.Token);
        dialog.ShowDialog(); // blockierend — Cancel-Button im Dialog setzt CancelRequested.

        try { await streamTask.ConfigureAwait(true); }
        catch { /* Errors landen im Dialog ueber dialogVm.ErrorText */ }
        finally
        {
            cts.Dispose();
            card.IsBusy = false;
        }

        await LoadAsync().ConfigureAwait(true);
    }

    private async Task StreamPullAsync(string name, DownloadProgressViewModel vm, CancellationToken ct)
    {
        try
        {
            await foreach (var evt in _api.PullModelAsync(name, ct).WithCancellation(ct))
            {
                if (!string.IsNullOrEmpty(evt.Error))
                {
                    vm.ApplyError(evt.Error);
                    return;
                }
                vm.ApplyProgress(evt);
                if (evt.IsTerminal)
                {
                    vm.ApplyDone();
                    return;
                }
            }
            // Stream zu Ende ohne Terminal-Event — wir behandeln das als unklare Beendigung.
            vm.ApplyDone();
        }
        catch (OperationCanceledException)
        {
            vm.ApplyCancelled();
        }
        catch (Exception ex)
        {
            vm.ApplyError(ex.Message);
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _loadCts?.Cancel();
        _loadCts?.Dispose();
    }
}

// =====================================================================
// Karten-ViewModels
// =====================================================================

/// <summary>Karte fuer ein installiertes Modell.</summary>
public partial class InstalledModelCardViewModel : ObservableObject
{
    private readonly ModelManagerViewModel _parent;
    public string Name { get; }
    public double SizeGb { get; }
    public string ModifiedDisplay { get; }
    public string ParameterSize { get; }
    public string Quantization { get; }

    [ObservableProperty] private bool _isBusy;

    public InstalledModelCardViewModel(ModelListEntry entry, ModelManagerViewModel parent)
    {
        _parent = parent;
        Name = entry.Name;
        SizeGb = entry.SizeGb;
        ParameterSize = entry.ParameterSize ?? "—";
        Quantization = entry.QuantizationLevel ?? "—";
        ModifiedDisplay = FormatTimestamp(entry.ModifiedAt);
    }

    public string SizeDisplay => SizeGb > 0 ? $"{SizeGb:F2} GB" : "—";

    [RelayCommand]
    private Task DeleteAsync() => _parent.DeleteInstalledAsync(this);

    private static string FormatTimestamp(string raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return "—";
        if (DateTimeOffset.TryParse(raw, out var dt))
            return dt.LocalDateTime.ToString("yyyy-MM-dd HH:mm");
        return raw;
    }
}

/// <summary>Karte fuer ein kuratiertes (ggf. nicht installiertes) Modell.</summary>
public partial class AvailableModelCardViewModel : ObservableObject
{
    private readonly ModelManagerViewModel _parent;
    public string Name { get; }
    public string Description { get; }
    public string SuggestedMode { get; }
    public double SizeEstimateGb { get; }
    public bool Installed { get; }

    [ObservableProperty] private bool _isBusy;

    public AvailableModelCardViewModel(AvailableModelEntry entry, ModelManagerViewModel parent)
    {
        _parent = parent;
        Name = entry.Name;
        Description = entry.Description;
        SuggestedMode = entry.SuggestedMode;
        SizeEstimateGb = entry.SizeEstimateGb;
        Installed = entry.Installed;
    }

    public string SizeDisplay => $"~{SizeEstimateGb:F1} GB";
    public string ModeBadge => SuggestedMode?.ToUpperInvariant() ?? "—";
    public bool CanDownload => !Installed && !IsBusy;

    [RelayCommand(CanExecute = nameof(CanDownload))]
    private Task DownloadAsync() => _parent.DownloadAvailableAsync(this);

    partial void OnIsBusyChanged(bool value) => DownloadCommand.NotifyCanExecuteChanged();
}

// =====================================================================
// Download-Dialog ViewModel
// =====================================================================

/// <summary>ViewModel fuer den Pull-Progress-Dialog.</summary>
public partial class DownloadProgressViewModel : ObservableObject
{
    [ObservableProperty] private string _modelName = "";
    [ObservableProperty] private string _statusText = "Verbinde mit Ollama...";
    [ObservableProperty] private string _detailText = "";
    [ObservableProperty] private double _percent;
    [ObservableProperty] private bool _isIndeterminate = true;
    [ObservableProperty] private bool _isFinished;
    [ObservableProperty] private string? _errorText;
    [ObservableProperty] private long _completedBytes;
    [ObservableProperty] private long _totalBytes;
    [ObservableProperty] private double _sizeEstimateGb;

    public event EventHandler? CancelRequested;

    public DownloadProgressViewModel(string name, double sizeEstimateGb)
    {
        ModelName = name;
        SizeEstimateGb = sizeEstimateGb;
        DetailText = $"Erwartete Groesse ca. {sizeEstimateGb:F1} GB.";
    }

    public void ApplyProgress(PullProgressEvent evt)
    {
        StatusText = evt.Status ?? StatusText;
        if (evt.Completed.HasValue) CompletedBytes = evt.Completed.Value;
        if (evt.Total.HasValue) TotalBytes = evt.Total.Value;

        if (evt.Percent is double p)
        {
            Percent = Math.Clamp(p, 0, 100);
            IsIndeterminate = false;
            DetailText = $"{FormatBytes(CompletedBytes)} / {FormatBytes(TotalBytes)}  ({Percent:F1}%)";
        }
        else
        {
            IsIndeterminate = true;
            DetailText = evt.Digest ?? "";
        }
    }

    public void ApplyDone()
    {
        Percent = 100;
        IsIndeterminate = false;
        IsFinished = true;
        StatusText = "Fertig.";
        DetailText = $"'{ModelName}' wurde erfolgreich heruntergeladen.";
    }

    public void ApplyError(string error)
    {
        ErrorText = error;
        IsFinished = true;
        IsIndeterminate = false;
        StatusText = "Fehler.";
        DetailText = error;
    }

    public void ApplyCancelled()
    {
        IsFinished = true;
        IsIndeterminate = false;
        StatusText = "Abgebrochen.";
        DetailText = "Pull wurde vom Nutzer abgebrochen.";
    }

    [RelayCommand]
    private void Cancel() => CancelRequested?.Invoke(this, EventArgs.Empty);

    private static string FormatBytes(long bytes)
    {
        if (bytes <= 0) return "0 B";
        string[] units = { "B", "KB", "MB", "GB", "TB" };
        double size = bytes;
        int unit = 0;
        while (size >= 1024 && unit < units.Length - 1)
        {
            size /= 1024;
            unit++;
        }
        return $"{size:F2} {units[unit]}";
    }
}
