using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using Microsoft.Win32;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Produktions/Rendering Tab.</summary>
public partial class ProductionViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private readonly SSEClient _sse;
    private string? _currentTaskId;

    [ObservableProperty] private string _outputPath = "";
    [ObservableProperty] private string _audioPath = "";
    [ObservableProperty] private string _selectedQuality = "high";
    [ObservableProperty] private int _width = 1920;
    [ObservableProperty] private int _height = 1080;
    [ObservableProperty] private double _fps = 30.0;
    [ObservableProperty] private string _statusText = "Bereit für Rendering";
    [ObservableProperty] private double _renderProgress;
    [ObservableProperty] private bool _isRendering;
    [ObservableProperty] private string _etaText = "";

    public ObservableCollection<string> RenderLogEntries { get; } = [];
    public List<string> QualityOptions { get; } = ["preview", "standard", "high", "ultra"];

    public ProductionViewModel(IApiClient api, SSEClient sse)
    {
        _api = api;
        _sse = sse;
        _sse.ProgressReceived += OnRenderProgress;
        _sse.LogReceived += OnLogReceived;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "backend-ready" or "timeline-refresh")
                _ = SyncAudioPathFromTimelineAsync();
        });
    }

    [RelayCommand]
    private void BrowseOutput()
    {
        var dialog = new SaveFileDialog
        {
            Filter = "MP4 Video|*.mp4|MKV Video|*.mkv",
            DefaultExt = ".mp4",
            Title = "Ausgabedatei wählen",
        };
        if (dialog.ShowDialog() == true)
            OutputPath = dialog.FileName;
    }

    [RelayCommand]
    private async Task StartRenderAsync()
    {
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

        IsRendering = true;
        RenderProgress = 0;
        EtaText = "";
        StatusText = "Rendering startet...";

        var request = new RenderRequest(
            OutputPath: OutputPath,
            AudioPath: AudioPath,
            Quality: SelectedQuality,
            ResolutionWidth: Width,
            ResolutionHeight: Height,
            Fps: Fps
        );

        var result = await _api.StartRenderAsync(request);
        if (result != null)
        {
            _currentTaskId = result.TaskId;
            StatusText = $"Render-Task: {result.TaskId}";
            AppendLog("info", $"Render-Task gestartet: {result.TaskId}");
        }
        else
        {
            IsRendering = false;
            StatusText = "Rendering konnte nicht gestartet werden";
            AppendLog("error", "Render-Start fehlgeschlagen");
        }
    }

    [RelayCommand]
    private async Task CancelRenderAsync()
    {
        if (_currentTaskId == null)
            return;

        await _api.CancelRenderAsync(_currentTaskId);
        StatusText = "Abbruch angefordert...";
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
        var timeline = await _api.GetTimelineAsync();
        if (!string.IsNullOrEmpty(timeline?.AudioPath))
            AudioPath = timeline.AudioPath;
    }

    private void OnRenderProgress(object? sender, ProgressEventArgs e)
    {
        if (e.EventType != "render_progress") return;
        if (!string.IsNullOrEmpty(_currentTaskId) && !string.IsNullOrEmpty(e.TaskId) && e.TaskId != _currentTaskId) return;

        App.Current.Dispatcher.Invoke(() =>
        {
            RenderProgress = e.Percent;

            if (!string.IsNullOrWhiteSpace(e.Message))
                StatusText = e.Message;

            switch (e.Status)
            {
                case "completed":
                    IsRendering = false;
                    RenderProgress = 100;
                    EtaText = "";
                    StatusText = "Rendering abgeschlossen!";
                    AppendLog("info", "Rendering abgeschlossen");
                    break;

                case "cancelled":
                    IsRendering = false;
                    EtaText = "";
                    StatusText = "Rendering abgebrochen";
                    AppendLog("warn", "Rendering wurde abgebrochen");
                    break;

                case "failed":
                    IsRendering = false;
                    EtaText = "";
                    StatusText = string.IsNullOrWhiteSpace(e.Message) ? "Rendering fehlgeschlagen" : e.Message;
                    AppendLog("error", $"Rendering fehlgeschlagen: {StatusText}");
                    break;

                case "running":
                    if (e.Percent > 0)
                        EtaText = $"{e.Percent:F0}%";
                    break;
            }
        });
    }

    private void OnLogReceived(object? sender, LogEventArgs e)
    {
        App.Current.Dispatcher.Invoke(() => AppendLog(e.Level, e.Message));
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
}
