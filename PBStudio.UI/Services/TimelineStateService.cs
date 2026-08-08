using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Shared Timeline-Zustand für WPF ViewModels.
/// Deduped parallele Timeline-Loads und verteilt das letzte Resultat an Konsumenten.
/// </summary>
public class TimelineStateService
{
    private readonly IApiClient _api;
    private readonly ILogger<TimelineStateService> _logger;
    private readonly ProjectService _projectService;
    private readonly object _sync = new();

    private Task<TimelineResponse?>? _inFlightRefresh;
    private ProjectOperationContext? _inFlightContext;
    private long _refreshGeneration;

    public TimelineResponse? CurrentTimeline { get; private set; }

    public event EventHandler<TimelineResponse?>? TimelineChanged;

    public TimelineStateService(
        IApiClient api,
        ILogger<TimelineStateService> logger,
        ProjectService projectService)
    {
        _api = api;
        _logger = logger;
        _projectService = projectService;
    }

    public Task<TimelineResponse?> RefreshAsync()
    {
        ProjectOperationContext context;
        try
        {
            context = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            return Task.FromResult<TimelineResponse?>(null);
        }

        lock (_sync)
        {
            if (_inFlightRefresh != null && _inFlightContext == context)
                return _inFlightRefresh;

            var generation = ++_refreshGeneration;
            _inFlightContext = context;
            _inFlightRefresh = RefreshCoreAsync(context, generation);
            return _inFlightRefresh;
        }
    }

    public void Clear()
    {
        lock (_sync)
        {
            _refreshGeneration++;
            _inFlightRefresh = null;
            _inFlightContext = null;
            CurrentTimeline = null;
        }
        TimelineChanged?.Invoke(this, null);
    }

    private async Task<TimelineResponse?> RefreshCoreAsync(
        ProjectOperationContext context,
        long generation)
    {
        await Task.Yield();
        try
        {
            var timeline = await _api.GetTimelineAsync(
                context.CancellationToken).ConfigureAwait(false);
            var accepted = false;
            var committed = _projectService.TryCommit(context, () =>
            {
                lock (_sync)
                {
                    if (generation != _refreshGeneration)
                        return;
                    CurrentTimeline = timeline;
                    accepted = true;
                }
                if (accepted)
                    TimelineChanged?.Invoke(this, timeline);
            });
            if (!committed || !accepted)
                return null;
            return timeline;
        }
        catch (OperationCanceledException) when (context.CancellationToken.IsCancellationRequested)
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Timeline-Refresh fehlgeschlagen");
            return null;
        }
        finally
        {
            lock (_sync)
            {
                if (generation == _refreshGeneration)
                {
                    _inFlightRefresh = null;
                    _inFlightContext = null;
                }
            }
        }
    }
}
