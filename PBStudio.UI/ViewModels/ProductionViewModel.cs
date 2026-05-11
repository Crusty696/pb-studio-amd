using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Win32;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Produktions/Rendering Tab.</summary>
public partial class ProductionViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly SSEClient _sse;
    private readonly TimelineStateService _timelineState;
    private readonly ProjectService _projects;
    private readonly IDialogService _dialogService;
    private string? _currentTaskId;
    private DateTime _lastGpuLogUtc = DateTime.MinValue;
    private bool _disposed;

    [ObservableProperty] private string _outputPath = "";
    [ObservableProperty] private string _audioPath = "";
    [ObservableProperty] private string _selectedQuality = "high";
    [ObservableProperty] private int _width = 1920;
    [ObservableProperty] private int _height = 1080;
    [ObservableProperty] private double _fps = 30.0;
    // L-N5: Bitrate-Slider (4-50 Mbps, default 12). Wird an /render/start als bitrate_mbps geschickt.
    [ObservableProperty] private int _bitrateMbps = 12;
    [ObservableProperty] private string _statusText = "Bereit für Rendering";
    [ObservableProperty] private double _renderProgress;
    [ObservableProperty] private bool _isRendering;
    [ObservableProperty] private string _etaText = "";
    [ObservableProperty] private bool _hasProject;

    public ObservableCollection<string> RenderLogEntries { get; } = [];
    public List<string> QualityOptions { get; } = ["preview", "standard", "high", "ultra"];

    public ProductionViewModel(IApiClient api, SSEClient sse, TimelineStateService timelineState, ProjectService projects, IDialogService dialogService)
    {
        _api = api;
        _sse = sse;
        _timelineState = timelineState;
        _projects = projects;
        _dialogService = dialogService;
        HasProject = _projects.HasProject;
        _sse.ProgressReceived += OnRenderProgress;
        _sse.LogReceived += OnLogReceived;
        _sse.GpuStatusReceived += OnGpuStatusReceived;
        _timelineState.TimelineChanged += OnTimelineChanged;

        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) =>
        {
            // Send() kann von Background-Thread kommen (ProjectService.OpenProjectAsync).
            // NotifyCanExecuteChanged + Observable-Property-Sets brauchen UI-Thread.
            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                HasProject = true;
                StartRenderCommand.NotifyCanExecuteChanged();
            });
        });
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetProjectState));

        if (HasProject)
        {
            StatusText = "Bereit für Rendering";
            _ = SyncAudioPathFromTimelineAsync();
        }
    }

    [RelayCommand]
    private void BrowseOutput()
    {
        var file = _dialogService.SaveFile(
            "Ausgabedatei wählen",
            "MP4 Video|*.mp4|MKV Video|*.mkv",
            "output.mp4"
        );
        if (!string.IsNullOrEmpty(file))
            OutputPath = file;
    }

    private bool CanStartRender() => HasProject && !IsRendering;

    [RelayCommand(CanExecute = nameof(CanStartRender))]
    private async Task StartRenderAsync()
    {
        if (IsRendering)
        {
            AppendLog("warn", "Rendering läuft bereits");
            return;
        }

        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            StatusText = "Kein Ausgabepfad gewählt";
            return;
        }

        await SyncAudioPathFromTimelineAsync();
        if (string.IsNullOrWhiteSpace(AudioPath))
        {
            StatusText = "Kein Audio-Pfad vorhanden. Bitte zuerst eine Cut-Liste generieren.";
            return;
        }

        RenderLogEntries.Clear();
        AppendLog("info", $"Render startet: {OutputPath}");
        AppendLog("info", $"Quelle: {AudioPath}");
        AppendLog("info", $"Preset: {SelectedQuality} | {Width}x{Height} @ {Fps:0.##} fps | {BitrateMbps} Mbps");

        IsRendering = true;
        RenderProgress = 0;
        EtaText = "Verbinde…";
        StatusText = "Rendering startet...";
        _currentTaskId = null;
        _lastGpuLogUtc = DateTime.MinValue;

        var request = new RenderRequest(
            OutputPath: OutputPath,
            AudioPath: AudioPath,
            Quality: SelectedQuality,
            ResolutionWidth: Width,
            ResolutionHeight: Height,
            Fps: Fps,
            BitrateMbps: BitrateMbps
        );

        try
        {
            var result = await _api.StartRenderAsync(request);
            if (result != null)
            {
                _currentTaskId = result.TaskId;
                ApplyProgressUpdate(result.TaskId, result.Status, result.Percent, "Render-Task registriert", result.CurrentFrame, result.TotalFrames, result.ElapsedSeconds, result.EtaSeconds, result.OutputPath, result.Error);
                AppendLog("info", $"Render-Task gestartet: {result.TaskId}");
            }
            else
            {
                ResetRenderState("Rendering konnte nicht gestartet werden", "error", "Render-Start fehlgeschlagen");
            }
        }
        catch (Exception ex)
        {
            ResetRenderState($"Rendering fehlgeschlagen: {ex.Message}", "error", $"Unerwarteter Fehler beim Render-Start: {ex.Message}");
        }
    }

    [RelayCommand]
    private async Task CancelRenderAsync()
    {
        if (_currentTaskId == null)
            return;

        await _api.CancelRenderAsync(_currentTaskId);
        StatusText = "Abbruch angefordert...";
        EtaText = "Stoppt…";
        AppendLog("warn", $"Cancel angefordert für Task {_currentTaskId}");
    }

    [RelayCommand]
    private void ClearRenderLog()
    {
        RenderLogEntries.Clear();
        AppendLog("info", "Render-Log geleert");
    }

    private async Task SyncAudioPathFromTimelineAsync()
    {
        var timeline = _timelineState.CurrentTimeline ?? await _timelineState.RefreshAsync();
        if (!string.IsNullOrEmpty(timeline?.AudioPath))
            AudioPath = timeline.AudioPath;
    }

    private void OnTimelineChanged(object? sender, TimelineResponse? timeline)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            AudioPath = timeline?.AudioPath ?? string.Empty;
        });
    }

    private void OnRenderProgress(object? sender, ProgressEventArgs e)
    {
        if (e.EventType != "render_progress")
            return;

        if (!string.IsNullOrEmpty(_currentTaskId) && !string.IsNullOrEmpty(e.TaskId) && e.TaskId != _currentTaskId)
            return;

        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            if (!string.IsNullOrWhiteSpace(e.TaskId))
                _currentTaskId = e.TaskId;

            ApplyProgressUpdate(
                e.TaskId,
                e.Status,
                e.Percent,
                e.Message,
                e.CurrentFrame,
                e.TotalFrames,
                e.ElapsedSeconds,
                e.EtaSeconds,
                e.OutputPath,
                e.Error);
        });
    }

    private void ApplyProgressUpdate(
        string? taskId,
        string? status,
        double percent,
        string? message,
        int currentFrame,
        int totalFrames,
        double elapsedSeconds,
        double etaSeconds,
        string? outputPath,
        string? error)
    {
        var normalizedStatus = (status ?? string.Empty).Trim().ToLowerInvariant();
        var effectiveMessage = string.IsNullOrWhiteSpace(message)
            ? normalizedStatus switch
            {
                "completed" => "Rendering abgeschlossen",
                "cancelled" => "Rendering abgebrochen",
                "failed" => "Rendering fehlgeschlagen",
                "pending" => "Render-Task wartet…",
                "running" => "Rendering läuft...",
                _ => "Render-Update empfangen",
            }
            : message.Trim();

        RenderProgress = Math.Clamp(percent, 0, 100);
        StatusText = effectiveMessage;
        EtaText = BuildEtaText(normalizedStatus, percent, currentFrame, totalFrames, elapsedSeconds, etaSeconds);

        switch (normalizedStatus)
        {
            case "completed":
                IsRendering = false;
                RenderProgress = 100;
                EtaText = string.Empty;
                StatusText = effectiveMessage;
                AppendLog("info", taskId is null ? effectiveMessage : $"{effectiveMessage} ({taskId})");
                if (!string.IsNullOrWhiteSpace(outputPath))
                    AppendLog("info", $"Output: {outputPath}");
                _currentTaskId = null;
                break;

            case "cancelled":
                ResetRenderState(effectiveMessage, "warn", taskId is null ? effectiveMessage : $"{effectiveMessage} ({taskId})");
                break;

            case "failed":
                ResetRenderState(effectiveMessage, "error", string.IsNullOrWhiteSpace(error) ? effectiveMessage : $"{effectiveMessage}: {error}");
                break;

            default:
                IsRendering = true;
                break;
        }
    }

    private static string BuildEtaText(string status, double percent, int currentFrame, int totalFrames, double elapsedSeconds, double etaSeconds)
    {
        if (status is "completed" or "cancelled" or "failed")
            return string.Empty;

        var parts = new List<string>();

        if (percent > 0)
            parts.Add($"{percent:F0}%");

        if (totalFrames > 0)
            parts.Add($"{currentFrame}/{totalFrames} Frames");

        if (etaSeconds > 0)
            parts.Add($"ETA {FormatDuration(etaSeconds)}");
        else if (elapsedSeconds > 0)
            parts.Add($"Läuft {FormatDuration(elapsedSeconds)}");

        return string.Join(" | ", parts);
    }

    private static string FormatDuration(double totalSeconds)
    {
        var safeSeconds = Math.Max(0, (int)Math.Round(totalSeconds));
        var duration = TimeSpan.FromSeconds(safeSeconds);

        return duration.TotalHours >= 1
            ? $"{(int)duration.TotalHours:D2}:{duration.Minutes:D2}:{duration.Seconds:D2}"
            : $"{duration.Minutes:D2}:{duration.Seconds:D2}";
    }

    private void OnLogReceived(object? sender, LogEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() => AppendLog(e.Level, e.Message));
    }

    private void OnGpuStatusReceived(object? sender, GpuEventArgs e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            if (!string.IsNullOrWhiteSpace(e.Error))
            {
                if (DateTime.UtcNow - _lastGpuLogUtc > TimeSpan.FromSeconds(15))
                {
                    AppendLog("debug", $"GPU-Monitor: {e.Error}");
                    _lastGpuLogUtc = DateTime.UtcNow;
                }
                return;
            }

            var gpuParts = new List<string>();
            if (e.VramTotalMb > 0)
                gpuParts.Add($"VRAM {e.VramUsedMb}/{e.VramTotalMb} MB");
            if (e.GpuLoadPercent > 0)
                gpuParts.Add($"Load {e.GpuLoadPercent:F0}%");
            if (e.TemperatureC > 0)
                gpuParts.Add($"{e.TemperatureC}°C");

            if (gpuParts.Count == 0)
                return;

            var gpuSummary = string.Join(" | ", gpuParts);

            // BUG-053 FIX: Nur aktualisieren, wenn nicht gerendert wird
            if (!IsRendering)
            {
                EtaText = gpuSummary;
            }

            if (DateTime.UtcNow - _lastGpuLogUtc > TimeSpan.FromSeconds(15))
            {
                AppendLog("debug", $"GPU: {gpuSummary}");
                _lastGpuLogUtc = DateTime.UtcNow;
            }
        });
    }

    partial void OnIsRenderingChanged(bool value)
    {
        StartRenderCommand.NotifyCanExecuteChanged();
    }

    private void ResetRenderState(string statusText, string logLevel, string logMessage)
    {
        IsRendering = false;
        EtaText = string.Empty;
        StatusText = statusText;
        AppendLog(logLevel, logMessage);
        _currentTaskId = null;
    }

    private void AppendLog(string level, string message)
    {
        if (string.IsNullOrWhiteSpace(message))
            return;

        var prefix = level.ToUpperInvariant() switch
        {
            "ERROR" => "[ERR]",
            "WARN" or "WARNING" => "[WRN]",
            "DEBUG" => "[DBG]",
            _ => "[INF]",
        };

        RenderLogEntries.Add($"{DateTime.Now:HH:mm:ss} {prefix} {message}");

        while (RenderLogEntries.Count > 300)
            RenderLogEntries.RemoveAt(0);
    }

    private void ResetProjectState()
    {
        HasProject = false;
        StartRenderCommand.NotifyCanExecuteChanged();
        _currentTaskId = null;
        AudioPath = string.Empty;
        RenderProgress = 0;
        IsRendering = false;
        EtaText = string.Empty;
        StatusText = "Kein Projekt geöffnet";
    }

    // R17/LOW: Added _disposed guard — consistent with all other ViewModels.
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _sse.ProgressReceived -= OnRenderProgress;
        _sse.LogReceived -= OnLogReceived;
        _sse.GpuStatusReceived -= OnGpuStatusReceived;
        _timelineState.TimelineChanged -= OnTimelineChanged;
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
