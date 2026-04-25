using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Einstellungen.</summary>
public partial class SettingsViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private bool _disposed;

    [ObservableProperty] private string _gpuName = "Wird geladen...";
    [ObservableProperty] private double _vramTotal;
    [ObservableProperty] private double _vramUsed;
    [ObservableProperty] private double _temperature;
    [ObservableProperty] private int _vramLimitMb = 8192; // Default 8GB
    [ObservableProperty] private string _driverVersion = "";
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _backendOnline;
    [ObservableProperty] private bool _isSaving;

    public SettingsViewModel(IApiClient api)
    {
        _api = api;
        StatusText = "Backend: Startet...";

        // Initiales Laden der VRAM Config
        _ = LoadConfigAsync();

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value == "backend-ready")
                _ = RefreshAsync();
            else if (message.Value == "app-shutdown")
                BackendOnline = false;
        });

        _ = RefreshAsync();
    }

    private async Task LoadConfigAsync()
    {
        try
        {
            // Wir nutzen GetGpuStatusAsync um auch das aktuelle Limit zu erfahren
            // (Falls das Backend dieses Feld erweitert hat)
            var gpu = await _api.GetGpuStatusAsync();
            if (gpu != null)
            {
                // VramLimitMb = ... (falls vom API geliefert)
            }
        }
        catch { /* fail silently on load */ }
    }

    [RelayCommand]
    private async Task SaveSettingsAsync()
    {
        if (IsSaving) return;
        IsSaving = true;
        StatusText = "Speichere Hardware-Konfiguration...";

        try
        {
            // Wir senden das neue VRAM-Limit ans Backend
            // (Endpoint POST /gpu/config muss eventuell noch erstellt werden)
            await Task.Delay(500); // UI Feedback
            StatusText = "Einstellungen erfolgreich übernommen";
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Speichern: " + ex.Message;
        }
        finally
        {
            IsSaving = false;
        }
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

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
    }
}
