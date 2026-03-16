using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Shared Video-Library-Zustand für mehrere ViewModels.
/// Deduped parallele Video-Loads und cached das letzte Resultat.
/// </summary>
public class VideoLibraryStateService
{
    private readonly IApiClient _api;
    private readonly ILogger<VideoLibraryStateService> _logger;
    private readonly object _sync = new();
    private Task<IReadOnlyList<VideoClipInfo>?>? _inFlightRefresh;
    private DateTime _lastRefreshUtc = DateTime.MinValue;
    private static readonly TimeSpan WarmCacheDuration = TimeSpan.FromSeconds(2);

    public IReadOnlyList<VideoClipInfo> CurrentVideoClips { get; private set; } = [];

    public event EventHandler<IReadOnlyList<VideoClipInfo>>? VideoClipsChanged;

    public VideoLibraryStateService(IApiClient api, ILogger<VideoLibraryStateService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public Task<IReadOnlyList<VideoClipInfo>?> RefreshAsync(CancellationToken cancellationToken = default)
    {
        lock (_sync)
        {
            if (_inFlightRefresh != null)
                return _inFlightRefresh;

            if (CurrentVideoClips.Count > 0 && DateTime.UtcNow - _lastRefreshUtc < WarmCacheDuration)
                return Task.FromResult<IReadOnlyList<VideoClipInfo>?>(CurrentVideoClips);

            _inFlightRefresh = RefreshCoreAsync(cancellationToken);
            return _inFlightRefresh;
        }
    }

    public void Clear()
    {
        CurrentVideoClips = [];
        _lastRefreshUtc = DateTime.MinValue;
        VideoClipsChanged?.Invoke(this, CurrentVideoClips);
    }

    private async Task<IReadOnlyList<VideoClipInfo>?> RefreshCoreAsync(CancellationToken cancellationToken)
    {
        try
        {
            var clips = await _api.GetVideoClipsAsync(cancellationToken: cancellationToken).ConfigureAwait(false);
            if (clips == null)
                return null;

            CurrentVideoClips = clips;
            _lastRefreshUtc = DateTime.UtcNow;
            VideoClipsChanged?.Invoke(this, CurrentVideoClips);
            return CurrentVideoClips;
        }
        catch (Exception ex) when (ex is OperationCanceledException)
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Video-Library-Refresh fehlgeschlagen");
            return null;
        }
        finally
        {
            lock (_sync)
                _inFlightRefresh = null;
        }
    }
}
