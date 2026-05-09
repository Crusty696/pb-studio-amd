using System;
using System.Collections.ObjectModel;
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
    private readonly VideoLibraryStateService _videoState;
    private bool _disposed;

    [ObservableProperty] private string _projectName = "Kein Projekt";
    [ObservableProperty] private string _projectPath = "–";
    [ObservableProperty] private int _audioCount;
    [ObservableProperty] private int _videoCount;
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private bool _hasTimeline;
    [ObservableProperty] private string _statusText = "Bereit";
    [ObservableProperty] private bool _isBusy;

    public ProjectOverviewViewModel(IApiClient api, ProjectService projectService,
                                   AudioLibraryStateService audioState, VideoLibraryStateService videoState)
    {
        _api = api;
        _projectService = projectService;
        _audioState = audioState;
        _videoState = videoState;

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
        if (IsBusy) return;
        IsBusy = true;

        try
        {
            var info = await _api.GetProjectInfoAsync();
            if (info != null)
            {
                ProjectName = info.Name;
                ProjectPath = info.Path;
                AudioCount = info.AudioCount;
                VideoCount = info.VideoCount;
                HasTimeline = info.HasTimeline;

                // Weitere Stats laden
                var audioClips = await _audioState.RefreshAsync();
                if (audioClips != null)
                {
                    double dur = 0;
                    foreach (var c in audioClips) dur = Math.Max(dur, c.DurationSeconds);
                    TotalDuration = dur;
                }

                StatusText = "Projekt-Status aktuell";
            }
            else
            {
                ResetState();
            }
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Laden der Stats: " + ex.Message;
        }
        finally
        {
            IsBusy = false;
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

    private void ResetState()
    {
        ProjectName = "Kein Projekt";
        ProjectPath = "–";
        AudioCount = 0;
        VideoCount = 0;
        TotalDuration = 0;
        HasTimeline = false;
        StatusText = "Bereit für ein neues Projekt";
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
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
