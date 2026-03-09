using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Verwaltet den Projekt-Zustand auf C#-Seite.
/// Kommuniziert mit dem Python Backend für Projekt-CRUD.
/// </summary>
public class ProjectService
{
    private readonly ApiClient _api;
    private readonly ILogger<ProjectService> _logger;

    public string? CurrentProjectName { get; private set; }
    public string? CurrentProjectPath { get; private set; }
    public bool HasProject => CurrentProjectName != null;

    public event EventHandler<string?>? ProjectChanged;

    public ProjectService(ApiClient api, ILogger<ProjectService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public async Task<bool> CreateProjectAsync(string name, string path)
    {
        // Hier würde der API-Call hin
        await Task.CompletedTask; // CS1998 Fix: Stub hält async-Signatur für späteren API-Call
        CurrentProjectName = name;
        CurrentProjectPath = path;
        ProjectChanged?.Invoke(this, name);
        _logger.LogInformation("Projekt erstellt: {Name}", name);
        return true;
    }

    public async Task<bool> OpenProjectAsync(string path)
    {
        await Task.CompletedTask; // CS1998 Fix
        CurrentProjectPath = path;
        CurrentProjectName = System.IO.Path.GetFileName(path);
        ProjectChanged?.Invoke(this, CurrentProjectName);
        _logger.LogInformation("Projekt geöffnet: {Path}", path);
        return true;
    }

    public async Task CloseProjectAsync()
    {
        await Task.CompletedTask; // CS1998 Fix
        CurrentProjectName = null;
        CurrentProjectPath = null;
        ProjectChanged?.Invoke(this, null);
    }
}
