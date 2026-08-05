using System.Windows.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;
using System;
using System.Threading.Tasks;

namespace PBStudio.UI.ViewModels;

public partial class MainViewModel : ObservableObject, IDisposable
{
    private readonly ILogger<MainViewModel> _logger;
    private readonly PythonBridgeService _bridge;
    private readonly IApiClient _api;
    private readonly SSEClient _sse;
    private readonly ProjectService _projects;

    [ObservableProperty]
    private string _statusMessage = "Bereit";

    [ObservableProperty]
    private string _backendStatusText = "Backend: Offline";

    [ObservableProperty]
    private Brush _backendStatusColor = Brushes.Gray;

    [ObservableProperty]
    private bool _isBackendConnected = true; // Default true to prevent flicker on start

    // Spec 00010 T004: Latched unreachable-flag fuer ConnectionStatus-Overlay.
    // Wird nur true wenn SSEClient nach >=5 fehlgeschlagenen Reconnect-Versuchen
    // BackendReachabilityChanged(false) feuert. Auto-Hide bei BackendReachabilityChanged(true).
    [ObservableProperty]
    private bool _isBackendUnreachable = false;

    [ObservableProperty]
    private string _gpuStatusText = "GPU: Unbekannt";

    [ObservableProperty]
    private string _llmModelName = "Keines (Moondream-Fallback)";

    [ObservableProperty]
    private string _llmProvider = "Lokal (GPU)";

    [ObservableProperty]
    private double _llmLoadProgress = 0.0;

    [ObservableProperty]
    private string _llmStatusText = "Bereit";

    [ObservableProperty]
    private Brush _llmStatusColor = Brushes.Gray;

    // Audit 2026-08-05 (C-A): Persistenzfehler-Banner. Das Backend publisht
    // "persist_error" seit jeher, aber der Event wurde im Filter und im
    // SSEClient verworfen — der User sah einen fehlgeschlagenen Speichervorgang
    // nie. Beides ist gefixt, hier liegt die Anzeige.
    [ObservableProperty]
    private bool _hasPersistError;

    [ObservableProperty]
    private string _persistErrorText = string.Empty;

    // Review-Fix LOW (2026-07-09): frozen statt pro Event neu allokiert (GC-Churn)
    private static readonly SolidColorBrush LlmLoadingBrush = CreateFrozen(Color.FromRgb(255, 110, 0));

    private static SolidColorBrush CreateFrozen(Color color)
    {
        var brush = new SolidColorBrush(color);
        brush.Freeze();
        return brush;
    }

    [ObservableProperty]
    private int _selectedTabIndex = 0;

    public string? CurrentProjectName => _projects.CurrentProjectName;

    public MainViewModel(
        ILogger<MainViewModel> logger,
        PythonBridgeService bridge,
        IApiClient api,
        SSEClient sse,
        ProjectService projects)
    {
        _logger = logger;
        _bridge = bridge;
        _api = api;
        _sse = sse;
        _projects = projects;

        _bridge.StatusChanged += OnBackendStatusChanged;
        _sse.ProgressReceived += OnProgressReceived;
        _sse.GpuStatusReceived += OnGpuStatusReceived;
        _sse.LlmStatusReceived += OnLlmStatusReceived;
        _sse.PersistErrorReceived += OnPersistErrorReceived;
        // Spec 00010 T004: Latched-reachability fuer Overlay.
        _sse.BackendReachabilityChanged += OnBackendReachabilityChanged;
        _projects.ProjectChanged += OnProjectChanged;

        WeakReferenceMessenger.Default.Register<BackendReadyMessage>(this, (_, _) => _ = InitializeAsync());
        WeakReferenceMessenger.Default.Register<NavigateDirectorMessage>(this, (_, _) =>
        {
            SelectedTabIndex = 3; // Index 3 is KI-REGIE (Director)
        });

        _ = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        try
        {
            for (int i = 0; i < 60; i++)
            {
                if (_bridge.IsRunning)
                {
                    BackendStatusText = "Backend: Online";
                    BackendStatusColor = Brushes.LimeGreen;
                    _sse.StartListening();
                    await RefreshGpuStatusAsync();
                    await _projects.RefreshProjectInfoAsync();
                    return;
                }

                await Task.Delay(500);
            }

            BackendStatusText = "Backend: Offline";
            BackendStatusColor = Brushes.Red;
        }
        catch (Exception)
        {
            BackendStatusText = "Backend: Fehler";
            BackendStatusColor = Brushes.Red;
            StatusMessage = "Initialisierungsfehler";
        }
    }

    private void OnBackendStatusChanged(object? sender, bool isRunning)
    {
        if (isRunning)
        {
            _ = InitializeAsync();
        }
        else
        {
            BackendStatusText = "Backend: Gestoppt";
            BackendStatusColor = Brushes.Gray;
            _sse.StopListening();
        }
    }

    private void OnProgressReceived(object? sender, ProgressEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            StatusMessage = e.Message;
        });
    }

    private void OnGpuStatusReceived(object? sender, GpuEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            GpuStatusText = $"GPU: {e.VramUsedMb}/{e.VramTotalMb} MB";
        });
    }

    private void OnLlmStatusReceived(object? sender, LlmStatusEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            LlmModelName = string.IsNullOrEmpty(e.Model) || e.Model == "none" ? "Keines (Moondream-Fallback)" : e.Model;
            LlmProvider = string.IsNullOrEmpty(e.Provider) ? "Lokal (GPU)" : e.Provider;
            LlmLoadProgress = e.Percent;

            if (e.Status == "loading")
            {
                LlmStatusText = $"Lade LLM ({e.Percent}%)";
                LlmStatusColor = LlmLoadingBrush; // Orange
            }
            else if (e.Status == "active")
            {
                LlmStatusText = "Aktiv";
                LlmStatusColor = Brushes.LimeGreen;
            }
            else if (e.Status == "failed")
            {
                LlmStatusText = "Fehler / Fallback";
                LlmStatusColor = Brushes.Red;
            }
            else if (e.Status == "unavailable")
            {
                // Audit 2026-08-05 (H-6): Der Vision-Wrapper sendet ausdruecklich
                // "unavailable" (z.B. Moondream-Caption ohne ONNX-Decoder). Ohne
                // eigenen Zweig landete das im Default und wurde als "Bereit"
                // angezeigt — genau die Art Beschoenigung, die IRON RULE 10 verbietet.
                LlmStatusText = "Nicht verfügbar";
                LlmStatusColor = Brushes.OrangeRed;
            }
            else
            {
                // "idle" und unbekannte Stati: neutral, kein Erfolgsversprechen.
                LlmStatusText = "Bereit";
                LlmStatusColor = Brushes.Gray;
            }
        });
    }

    /// <summary>
    /// Persistenzfehler sichtbar machen (IRON RULE 10). Zuvor wurde dieser Kanal
    /// zweifach verworfen, sodass ein fehlgeschlagener Speichervorgang fuer den
    /// User wie ein Erfolg aussah (Audit 2026-08-05, C-A).
    /// </summary>
    private void OnPersistErrorReceived(object? sender, PersistErrorEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            var source = string.IsNullOrWhiteSpace(e.Source) ? "Backend" : e.Source;
            var message = string.IsNullOrWhiteSpace(e.Message)
                ? "Persistenzfehler ohne Detailangabe"
                : e.Message;

            PersistErrorText = $"Speicherfehler ({source}): {message}";
            HasPersistError = true;

            _logger?.LogError(
                "Persistenzfehler vom Backend: source={Source} message={Message} detail={Detail}",
                source,
                message,
                e.Detail);
        });
    }

    /// <summary>Loescht die Persistenzfehler-Anzeige (Button "Verstanden").</summary>
    [RelayCommand]
    private void DismissPersistError()
    {
        HasPersistError = false;
        PersistErrorText = string.Empty;
    }

    private void OnBackendReachabilityChanged(object? sender, bool reachable)
    {
        // Spec 00010 T004: invertierte Flagge — bindbar an Overlay.Visibility
        // via BooleanToVisibilityConverter. Auf UI-Thread dispatchen.
        _ = App.Current.Dispatcher.InvokeAsync(async () =>
        {
            IsBackendUnreachable = !reachable;

            if (!reachable)
            {
                _logger.LogWarning("WPF Auto-Recovery: Backend nicht erreichbar. Versuche automatischen Neustart des Backends im Hintergrund...");
                try
                {
                    // StartAsync() im Hintergrund aufrufen, um den UI-Thread nicht zu belasten.
                    await Task.Run(async () => await _bridge.StartAsync().ConfigureAwait(false));
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "WPF Auto-Recovery: Fehler beim Versuch, das Backend neu zu starten.");
                }
            }
        });
    }

    private void OnProjectChanged(object? sender, ProjectInfo? e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            OnPropertyChanged(nameof(CurrentProjectName));
        });
    }

    private async Task RefreshGpuStatusAsync()
    {
        try
        {
            var gpu = await _api.GetGpuStatusAsync();
            if (gpu != null)
            {
                _ = App.Current.Dispatcher.InvokeAsync(() =>
                {
                    GpuStatusText = $"GPU: {gpu.VramUsedMb}/{gpu.VramTotalMb} MB";
                });
            }
        }
        catch
        {
            // Background refresh fail is non-critical
        }
    }

    public void Dispose()
    {
        _bridge.StatusChanged -= OnBackendStatusChanged;
        _sse.ProgressReceived -= OnProgressReceived;
        _sse.GpuStatusReceived -= OnGpuStatusReceived;
        _sse.LlmStatusReceived -= OnLlmStatusReceived;
        _sse.PersistErrorReceived -= OnPersistErrorReceived;
        _sse.BackendReachabilityChanged -= OnBackendReachabilityChanged;
        _projects.ProjectChanged -= OnProjectChanged;
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
