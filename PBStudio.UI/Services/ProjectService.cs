using Microsoft.Extensions.Logging;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.Services;

/// <summary>
/// Verwaltet den Projekt-Zustand auf C#-Seite.
/// Kommuniziert mit dem Python Backend für Projekt-CRUD.
/// </summary>
public class ProjectService : IDisposable
{
    private readonly IApiClient _api;
    private readonly ILogger<ProjectService> _logger;
    private readonly SemaphoreSlim _projectTransitionGate = new(1, 1);
    private readonly object _projectLifetimeLock = new();
    private CancellationTokenSource _projectLifetimeCts = new();
    private long _projectGeneration;
    private int _projectTransitionCount;
    private bool _disposed;

    public ProjectInfo? CurrentProject { get; private set; }
    public string? CurrentProjectName => CurrentProject?.Name;
    public string? CurrentProjectPath => CurrentProject?.Path;
    public bool HasProject => CurrentProject != null;

    public event EventHandler<ProjectInfo?>? ProjectChanged;
    public event EventHandler? ProjectTransitionStarted;

    public ProjectService(IApiClient api, ILogger<ProjectService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public async Task<bool> CreateProjectAsync(string name, string path)
    {
        await _projectTransitionGate.WaitAsync().ConfigureAwait(false);
        var stableProject = CurrentProject;
        var completed = false;
        try
        {
            BeginProjectTransition();
            var project = await _api.CreateProjectAsync(name, path).ConfigureAwait(false);
            if (project == null)
                return false;

            SwitchToProject(project);
            completed = true;
            _logger.LogInformation("Projekt erstellt: {Name} ({Path})", project.Name, project.Path);
            return true;
        }
        finally
        {
            try
            {
                if (!completed)
                    RestoreStableProject(stableProject);
            }
            finally
            {
                _projectTransitionGate.Release();
            }
        }
    }

    public async Task<bool> OpenProjectAsync(string path)
    {
        await _projectTransitionGate.WaitAsync().ConfigureAwait(false);
        var stableProject = CurrentProject;
        var completed = false;
        try
        {
            BeginProjectTransition();
            var project = await _api.OpenProjectAsync(path).ConfigureAwait(false);
            if (project == null)
                return false;

            SwitchToProject(project);
            completed = true;
            _logger.LogInformation("Projekt geöffnet: {Path}", path);
            return true;
        }
        finally
        {
            try
            {
                if (!completed)
                    RestoreStableProject(stableProject);
            }
            finally
            {
                _projectTransitionGate.Release();
            }
        }
    }

    public async Task<bool> SaveProjectAsync()
    {
        var result = await _api.SaveProjectAsync().ConfigureAwait(false);
        if (result?.Success != true)
            return false;

        var refreshedProject = await _api.GetProjectInfoAsync().ConfigureAwait(false);
        RunOnUiThread(() =>
        {
            CurrentProject = refreshedProject ?? CurrentProject;
            ProjectChanged?.Invoke(this, CurrentProject);
        });
        _logger.LogInformation("Projekt gespeichert: {Path}", CurrentProject?.Path);
        return true;
    }

    public async Task<bool> RefreshProjectInfoAsync()
    {
        var project = await _api.GetProjectInfoAsync().ConfigureAwait(false);
        if (project == null)
            return false;

        SwitchToProject(project);
        return true;
    }

    public async Task<bool> CloseProjectAsync()
    {
        await _projectTransitionGate.WaitAsync().ConfigureAwait(false);
        var stableProject = CurrentProject;
        var completed = false;
        try
        {
            BeginProjectTransition();
            var result = await _api.CloseProjectAsync().ConfigureAwait(false);
            if (result?.Success != true)
                return false;

            RunOnUiThread(() =>
            {
                WeakReferenceMessenger.Default.Send(new ProjectClosingMessage());
                CurrentProject = null;
                EndProjectTransition();
                ProjectChanged?.Invoke(this, null);
                WeakReferenceMessenger.Default.Send(new ProjectClosedMessage());
            });
            completed = true;
            _logger.LogInformation("Projekt geschlossen");
            return true;
        }
        finally
        {
            try
            {
                if (!completed)
                    RestoreStableProject(stableProject);
            }
            finally
            {
                _projectTransitionGate.Release();
            }
        }
    }

    private void RestoreStableProject(ProjectInfo? stableProject)
    {
        RunOnUiThread(() =>
        {
            CurrentProject = stableProject;
            EndProjectTransition();
            ProjectChanged?.Invoke(this, CurrentProject);
            if (CurrentProject == null)
                WeakReferenceMessenger.Default.Send(new ProjectClosedMessage());
            else
                WeakReferenceMessenger.Default.Send(new ProjectOpenedMessage());
        });
    }

    private void SwitchToProject(ProjectInfo project)
    {
        RunOnUiThread(() =>
        {
            var isDirectSwitch = CurrentProject != null
                && !string.Equals(
                    CurrentProject.Path,
                    project.Path,
                    StringComparison.OrdinalIgnoreCase);

            if (isDirectSwitch)
            {
                WeakReferenceMessenger.Default.Send(new ProjectClosingMessage());
                CurrentProject = null;
                ProjectChanged?.Invoke(this, null);
                WeakReferenceMessenger.Default.Send(new ProjectClosedMessage());
            }

            CurrentProject = project;
            EndProjectTransition();
            ProjectChanged?.Invoke(this, CurrentProject);
            WeakReferenceMessenger.Default.Send(new ProjectOpenedMessage());
        });
    }

    public ProjectOperationContext CaptureOperationContext()
    {
        lock (_projectLifetimeLock)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            if (_projectTransitionCount > 0 || CurrentProject == null)
                throw new InvalidOperationException("Kein stabiler Projektkontext verfügbar");
            return new ProjectOperationContext(
                _projectGeneration,
                CurrentProject.Path,
                _projectLifetimeCts.Token);
        }
    }

    public bool IsCurrent(ProjectOperationContext context)
    {
        lock (_projectLifetimeLock)
        {
            return IsCurrentLocked(context);
        }
    }

    public bool TryCommit(
        ProjectOperationContext context,
        Action commit)
    {
        ArgumentNullException.ThrowIfNull(commit);
        lock (_projectLifetimeLock)
        {
            if (!IsCurrentLocked(context))
                return false;
            commit();
            return true;
        }
    }

    private bool IsCurrentLocked(ProjectOperationContext context)
        => !_disposed
            && _projectTransitionCount == 0
            && CurrentProject != null
            && !context.CancellationToken.IsCancellationRequested
            && context.Generation == _projectGeneration
            && string.Equals(
                context.ProjectPath,
                CurrentProject.Path,
                StringComparison.OrdinalIgnoreCase);

    private void BeginProjectTransition()
    {
        CancellationTokenSource previous;
        lock (_projectLifetimeLock)
        {
            if (_disposed)
                return;

            previous = _projectLifetimeCts;
            _projectLifetimeCts = new CancellationTokenSource();
            _projectGeneration++;
            _projectTransitionCount++;
        }

        previous.Cancel();
        previous.Dispose();
        RunOnUiThread(() => ProjectTransitionStarted?.Invoke(this, EventArgs.Empty));
    }

    private void EndProjectTransition()
    {
        lock (_projectLifetimeLock)
        {
            if (!_disposed && _projectTransitionCount > 0)
                _projectTransitionCount--;
        }
    }

    private static void RunOnUiThread(Action action)
    {
        var dispatcher = System.Windows.Application.Current?.Dispatcher;
        if (dispatcher == null || dispatcher.CheckAccess())
            action();
        else
            dispatcher.Invoke(action);
    }

    public void Dispose()
    {
        CancellationTokenSource lifetime;
        lock (_projectLifetimeLock)
        {
            if (_disposed)
                return;
            _disposed = true;
            lifetime = _projectLifetimeCts;
        }
        lifetime.Cancel();
        lifetime.Dispose();
    }
}

public readonly record struct ProjectOperationContext(
    long Generation,
    string ProjectPath,
    CancellationToken CancellationToken);
