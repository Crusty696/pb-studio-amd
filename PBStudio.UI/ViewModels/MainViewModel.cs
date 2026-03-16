using System.Windows;
using System.Windows.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using Microsoft.Win32;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>Haupt-ViewModel für das MainWindow. Verwaltet Tab-Navigation und globalen Status.</summary>
public partial class MainViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private readonly SSEClient _sse;
    private readonly PythonBridgeService _bridge;
    private readonly ProjectService _projects;
    private bool _backendReadySent;
    private string? _lastProjectPath;

    [ObservableProperty] private int _selectedTabIndex;
    [ObservableProperty] private string _statusMessage = "Bereit";
    [ObservableProperty] private double _globalProgress;
    [ObservableProperty] private bool _isProgressVisible;
    [ObservableProperty] private string _gpuStatusText = "GPU: --";
    [ObservableProperty] private string _backendStatusText = "Backend: Startet...";
    [ObservableProperty] private Brush _backendStatusColor = Brushes.Orange;
    [ObservableProperty] private string _currentProjectName = "Kein Projekt";
    [ObservableProperty] private string _currentProjectPath = "";
    [ObservableProperty] private bool _hasProject;

    public MainViewModel(IApiClient api, SSEClient sse, PythonBridgeService bridge, ProjectService projects)
    {
        _api = api;
        _sse = sse;
        _bridge = bridge;
        _projects = projects;

        _bridge.StatusChanged += OnBackendStatusChanged;
        _sse.ProgressReceived += OnProgressReceived;
        _sse.GpuStatusReceived += OnGpuStatusReceived;
        _projects.ProjectChanged += OnProjectChanged;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value == "app-shutdown")
                _sse.StopListening();
        });

        _ = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        for (int i = 0; i < 60; i++)
        {
            if (_bridge.IsRunning)
            {
                BackendStatusText = "Backend: Online";
                BackendStatusColor = Brushes.LimeGreen;
                SendBackendReadyOnce();
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

    [RelayCommand]
    private async Task CreateProjectAsync()
    {
        var folderDialog = new OpenFolderDialog
        {
            Title = "Basisordner für neues Projekt wählen",
        };
        if (folderDialog.ShowDialog() != true || string.IsNullOrWhiteSpace(folderDialog.FolderName))
            return;

        var name = PromptDialog.Show("Neues Projekt", "Projektname:", "pb-studio-project");
        if (string.IsNullOrWhiteSpace(name))
            return;

        StatusMessage = "Projekt wird erstellt...";
        var ok = await _projects.CreateProjectAsync(name.Trim(), folderDialog.FolderName);
        if (!ok)
        {
            StatusMessage = "Projekt konnte nicht erstellt werden";
            MessageBox.Show("Projekt konnte nicht erstellt werden.", "PB Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        StatusMessage = $"Projekt erstellt: {_projects.CurrentProjectName}";
    }

    [RelayCommand]
    private async Task OpenProjectAsync()
    {
        var folderDialog = new OpenFolderDialog
        {
            Title = "Projektordner öffnen",
        };
        if (folderDialog.ShowDialog() != true || string.IsNullOrWhiteSpace(folderDialog.FolderName))
            return;

        StatusMessage = "Projekt wird geöffnet...";
        var ok = await _projects.OpenProjectAsync(folderDialog.FolderName);
        if (!ok)
        {
            StatusMessage = "Projekt konnte nicht geöffnet werden";
            MessageBox.Show("Projekt konnte nicht geöffnet werden.", "PB Studio", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        StatusMessage = $"Projekt geöffnet: {_projects.CurrentProjectName}";
    }

    [RelayCommand]
    private async Task SaveProjectAsync()
    {
        if (!HasProject)
            return;

        StatusMessage = "Projekt wird gespeichert...";
        var ok = await _projects.SaveProjectAsync();
        StatusMessage = ok
            ? $"Projekt gespeichert: {_projects.CurrentProjectName}"
            : "Projekt konnte nicht gespeichert werden";
    }

    [RelayCommand]
    private async Task CloseProjectAsync()
    {
        if (!HasProject)
            return;

        WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-closing"));
        await _projects.CloseProjectAsync();
        StatusMessage = "Projekt geschlossen";
    }

    private void OnProjectChanged(object? sender, ProjectInfo? project)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            var previousProjectPath = _lastProjectPath;
            var currentProjectPath = project?.Path;

            CurrentProjectName = project?.Name ?? "Kein Projekt";
            CurrentProjectPath = currentProjectPath ?? "";
            HasProject = project != null;
            _lastProjectPath = currentProjectPath;

            if (project == null)
            {
                if (!string.IsNullOrEmpty(previousProjectPath))
                    WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-closed"));

                return;
            }

            if (!string.Equals(previousProjectPath, currentProjectPath, StringComparison.OrdinalIgnoreCase))
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-opened"));
        });
    }

    private void OnBackendStatusChanged(object? sender, bool isRunning)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            BackendStatusText = isRunning ? "Backend: Online" : "Backend: Offline";
            BackendStatusColor = isRunning ? Brushes.LimeGreen : Brushes.Red;

            if (isRunning)
            {
                SendBackendReadyOnce();
                return;
            }

            _backendReadySent = false;
        });
    }

    private void SendBackendReadyOnce()
    {
        if (_backendReadySent)
            return;

        _backendReadySent = true;
        WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("backend-ready"));
    }

    private void OnProgressReceived(object? sender, ProgressEventArgs e)
    {
        App.Current.Dispatcher.Invoke(() =>
        {
            GlobalProgress = e.Percent;
            StatusMessage = string.IsNullOrWhiteSpace(e.Message) ? StatusMessage : e.Message;
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
