using System.Collections.ObjectModel;
using System.IO;
using System.Windows;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Video-Bibliothek.</summary>
public partial class VideoLibraryViewModel : ObservableObject, IDisposable
{
    private bool _disposed;
    private readonly IApiClient _api;
    private readonly VideoLibraryStateService _videoLibraryState;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private readonly Dictionary<int, BitmapImage> _thumbnailCache = [];
    private readonly HashSet<int> _thumbnailFailureCache = [];
    private readonly object _loadCancellationLock = new();
    private CancellationTokenSource? _activeLoadCts;
    private int _loadVersion;
    private volatile bool _reloadQueued;
    private volatile bool _isShuttingDown;

    private const int ThumbnailBatchSize = 12;
    private static readonly TimeSpan ThumbnailBatchPause = TimeSpan.FromMilliseconds(150);

    [ObservableProperty] private VideoClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isAnalyzingAll;
    [ObservableProperty] private double _analyzeAllProgress;
    [ObservableProperty] private bool _isLoadingThumbnails;
    [ObservableProperty] private bool _isLoadingClips;

    public ObservableCollection<VideoClipModel> VideoClips { get; } = [];

    public VideoLibraryViewModel(IApiClient api, VideoLibraryStateService videoLibraryState)
    {
        _api = api;
        _videoLibraryState = videoLibraryState;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (_isShuttingDown)
                return;

            if (message.Value is "video-imported" or "video-library-refresh" or "media-library-refresh" or "project-opened")
                _ = RequestClipReloadAsync();
            else if (message.Value is "project-closing" or "project-closed")
                ClearClips();
            else if (message.Value is "app-shutdown")
                BeginShutdown();
        });
    }

    [RelayCommand]
    private async Task LoadClipsAsync()
    {
        if (_isShuttingDown)
            return;

        _reloadQueued = false;
        var version = Interlocked.Increment(ref _loadVersion);
        using var loadCts = ReplaceActiveLoadCts();
        var cancellationToken = loadCts.Token;

        if (!await _loadGate.WaitAsync(0, cancellationToken))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            IsLoadingClips = true;
            StatusText = "Video-Clips werden geladen...";

            var clips = await _videoLibraryState.RefreshAsync(cancellationToken);
            if (cancellationToken.IsCancellationRequested || version != _loadVersion || _isShuttingDown)
                return;

            if (clips == null)
            {
                StatusText = "Video-Clips laden fehlgeschlagen";
                return;
            }

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                VideoClips.Clear();
                foreach (var c in clips)
                {
                    var clip = new VideoClipModel
                    {
                        Id = c.Id,
                        Name = c.Name,
                        Path = c.Path,
                        DurationSeconds = c.DurationSeconds,
                        Width = c.Width,
                        Height = c.Height,
                        Fps = c.Fps,
                        Tags = c.Tags,
                        IsAnalyzed = c.IsAnalyzed,
                        ThumbnailAvailable = c.ThumbnailAvailable,
                    };

                    if (_thumbnailCache.TryGetValue(c.Id, out var cachedThumb))
                        clip.Thumbnail = cachedThumb;
                    else if (_thumbnailFailureCache.Contains(c.Id))
                        clip.Thumbnail = null;

                    VideoClips.Add(clip);
                }
            });
            StatusText = $"{VideoClips.Count} Clips geladen";

            await LoadAllThumbnailsAsync(version, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            if (!_isShuttingDown && version == _loadVersion)
                StatusText = "Ladevorgang abgebrochen";
        }
        finally
        {
            IsLoadingClips = false;
            if (_loadGate.CurrentCount == 0)
                _loadGate.Release();

            ClearActiveLoadCts(loadCts);
        }

        if (_reloadQueued && !_isShuttingDown)
            await LoadClipsAsync();
    }

    [RelayCommand]
    private async Task AnalyzeSelectedAsync()
    {
        if (SelectedClip == null) return;

        IsAnalyzing = true;
        StatusText = $"Analysiere: {SelectedClip.Name}...";

        try
        {
            var result = await _api.AnalyzeVideoAsync(SelectedClip.Id);
            if (result != null)
            {
                SelectedClip.IsAnalyzed = true;
                StatusText = $"Analyse fertig: {result.SceneCount} Scenes | Motion: {result.AvgMotion:F1}";
            }
            else
            {
                StatusText = "Analyse fehlgeschlagen";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Analyse fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsAnalyzing = false;
        }
    }

    [RelayCommand]
    private async Task AnalyzeAllAsync()
    {
        if (VideoClips.Count == 0) return;

        IsAnalyzingAll = true;
        IsAnalyzing = true;
        var total = VideoClips.Count;
        var done = 0;

        try
        {
            foreach (var clip in VideoClips.ToList())
            {
                if (clip.IsAnalyzed) { done++; continue; }

                StatusText = $"Analysiere {done + 1}/{total}: {clip.Name}...";
                AnalyzeAllProgress = (double)done / total * 100;

                var result = await _api.AnalyzeVideoAsync(clip.Id);
                if (result != null)
                {
                    clip.IsAnalyzed = true;
                }
                done++;
            }

            AnalyzeAllProgress = 100;
            StatusText = $"Alle {total} Clips analysiert";
        }
        catch (Exception ex)
        {
            StatusText = $"Analyse abgebrochen: {ex.Message}";
        }
        finally
        {
            IsAnalyzingAll = false;
            IsAnalyzing = false;
        }
    }

    private async Task LoadAllThumbnailsAsync(int version, CancellationToken cancellationToken)
    {
        IsLoadingThumbnails = true;
        try
        {
            var uncachedSincePause = 0;

            foreach (var clip in VideoClips.ToList())
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (version != _loadVersion || _isShuttingDown)
                    return;

                if (_thumbnailCache.TryGetValue(clip.Id, out var cached))
                {
                    clip.Thumbnail = cached;
                    continue;
                }

                if (_thumbnailFailureCache.Contains(clip.Id))
                    continue;

                var bytes = await _api.GetThumbnailAsync(clip.Id, cancellationToken);
                if (cancellationToken.IsCancellationRequested || version != _loadVersion || _isShuttingDown)
                    return;

                if (bytes != null && bytes.Length > 0)
                {
                    var bmp = BytesToBitmapImage(bytes);
                    _thumbnailCache[clip.Id] = bmp;
                    _thumbnailFailureCache.Remove(clip.Id);
                    clip.Thumbnail = bmp;
                }
                else
                {
                    _thumbnailFailureCache.Add(clip.Id);
                }

                uncachedSincePause++;
                if (uncachedSincePause >= ThumbnailBatchSize)
                {
                    uncachedSincePause = 0;
                    await Task.Delay(ThumbnailBatchPause, cancellationToken);
                }
            }
        }
        finally
        {
            IsLoadingThumbnails = false;
        }
    }

    private async Task RequestClipReloadAsync()
    {
        if (_isShuttingDown)
            return;

        _reloadQueued = true;
        if (IsLoadingClips)
            return;

        await LoadClipsAsync();
    }

    private void ClearClips()
    {
        CancelActiveLoad();
        Interlocked.Increment(ref _loadVersion);
        _reloadQueued = false;
        _videoLibraryState.Clear();
        _thumbnailFailureCache.Clear();
        _thumbnailCache.Clear();
        VideoClips.Clear();
        SelectedClip = null;
        StatusText = "Kein Projekt geöffnet";
        IsLoadingClips = false;
        IsLoadingThumbnails = false;
        IsAnalyzing = false;
        IsAnalyzingAll = false;
    }

    private void BeginShutdown()
    {
        if (_isShuttingDown)
            return;

        _isShuttingDown = true;
        CancelActiveLoad();
        Interlocked.Increment(ref _loadVersion);
        _reloadQueued = false;
        IsLoadingClips = false;
        IsLoadingThumbnails = false;
    }

    private CancellationTokenSource ReplaceActiveLoadCts()
    {
        var next = new CancellationTokenSource();
        CancellationTokenSource? previous;

        lock (_loadCancellationLock)
        {
            previous = _activeLoadCts;
            _activeLoadCts = next;
        }

        previous?.Cancel();
        previous?.Dispose();
        return next;
    }

    private void CancelActiveLoad()
    {
        CancellationTokenSource? active;

        lock (_loadCancellationLock)
        {
            active = _activeLoadCts;
            _activeLoadCts = null;
        }

        active?.Cancel();
        active?.Dispose();
    }

    private void ClearActiveLoadCts(CancellationTokenSource loadCts)
    {
        lock (_loadCancellationLock)
        {
            if (ReferenceEquals(_activeLoadCts, loadCts))
                _activeLoadCts = null;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
        BeginShutdown();
        _loadGate.Dispose();
    }

    private static BitmapImage BytesToBitmapImage(byte[] bytes)
    {
        var bmp = new BitmapImage();
        using var ms = new MemoryStream(bytes);
        bmp.BeginInit();
        bmp.CacheOption = BitmapCacheOption.OnLoad;
        bmp.StreamSource = ms;
        bmp.EndInit();
        bmp.Freeze();
        return bmp;
    }
}
