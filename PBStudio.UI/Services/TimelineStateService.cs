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
    private readonly object _sync = new();

    private Task<TimelineResponse?>? _inFlightRefresh;

    public TimelineResponse? CurrentTimeline { get; private set; }

    public event EventHandler<TimelineResponse?>? TimelineChanged;

    public TimelineStateService(IApiClient api, ILogger<TimelineStateService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public Task<TimelineResponse?> RefreshAsync()
    {
        lock (_sync)
        {
            if (_inFlightRefresh != null)
                return _inFlightRefresh;

            _inFlightRefresh = RefreshCoreAsync();
            return _inFlightRefresh;
        }
    }

    public void Clear()
    {
        CurrentTimeline = null;
        TimelineChanged?.Invoke(this, null);
    }

    private async Task<TimelineResponse?> RefreshCoreAsync()
    {
        try
        {
            var timeline = await _api.GetTimelineAsync().ConfigureAwait(false);
            CurrentTimeline = timeline;
            TimelineChanged?.Invoke(this, timeline);
            return timeline;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Timeline-Refresh fehlgeschlagen");
            return null;
        }
        finally
        {
            lock (_sync)
                _inFlightRefresh = null;
        }
    }
}
