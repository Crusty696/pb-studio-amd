using System;
using System.Collections.ObjectModel;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für das neue Projekt-Dashboard (Workflow-Zentrum).</summary>
public partial class ProjectOverviewViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly ProjectService _projectService;
    private readonly AudioLibraryStateService _audioState;
    private bool _disposed;
    private int _refreshVersion;
    private int _refreshActive;
    private int _refreshQueued;

    [ObservableProperty] private string _projectName = "Kein Projekt";
    [ObservableProperty] private string _projectPath = "–";
    [ObservableProperty] private int _audioCount;
    [ObservableProperty] private int _videoCount;
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private bool _hasTimeline;
    [ObservableProperty] private string _statusText = "Bereit";
    [ObservableProperty] private bool _isBusy;

    public string TimelineStatusText =>
        ProjectName == "Kein Projekt"
            ? "Kein Projekt geöffnet"
            : HasTimeline
                ? "Video Timeline generiert"
                : "Noch keine Video-Timeline";

    public bool CanGenerateTimeline => ProjectName != "Kein Projekt" && !HasTimeline;

    partial void OnProjectNameChanged(string value)
    {
        OnPropertyChanged(nameof(TimelineStatusText));
        OnPropertyChanged(nameof(CanGenerateTimeline));
    }

    partial void OnHasTimelineChanged(bool value)
    {
        OnPropertyChanged(nameof(TimelineStatusText));
        OnPropertyChanged(nameof(CanGenerateTimeline));
    }

    public ProjectOverviewViewModel(
        IApiClient api,
        ProjectService projectService,
        AudioLibraryStateService audioState)
    {
        _api = api;
        _projectService = projectService;
        _audioState = audioState;

        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<MediaLibraryRefreshMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<VideoImportedMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<AudioImportedMessage>(this, (_, _) => _ = RefreshAsync());

        _ = RefreshAsync();
    }

    [RelayCommand]
    public async Task RefreshAsync()
    {
        if (_disposed)
            return;

        var version = Interlocked.Increment(ref _refreshVersion);
        if (Interlocked.CompareExchange(ref _refreshActive, 1, 0) != 0)
        {
            Interlocked.Exchange(ref _refreshQueued, 1);
            return;
        }

        IsBusy = true;

        try
        {
            var info = await _api.GetProjectInfoAsync();
            if (_disposed || version != Volatile.Read(ref _refreshVersion))
                return;

            if (info != null)
            {
                var audioClips = await _audioState.RefreshAsync();
                if (_disposed || version != Volatile.Read(ref _refreshVersion))
                    return;

                double duration = 0;
                if (audioClips != null)
                {
                    foreach (var c in audioClips)
                        duration = Math.Max(duration, c.DurationSeconds);
                }

                ProjectName = info.Name;
                ProjectPath = info.Path;
                AudioCount = info.AudioCount;
                VideoCount = info.VideoCount;
                HasTimeline = info.HasTimeline;
                TotalDuration = duration;
                StatusText = "Projekt-Status aktuell";
            }
            else
            {
                ResetState();
            }
        }
        catch (Exception ex)
        {
            if (!_disposed && version == Volatile.Read(ref _refreshVersion))
                StatusText = "Fehler beim Laden der Stats: " + ex.Message;
        }
        finally
        {
            if (!_disposed)
            {
                IsBusy = false;
                NotifyProjectCommandState();
            }

            Interlocked.Exchange(ref _refreshActive, 0);
            if (!_disposed && Interlocked.Exchange(ref _refreshQueued, 0) == 1)
                await RefreshAsync();
        }
    }

    [RelayCommand]
    private async Task CreateProjectAsync()
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
            StatusText = "Erstelle Projekt...";
            var success = await _projectService.CreateProjectAsync(name, dialog.FolderName);
            if (!success)
            {
                StatusText = "Fehler: Projekt konnte nicht erstellt werden. Prüfen Sie den Pfad (muss in Documents/PBStudio liegen).";
                return;
            }
            await RefreshAsync();
        }
    }

    [RelayCommand]
    private async Task OpenProjectAsync()
    {
        var dialog = new Microsoft.Win32.OpenFolderDialog
        {
            Title = "Projektordner öffnen",
            InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
        };

        if (dialog.ShowDialog() == true)
        {
            StatusText = "Öffne Projekt...";
            var success = await _projectService.OpenProjectAsync(dialog.FolderName);
            if (!success)
            {
                StatusText = "Fehler: Projekt konnte nicht geöffnet werden.";
                return;
            }
            await RefreshAsync();
        }
    }

    [RelayCommand(CanExecute = nameof(CanManageProject))]
    private async Task SaveProjectAsync()
    {
        StatusText = "Speichere Projekt...";
        var success = await _projectService.SaveProjectAsync();
        if (!success)
        {
            StatusText = "Fehler: Projekt konnte nicht gespeichert werden.";
            return;
        }

        await RefreshAsync();
        StatusText = "Projekt gespeichert.";
    }

    [RelayCommand(CanExecute = nameof(CanManageProject))]
    private async Task CloseProjectAsync()
    {
        var success = await _projectService.CloseProjectAsync();
        if (!success)
        {
            StatusText = "Fehler: Projekt konnte nicht geschlossen werden.";
            return;
        }

        ResetState();
        StatusText = "Projekt geschlossen.";
        NotifyProjectCommandState();
    }

    private bool CanManageProject() => _projectService.HasProject;

    private void NotifyProjectCommandState()
    {
        SaveProjectCommand.NotifyCanExecuteChanged();
        CloseProjectCommand.NotifyCanExecuteChanged();
    }

    private void ResetState()
    {
        ProjectName = "Kein Projekt";
        ProjectPath = "–";
        AudioCount = 0;
        VideoCount = 0;
        TotalDuration = 0;
        HasTimeline = false;
        StatusText = "Bereit für ein neues Projekt";
        NotifyProjectCommandState();
    }

    [RelayCommand]
    private void GoToDirector()
    {
        WeakReferenceMessenger.Default.Send(new NavigateDirectorMessage());
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        Interlocked.Increment(ref _refreshVersion);
        Interlocked.Exchange(ref _refreshQueued, 0);
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
