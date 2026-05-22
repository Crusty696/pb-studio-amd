using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Shared Audio-Library-Zustand für mehrere ViewModels.
/// Deduped parallele Audio-Loads und cached das letzte Resultat.
/// </summary>
public class AudioLibraryStateService
{
    private readonly IApiClient _api;
    private readonly ILogger<AudioLibraryStateService> _logger;
    private readonly object _sync = new();
    private Task<IReadOnlyList<AudioClipInfo>?>? _inFlightRefresh;
    private DateTime _lastRefreshUtc = DateTime.MinValue;
    private static readonly TimeSpan WarmCacheDuration = TimeSpan.FromSeconds(2);

    public IReadOnlyList<AudioClipInfo> CurrentAudioClips { get; private set; } = [];

    public event EventHandler<IReadOnlyList<AudioClipInfo>>? AudioClipsChanged;

    public AudioLibraryStateService(IApiClient api, ILogger<AudioLibraryStateService> logger)
    {
        _api = api;
        _logger = logger;
    }

    public Task<IReadOnlyList<AudioClipInfo>?> RefreshAsync()
    {
        lock (_sync)
        {
            if (_inFlightRefresh != null)
                return _inFlightRefresh;

            if (CurrentAudioClips.Count > 0 && DateTime.UtcNow - _lastRefreshUtc < WarmCacheDuration)
                return Task.FromResult<IReadOnlyList<AudioClipInfo>?>(CurrentAudioClips);

            _inFlightRefresh = RefreshCoreAsync();
            return _inFlightRefresh;
        }
    }

    public void Clear()
    {
        CurrentAudioClips = [];
        _lastRefreshUtc = DateTime.MinValue;
        AudioClipsChanged?.Invoke(this, CurrentAudioClips);
    }

    private async Task<IReadOnlyList<AudioClipInfo>?> RefreshCoreAsync()
    {
        try
        {
            var allClips = new List<AudioClipInfo>();
            int page = 1;
            int limit = 200;

            while (true)
            {
                var clips = await _api.GetAudioClipsAsync(page: page, limit: limit).ConfigureAwait(false);
                if (clips == null)
                    return null;

                allClips.AddRange(clips);
                if (clips.Count < limit)
                    break;

                page++;
            }

            CurrentAudioClips = allClips;
            _lastRefreshUtc = DateTime.UtcNow;
            AudioClipsChanged?.Invoke(this, CurrentAudioClips);
            return CurrentAudioClips;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Audio-Library-Refresh fehlgeschlagen");
            return null;
        }
        finally
        {
            lock (_sync)
                _inFlightRefresh = null;
        }
    }
}
