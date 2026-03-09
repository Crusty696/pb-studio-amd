using System.Windows.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>Haupt-ViewModel für das MainWindow. Verwaltet Tab-Navigation und globalen Status.</summary>
public partial class MainViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private readonly SSEClient _sse;
    private readonly PythonBridgeService _bridge;

    [ObservableProperty] private int _selectedTabIndex;
    [ObservableProperty] private string _statusMessage = "Bereit";
    [ObservableProperty] private double _globalProgress;
    [ObservableProperty] private bool _isProgressVisible;
    [ObservableProperty] private string _gpuStatusText = "GPU: --";
    [ObservableProperty] private string _backendStatusText = "Backend: Startet...";
    [ObservableProperty] private Brush _backendStatusColor = Brushes.Orange;

    public MainViewModel(IApiClient api, SSEClient sse, PythonBridgeService bridge)
    {
        _api = api;
        _sse = sse;
        _bridge = bridge;

        _bridge.StatusChanged += OnBackendStatusChanged;
        _sse.ProgressReceived += OnProgressReceived;
        _sse.GpuStatusReceived += OnGpuStatusReceived;

        _ = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        // Warte auf Backend
        for (int i = 0; i < 60; i++)
        {
            var health = await _api.GetHealthAsync();
            if (health != null)
            {
                BackendStatusText = "Backend: Online";
                BackendStatusColor = Brushes.LimeGreen;
                _sse.StartListening();
                await RefreshGpuStatusAsync();
                return;
            }
            await Task.Delay(500);
        }
        BackendStatusText = "Backend: Offline";
        BackendStatusColor = Brushes.Red;
    }

    private void OnBackendStatusChanged(object? sender, bool isRunning)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            BackendStatusText = isRunning ? "Backend: Online" : "Backend: Offline";
            BackendStatusColor = isRunning ? Brushes.LimeGreen : Brushes.Red;
        });
    }

    private void OnProgressReceived(object? sender, ProgressEventArgs e)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            GlobalProgress = e.Percent;
            StatusMessage = e.Message;
            IsProgressVisible = e.Percent is > 0 and < 100;
        });
    }

    private void OnGpuStatusReceived(object? sender, GpuEventArgs e)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            GpuStatusText = $"GPU: {e.VramUsedMb}/{e.VramTotalMb} MB | {e.TemperatureC}°C";
        });
    }

    private async Task RefreshGpuStatusAsync()
    {
        var gpu = await _api.GetGpuStatusAsync();
        if (gpu != null)
            GpuStatusText = $"GPU: {gpu.VramUsedMb}/{gpu.VramTotalMb} MB";
    }
}
