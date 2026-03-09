using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
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

    public List<string> QualityOptions { get; } = ["preview", "standard", "high", "ultra"];

    public ProductionViewModel(IApiClient api, SSEClient sse)
    {
        _api = api;
        _sse = sse;
        _sse.ProgressReceived += OnRenderProgress;
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
        if (string.IsNullOrEmpty(OutputPath))
        {
            StatusText = "Kein Ausgabepfad gewählt";
            return;
        }

        // Audio-Pfad aus Timeline laden falls nicht manuell gesetzt
        if (string.IsNullOrEmpty(AudioPath))
        {
            var timeline = await _api.GetTimelineAsync();
            if (timeline?.AudioPath != null)
                AudioPath = timeline.AudioPath;
        }
        if (string.IsNullOrEmpty(AudioPath))
        {
            StatusText = "Kein Audio-Pfad vorhanden. Bitte zuerst eine Cut-Liste generieren.";
            return;
        }

        IsRendering = true;
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
        }
        else
        {
            IsRendering = false;
            StatusText = "Rendering konnte nicht gestartet werden";
        }
    }

    [RelayCommand]
    private async Task CancelRenderAsync()
    {
        if (_currentTaskId == null) return;
        await _api.CancelRenderAsync(_currentTaskId);
        IsRendering = false;
        StatusText = "Rendering abgebrochen";
    }

    private void OnRenderProgress(object? sender, ProgressEventArgs e)
    {
        if (e.EventType != "render_progress") return;
        App.Current.Dispatcher.Invoke(() =>
        {
            RenderProgress = e.Percent;
            StatusText = e.Message;
            if (e.Percent >= 100)
            {
                IsRendering = false;
                StatusText = "Rendering abgeschlossen!";
            }
        });
    }
}
