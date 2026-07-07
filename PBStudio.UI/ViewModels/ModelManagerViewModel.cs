using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel fuer den MODELLE-Tab (Ollama Vision-Modelle).
/// Zeigt zwei Listen: installierte Modelle (mit Delete-Button) und kuratierte Verfuegbare
/// (mit Download-Button + Progress-Dialog). Nutzt <see cref="IApiClient"/>-Endpoints
/// <c>/models/list</c>, <c>/models/available</c>, <c>/models/recommendations</c>.
/// LM Studio Refactor 2026-05-17: <c>/models/pull</c> und <c>/models/{name}</c> liefern
/// jetzt HTTP 501 — Downloads/Loeschungen muessen ueber die LM-Studio-App passieren.
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
    // W-QA-2 (2026-05-22): Hybrid-Provider-Status sichtbar machen.
    [ObservableProperty] private bool _lmStudioAvailable;
    [ObservableProperty] private string _activeProvider = "unbekannt";
    [ObservableProperty] private string _providerBadge = "OFFLINE";
    [ObservableProperty] private DateTime? _lastFetchedAt;

    public ObservableCollection<InstalledModelCardViewModel> InstalledModels { get; } = new();
    public ObservableCollection<AvailableModelCardViewModel> AvailableModels { get; } = new();

    public ModelManagerViewModel(IApiClient api, ILogger<ModelManagerViewModel>? logger = null)
    {
        _api = api;
        _logger = logger;
        WeakReferenceMessenger.Default.Register<KiModeChangedMessage>(this, (_, _) => _ = RefreshAsync());
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
            LmStudioAvailable = (installed?.LmstudioAvailable ?? false) || (available?.LmstudioAvailable ?? false);
            BaseUrl = installed?.BaseUrl ?? available?.BaseUrl ?? "";
            LastFetchedAt = DateTime.Now;

            // W-QA-2 (2026-05-22): Provider-Status-Badge fuer User-Sichtbarkeit.
            // base_url verraet welcher Provider live aktiv ist (1234 = LM Studio, 11434 = Ollama).
            if (LmStudioAvailable && BaseUrl.Contains("1234"))
            {
                ActiveProvider = "LM Studio";
                ProviderBadge = "LM STUDIO";
            }
            else if (OllamaAvailable && BaseUrl.Contains("11434"))
            {
                ActiveProvider = "Ollama";
                ProviderBadge = "OLLAMA";
            }
            else if (LmStudioAvailable)
            {
                ActiveProvider = "LM Studio";
                ProviderBadge = "LM STUDIO";
            }
            else if (OllamaAvailable)
            {
                ActiveProvider = "Ollama";
                ProviderBadge = "OLLAMA";
            }
            else
            {
                ActiveProvider = "offline";
                ProviderBadge = "OFFLINE";
            }

            if (!OllamaAvailable && !LmStudioAvailable)
            {
                var err = installed?.Error ?? "Kein LLM-Provider erreichbar.";
                StatusText = $"OFFLINE: weder LM Studio noch Ollama. {err}";
                ErrorText = err;
            }
            else
            {
                var hybridHint = (OllamaAvailable && LmStudioAvailable) ? " (Hybrid: beide live)"
                               : (OllamaAvailable ? " · LM Studio: offline" : " · Ollama: offline");
                StatusText = $"{InstalledModels.Count} installiert  ·  {AvailableModels.Count} verfuegbar  ·  {ActiveProvider} @ {BaseUrl}{hybridHint}";
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

    /// <summary>Wird von einer InstalledModelCard aufgerufen.
    /// LM Studio Refactor 2026-05-17: Backend antwortet 501 — wir zeigen
    /// den User-tauglichen Hinweis an statt einer Fehlermeldung.</summary>
    internal async Task DeleteInstalledAsync(InstalledModelCardViewModel card)
    {
        var info = MessageBox.Show(
            $"Modelle koennen nicht mehr ueber PB Studio geloescht werden.\n\n" +
            $"Bitte oeffne LM Studio -> My Models und entferne '{card.Name}' dort.\n\n" +
            $"LM Studio jetzt oeffnen?",
            "Modell-Verwaltung",
            MessageBoxButton.YesNo,
            MessageBoxImage.Information);
        if (info != MessageBoxResult.Yes) return;

        card.IsBusy = true;
        try
        {
            await _api.DeleteModelAsync(card.Name).ConfigureAwait(true);
            StatusText = $"Bitte LM Studio fuer '{card.Name}' verwenden.";
        }
        catch (NotSupportedException ex)
        {
            StatusText = ex.Message;
        }
        catch (Exception ex)
        {
            ErrorText = $"Loeschen fehlgeschlagen fuer '{card.Name}': {ex.Message}";
        }
        finally
        {
            card.IsBusy = false;
        }
        await LoadAsync().ConfigureAwait(true);
    }

    /// <summary>Wird von einer AvailableModelCard aufgerufen.
    /// LM Studio Refactor 2026-05-17: Downloads werden nicht mehr unterstuetzt;
    /// stattdessen erscheint ein Hinweis-Dialog, der zum LM-Studio Discover-Tab leitet.</summary>
    internal async Task DownloadAvailableAsync(AvailableModelCardViewModel card)
    {
        if (card.Installed)
        {
            MessageBox.Show($"'{card.Name}' ist bereits installiert.", "PB Studio",
                MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        MessageBox.Show(
            $"Modell-Downloads laufen jetzt ueber LM Studio.\n\n" +
            $"Bitte oeffne LM Studio -> Discover-Tab und lade '{card.Name}' dort herunter.\n\n" +
            $"Nach dem Download ist das Modell sofort in PB Studio verfuegbar (LM Studio Server muss laufen).",
            "Modell-Download",
            MessageBoxButton.OK,
            MessageBoxImage.Information);

        // Optional: Backend trotzdem anrufen — antwortet 501, was wir im ApiClient
        // in NotSupportedException ueberfuehren. Reines Logging.
        card.IsBusy = true;
        try
        {
            await foreach (var _ in _api.PullModelAsync(card.Name).WithCancellation(default).ConfigureAwait(true))
            {
                // nichts — wir erwarten ohnehin keine Events mehr
            }
        }
        catch (NotSupportedException)
        {
            // erwarteter Pfad — der Hinweis war oben.
        }
        catch
        {
            // egal — User hat schon den Hinweis bekommen
        }
        finally
        {
            card.IsBusy = false;
        }

        await LoadAsync().ConfigureAwait(true);
    }

    internal async Task ActivateInstalledAsync(InstalledModelCardViewModel card)
    {
        if (card.IsBusy) return;
        card.IsBusy = true;
        try
        {
            var success = await _api.ActivateModelAsync(card.Name).ConfigureAwait(true);
            if (success)
            {
                StatusText = $"Modell '{card.Name}' erfolgreich aktiviert.";
            }
            else
            {
                ErrorText = $"Aktivierung fehlgeschlagen fuer '{card.Name}'";
                StatusText = "Aktivierung fehlgeschlagen.";
            }
        }
        catch (Exception ex)
        {
            ErrorText = $"Aktivierung fehlgeschlagen fuer '{card.Name}': {ex.Message}";
            StatusText = "Aktivierung fehlgeschlagen.";
        }
        finally
        {
            card.IsBusy = false;
        }
        await LoadAsync().ConfigureAwait(true);
    }

    internal async Task TestInstalledAsync(InstalledModelCardViewModel card)
    {
        if (card.IsTesting) return;
        card.IsTesting = true;
        card.TestStatus = "Wird getestet...";
        card.TestStatusColor = "#CCCCCC";
        try
        {
            var resp = await _api.TestModelAsync(card.Name).ConfigureAwait(true);
            if (resp != null && resp.Success)
            {
                card.TestStatus = $"Erfolgreich ({resp.LatencyMs:F0} ms)";
                card.TestStatusColor = "#00FF66"; // Ableton Green
            }
            else
            {
                var err = resp?.Error ?? "Unbekannter Fehler bei Inferenz.";
                card.TestStatus = $"Fehler: {err}";
                card.TestStatusColor = "#FF4444"; // Rot
            }
        }
        catch (Exception ex)
        {
            card.TestStatus = $"Fehler: {ex.Message}";
            card.TestStatusColor = "#FF4444";
        }
        finally
        {
            card.IsTesting = false;
        }
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
    
    [ObservableProperty] private string _description = "—";
    [ObservableProperty] private bool _isActive;
    [ObservableProperty] private string _activeTasksText = "—";
    [ObservableProperty] private bool _hasActiveTasks;
    [ObservableProperty] private string _testStatus = "Nicht getestet";
    [ObservableProperty] private string _testStatusColor = "#888888"; // Standardgrau
    [ObservableProperty] private string _capabilitiesText = "Text (Chat)";
    [ObservableProperty] private bool _isTesting;
    [ObservableProperty] private string _provider = "lmstudio";
    [ObservableProperty] private string _providerBadgeText = "LM STUDIO";
    public bool Vision { get; }

    [ObservableProperty] private bool _isBusy;

    public InstalledModelCardViewModel(ModelListEntry entry, ModelManagerViewModel parent)
    {
        _parent = parent;
        Name = entry.Name;
        SizeGb = entry.SizeGb;
        ParameterSize = entry.ParameterSize ?? "—";
        Quantization = entry.QuantizationLevel ?? "—";
        ModifiedDisplay = FormatTimestamp(entry.ModifiedAt);
        
        Description = entry.Description ?? "—";
        IsActive = entry.IsActive;
        Vision = entry.Vision;
        CapabilitiesText = entry.Vision ? "Vision & Text" : "Text (Chat)";
        ActiveTasksText = entry.ActiveTasks != null && entry.ActiveTasks.Count > 0 
            ? string.Join(", ", entry.ActiveTasks) 
            : "Keine";
        HasActiveTasks = entry.IsActive;
        Provider = entry.Provider;
        ProviderBadgeText = entry.Provider switch
        {
            "ollama" => "OLLAMA",
            "both" => "BEIDE",
            _ => "LM STUDIO"
        };
    }

    public string SizeDisplay => SizeGb > 0 ? $"{SizeGb:F2} GB" : "—";

    [RelayCommand]
    private Task DeleteAsync() => _parent.DeleteInstalledAsync(this);

    [RelayCommand]
    private Task ActivateAsync() => _parent.ActivateInstalledAsync(this);

    [RelayCommand]
    private Task TestAsync() => _parent.TestInstalledAsync(this);

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
