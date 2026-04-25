using System.Windows;
using System.Windows.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
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

    [ObservableProperty]
    private string _gpuStatusText = "GPU: Unbekannt";

    public string? CurrentProjectName => _projects.CurrentProjectName;
    public string? CurrentProjectPath => _projects.CurrentProjectPath;
    public bool HasProject => _projects.HasProject;

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
        _projects.ProjectChanged += OnProjectChanged;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (r, m) =>
        {
            if (m.Value == "backend-ready")
            {
                _ = InitializeAsync();
            }
        });

        _ = InitializeAsync();
    }

    [RelayCommand]
    private async Task CreateProject()
    {
        var name = PromptDialog.Show("Neues Projekt", "Projektname:");
        if (string.IsNullOrEmpty(name)) return;

        var dialog = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Basisverzeichnis für Projekt wählen",
            InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
        };

        if (dialog.ShowDialog() == true)
        {
            var success = await _projects.CreateProjectAsync(name, dialog.FolderName);
            if (!success)
            {
                MessageBox.Show("Projekt konnte nicht erstellt werden.", "PB Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            StatusMessage = $"Projekt erstellt: {CurrentProjectName}";
            OnPropertyChanged(nameof(CurrentProjectName));
            OnPropertyChanged(nameof(CurrentProjectPath));
            OnPropertyChanged(nameof(HasProject));
        }
    }

    [RelayCommand]
    private async Task OpenProject()
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Projektordner öffnen",
            InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
        };

        if (dialog.ShowDialog() == true)
        {
            var success = await _projects.OpenProjectAsync(dialog.FolderName);
            if (success)
            {
                StatusMessage = $"Projekt geöffnet: {CurrentProjectName}";
                OnPropertyChanged(nameof(CurrentProjectName));
                OnPropertyChanged(nameof(CurrentProjectPath));
                OnPropertyChanged(nameof(HasProject));
            }
        }
    }

    [RelayCommand]
    private async Task SaveProject()
    {
        var success = await _projects.SaveProjectAsync();
        if (success)
        {
            StatusMessage = "Projekt gespeichert.";
        }
    }

    [RelayCommand]
    private async Task CloseProject()
    {
        await _projects.CloseProjectAsync();
        StatusMessage = "Projekt geschlossen.";
        OnPropertyChanged(nameof(CurrentProjectName));
        OnPropertyChanged(nameof(CurrentProjectPath));
        OnPropertyChanged(nameof(HasProject));
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

    private void OnProjectChanged(object? sender, ProjectInfo? e)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            OnPropertyChanged(nameof(CurrentProjectName));
            OnPropertyChanged(nameof(CurrentProjectPath));
            OnPropertyChanged(nameof(HasProject));
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
        _projects.ProjectChanged -= OnProjectChanged;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
    }
}
