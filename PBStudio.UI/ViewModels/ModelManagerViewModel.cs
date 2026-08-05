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
    [ObservableProperty] private string _providerStatusText = "Noch nicht verifiziert";
    [ObservableProperty] private string _discoverActionsText = "Katalog nicht verifiziert";
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

        var previous = _loadCts;
        var current = new CancellationTokenSource();
        _loadCts = current;
        previous?.Cancel();
        var token = current.Token;

        IsLoading = true;
        ErrorText = null;
        try
        {
            // /models/list invalidiert genau einmal; /available liest danach
            // dieselbe Inventargeneration ohne parallelen Provider-Sturm.
            var installed = await _api.GetInstalledModelsAsync(token).ConfigureAwait(true);
            if (token.IsCancellationRequested) return;
            var available = await _api.GetAvailableModelsAsync(token).ConfigureAwait(true);

            ApplyInstalled(installed);
            ApplyAvailable(available);

            OllamaAvailable = (installed?.OllamaAvailable ?? false) || (available?.OllamaAvailable ?? false);
            LmStudioAvailable = (installed?.LmstudioAvailable ?? false) || (available?.LmstudioAvailable ?? false);
            BaseUrl = installed?.BaseUrl ?? available?.BaseUrl ?? "";
            LastFetchedAt = DateTime.Now;
            var providerStates = installed?.Providers ?? new List<ProviderStatusEntry>();
            ProviderStatusText = providerStates.Count > 0
                ? string.Join(" · ", providerStates.Select(p =>
                    $"{ProviderLabel(p.Provider)}: {p.Status.ToUpperInvariant()}" +
                    (string.IsNullOrWhiteSpace(p.StatusReason) ? "" : $" ({p.StatusReason})")))
                : "Providerstatus nicht verifiziert";
            DiscoverActionsText = available?.DiscoverActions is { Count: > 0 }
                ? string.Join(" · ", available.DiscoverActions.Select(action =>
                    $"{action.Label}: {CatalogLabel(action.CatalogStatus)}"))
                : "Keine live verifizierte Discover-Aktion";

            if (LmStudioAvailable && OllamaAvailable)
            {
                ActiveProvider = "Hybrid";
                ProviderBadge = "HYBRID";
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
            if (ReferenceEquals(_loadCts, current))
            {
                _loadCts = null;
                if (!_disposed)
                    IsLoading = false;
            }
            current.Dispose();
        }
    }

    private static string ProviderLabel(string provider) =>
        provider.Equals("lmstudio", StringComparison.OrdinalIgnoreCase)
            ? "LM Studio"
            : provider.Equals("ollama", StringComparison.OrdinalIgnoreCase)
                ? "Ollama"
                : provider;

    private static string CatalogLabel(string status) =>
        status.Equals("discover_only", StringComparison.OrdinalIgnoreCase)
            ? "allgemeine Suche"
            : status.Equals("verified", StringComparison.OrdinalIgnoreCase)
                ? "live verifiziert"
                : "nicht verifiziert";

    private void ApplyInstalled(ModelListResponse? resp)
    {
        InstalledModels.Clear();
        if (resp?.Models is null) return;
        foreach (var entry in resp.Models
            .OrderBy(m => m.Provider, StringComparer.OrdinalIgnoreCase)
            .ThenBy(m => m.Name, StringComparer.OrdinalIgnoreCase))
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

    /// <summary>Wird von einer providergebundenen InstalledModelCard aufgerufen.</summary>
    internal async Task DeleteInstalledAsync(InstalledModelCardViewModel card)
    {
        if (!card.Provider.Equals("ollama", StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show(
                $"Bitte oeffne LM Studio -> My Models und entferne '{card.Name}' dort.",
                "LM-Studio-Modell verwalten",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        var info = MessageBox.Show(
            $"Ollama-Modell '{card.Name}' wirklich loeschen?",
            "Ollama-Modell loeschen",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (info != MessageBoxResult.Yes) return;

        card.IsBusy = true;
        try
        {
            var deleted = await _api.DeleteModelAsync(card.Name).ConfigureAwait(true);
            StatusText = deleted
                ? $"Ollama-Modell '{card.Name}' geloescht."
                : $"Ollama-Modell '{card.Name}' konnte nicht geloescht werden.";
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

    /// <summary>Wird von einer providergebundenen AvailableModelCard aufgerufen.</summary>
    internal async Task DownloadAvailableAsync(AvailableModelCardViewModel card)
    {
        if (card.Installed)
        {
            MessageBox.Show($"'{card.Name}' ist bereits installiert.", "PB Studio",
                MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (!card.Provider.Equals("ollama", StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show(
                $"Bitte lade '{card.Name}' im Discover-Tab von LM Studio herunter.",
                "LM-Studio-Modell herunterladen",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        MessageBox.Show(
            $"Das live verifizierte Ollama-Modell '{card.Name}' wird jetzt heruntergeladen.",
            "Ollama-Modell herunterladen",
            MessageBoxButton.OK,
            MessageBoxImage.Information);

        card.IsBusy = true;
        try
        {
            var receivedEvent = false;
            await foreach (var progress in _api.PullModelAsync(card.Name)
                .WithCancellation(default)
                .ConfigureAwait(true))
            {
                receivedEvent = true;
                if (!string.IsNullOrWhiteSpace(progress.Error))
                    throw new InvalidOperationException(progress.Error);
                StatusText = $"Ollama-Download '{card.Name}': {progress.Status ?? "laeuft"}";
            }
            if (!receivedEvent)
                throw new InvalidOperationException("Backend lieferte keinen Downloadstatus.");
            StatusText = $"Ollama-Modell '{card.Name}' heruntergeladen.";
        }
        catch (Exception ex)
        {
            ErrorText = $"Download fehlgeschlagen fuer '{card.Name}': {ex.Message}";
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
            var success = await _api.ActivateModelAsync(card.Name, card.Provider).ConfigureAwait(true);
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
            var resp = await _api.TestModelAsync(card.Name, card.Provider).ConfigureAwait(true);
            // Audit 2026-08-05 (H-2/T3.10): Der Auswahl-Beleg wird jetzt vom
            // Backend mitgeliefert und angezeigt — vorher landete er nur im
            // backend.log, das bis zu diesem Audit nicht einmal ein Datum im
            // Zeitstempel hatte. Gilt auch im Fehlerfall: gerade dann ist
            // interessant, welches Modell mit welchen Capabilities gewaehlt wurde.
            card.SelectionReceiptText = FormatSelectionReceipt(resp?.SelectionReceipt);

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

    /// <summary>
    /// Formatiert den Auswahl-Beleg fuer die Anzeige auf der Modell-Karte.
    /// Leerer String, wenn kein Receipt geliefert wurde — dann bleibt der
    /// Bereich in der UI ausgeblendet statt eine Leerzeile zu zeigen.
    /// </summary>
    private static string FormatSelectionReceipt(ModelSelectionReceipt? receipt)
    {
        if (receipt is null || string.IsNullOrWhiteSpace(receipt.ModelId))
            return string.Empty;

        var verified = receipt.VerifiedCapabilities is { Count: > 0 }
            ? string.Join("+", receipt.VerifiedCapabilities)
            : "keine";
        var required = receipt.RequiredCapabilities is { Count: > 0 }
            ? string.Join("+", receipt.RequiredCapabilities)
            : "keine";

        return $"Gewaehlt: {receipt.ModelId} ({receipt.Provider}) · "
               + $"Task {receipt.Task}/{receipt.Mode} · "
               + $"benoetigt {required}, verifiziert {verified} · "
               + $"Quelle {receipt.Source}";
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

    /// <summary>
    /// Kontextfenster in Tokens, formatiert. Audit 2026-08-05 (H-3): LM Studio
    /// liefert diese Zahl, sie wurde aber auf drei Schichten hintereinander
    /// verworfen. Der Chat-Agent verweist im Fehlerfall selbst darauf
    /// ("Verlauf kuerzen oder groesseres Kontextfenster waehlen") — der User
    /// konnte den Rat nicht befolgen, weil die Zahl nirgends stand.
    /// </summary>
    public string ContextWindowDisplay { get; }

    /// <summary>Architektur laut LM Studio (z.B. "qwen35", "granitehybrid").</summary>
    public string ArchitectureDisplay { get; }


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
    [ObservableProperty] private string _stateText = "NICHT VERIFIZIERT";
    [ObservableProperty] private string _statusReason = "";

    /// <summary>
    /// Auswahl-Beleg des letzten Smoke-Tests (Audit 2026-08-05, H-2). Leer,
    /// solange kein Test gelaufen ist — die Anzeige bleibt dann ausgeblendet.
    /// </summary>
    [ObservableProperty] private string _selectionReceiptText = "";
    public bool Vision { get; }
    public bool Loaded { get; }
    public bool Usable { get; }
    public string StateColor { get; }

    [ObservableProperty] private bool _isBusy;

    public InstalledModelCardViewModel(ModelListEntry entry, ModelManagerViewModel parent)
    {
        _parent = parent;
        Name = entry.Name;
        SizeGb = entry.SizeGb;
        ParameterSize = entry.ParameterSize ?? "—";
        Quantization = entry.QuantizationLevel ?? "—";
        ModifiedDisplay = FormatTimestamp(entry.ModifiedAt);
        ContextWindowDisplay = entry.ContextLength is > 0
            ? $"{entry.ContextLength.Value:N0} Tokens"
            : "—";
        ArchitectureDisplay = string.IsNullOrWhiteSpace(entry.Architecture)
            ? "—"
            : entry.Architecture;


        Description = entry.Description ?? "—";
        IsActive = entry.IsActive;
        Vision = entry.Vision;
        var capabilities = entry.Capabilities ?? new List<string>();
        CapabilitiesText = capabilities.Count > 0
            ? string.Join(" + ", capabilities.Select(c => c.ToUpperInvariant()))
            : "Keine Capability verifiziert";
        ActiveTasksText = entry.ActiveTasks != null && entry.ActiveTasks.Count > 0 
            ? string.Join(", ", entry.ActiveTasks) 
            : "Keine";
        HasActiveTasks = entry.IsActive;
        Provider = entry.Provider;
        Loaded = entry.Loaded;
        Usable = entry.Usable;
        StateText = entry.Loaded
            ? "GELADEN"
            : entry.Usable
                ? "ON-DEMAND"
                : "NICHT NUTZBAR";
        StateColor = entry.Loaded
            ? "#00FF66"
            : entry.Usable
                ? "#FF8C00"
                : "#FF4444";
        StatusReason = entry.StatusReason;
        ProviderBadgeText = entry.Provider switch
        {
            "ollama" => "OLLAMA",
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
    public string Provider { get; }
    public string StatusReason { get; }
    public bool Downloadable { get; }

    [ObservableProperty] private bool _isBusy;

    public AvailableModelCardViewModel(AvailableModelEntry entry, ModelManagerViewModel parent)
    {
        _parent = parent;
        Name = entry.Name;
        Description = entry.Description;
        SuggestedMode = entry.SuggestedMode;
        SizeEstimateGb = entry.SizeEstimateGb;
        Installed = entry.Installed;
        Provider = entry.Provider;
        StatusReason = entry.StatusReason;
        Downloadable = entry.Downloadable;
    }

    public string SizeDisplay => $"~{SizeEstimateGb:F1} GB";
    public string ModeBadge => SuggestedMode?.ToUpperInvariant() ?? "—";
    public string ProviderLabel => Provider.Equals(
        "ollama",
        StringComparison.OrdinalIgnoreCase)
        ? "OLLAMA"
        : "LM STUDIO";
    public string DownloadActionText => Provider.Equals(
        "ollama",
        StringComparison.OrdinalIgnoreCase)
        ? "Mit Ollama laden"
        : "In LM Studio";
    public string DownloadToolTip => Provider.Equals(
        "ollama",
        StringComparison.OrdinalIgnoreCase)
        ? "Live verifiziertes Modell über die lokale Ollama-API herunterladen."
        : "Modell im Discover-Tab von LM Studio herunterladen.";
    public bool CanDownload => Downloadable && !Installed && !IsBusy;

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
