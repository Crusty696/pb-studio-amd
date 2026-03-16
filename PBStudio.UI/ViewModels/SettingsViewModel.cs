using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Einstellungen.</summary>
public partial class SettingsViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private string _gpuName = "Wird geladen...";
    [ObservableProperty] private double _vramTotal;
    [ObservableProperty] private double _vramUsed;
    [ObservableProperty] private double _temperature;
    [ObservableProperty] private string _driverVersion = "";
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _backendOnline;

    public SettingsViewModel(IApiClient api)
    {
        _api = api;
        StatusText = "Backend: Startet...";

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value == "backend-ready")
                _ = RefreshAsync();
            else if (message.Value == "app-shutdown")
                BackendOnline = false;
        });

        _ = RefreshAsync();
    }

    [RelayCommand]
    private async Task RefreshAsync()
    {
        var health = await _api.GetHealthAsync();
        BackendOnline = health != null;

        var gpu = await _api.GetGpuStatusAsync();
        if (gpu != null)
        {
            GpuName = gpu.Name;
            VramTotal = gpu.VramTotalMb;
            VramUsed = gpu.VramUsedMb;
            Temperature = gpu.TemperatureC;
            DriverVersion = gpu.DriverVersion;
        }
        StatusText = BackendOnline ? "Backend: Online" : "Backend: Offline";
    }

    [RelayCommand]
    private async Task CleanupGpuAsync()
    {
        StatusText = "VRAM aufräumen...";
        await _api.CleanupGpuAsync();
        StatusText = "VRAM aufgeräumt";
    }
}
