using Microsoft.Extensions.Logging;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;

namespace PBStudio.UI.Services;

/// <summary>
/// Verwaltet den Projekt-Zustand auf C#-Seite.
/// Kommuniziert mit dem Python Backend für Projekt-CRUD.
/// </summary>
public class ProjectService
{
    private readonly IApiClient _api;
    private readonly ILogger<ProjectService> _logger;

    public ProjectInfo? CurrentProject { get; private set; }
    public string? CurrentProjectName => CurrentProject?.Name;
    public string? CurrentProjectPath => CurrentProject?.Path;
    public bool HasProject => CurrentProject != null;

    public event EventHandler<ProjectInfo?>? ProjectChanged;

    public ProjectService(IApiClient api, ILogger<ProjectService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public async Task<bool> CreateProjectAsync(string name, string path)
    {
        var project = await _api.CreateProjectAsync(name, path).ConfigureAwait(false);
        if (project == null)
            return false;

        CurrentProject = project;
        ProjectChanged?.Invoke(this, CurrentProject);
        WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-opened"));
        _logger.LogInformation("Projekt erstellt: {Name} ({Path})", project.Name, project.Path);
        return true;
    }

    public async Task<bool> OpenProjectAsync(string path)
    {
        var project = await _api.OpenProjectAsync(path).ConfigureAwait(false);
        if (project == null)
            return false;

        CurrentProject = project;
        ProjectChanged?.Invoke(this, CurrentProject);
        WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-opened"));
        _logger.LogInformation("Projekt geöffnet: {Path}", path);
        return true;
    }

    public async Task<bool> SaveProjectAsync()
    {
        var result = await _api.SaveProjectAsync().ConfigureAwait(false);
        if (result?.Success != true)
            return false;

        CurrentProject = await _api.GetProjectInfoAsync().ConfigureAwait(false) ?? CurrentProject;
        ProjectChanged?.Invoke(this, CurrentProject);
        _logger.LogInformation("Projekt gespeichert: {Path}", CurrentProject?.Path);
        return true;
    }

    public async Task<bool> RefreshProjectInfoAsync()
    {
        var project = await _api.GetProjectInfoAsync().ConfigureAwait(false);
        CurrentProject = project;
        ProjectChanged?.Invoke(this, CurrentProject);
        
        if (project != null)
            WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-opened"));
            
        return project != null;
    }

    public async Task CloseProjectAsync()
    {
        await _api.CloseProjectAsync().ConfigureAwait(false);
        CurrentProject = null;
        ProjectChanged?.Invoke(this, null);
        WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("project-closed"));
        _logger.LogInformation("Projekt geschlossen");
    }
}
