using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Win32;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Video-Bibliothek.</summary>
public partial class VideoLibraryViewModel : ObservableObject, IDisposable
{
    private bool _disposed;
    private readonly IApiClient _api;
    private readonly VideoLibraryStateService _videoLibraryState;
    private readonly SSEClient _sseClient;
    private readonly IDialogService _dialogService;
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
    [ObservableProperty] private bool _isLoadingScenes;
    [ObservableProperty] private string _videoImportPath = string.Empty;
    [ObservableProperty] private bool _isDeleting;
    [ObservableProperty] private string _currentStep = "";
    [ObservableProperty] private int _currentStepIndex;
    [ObservableProperty] private int _currentStepTotal;
    [ObservableProperty] private double _currentClipProgress;
    [ObservableProperty] private int _analyzedCount;
    [ObservableProperty] private int _pendingCount;
    [ObservableProperty] private bool _isImporting;
    [ObservableProperty] private double _importProgress;

    public ObservableCollection<VideoClipModel> VideoClips { get; } = [];
    public ObservableCollection<SceneInfo> SelectedClipScenes { get; } = [];
    public ObservableCollection<VideoClipModel> SelectedClips { get; } = [];

    public VideoLibraryViewModel(IApiClient api, VideoLibraryStateService videoLibraryState, SSEClient sseClient, IDialogService dialogService)
    {
        _api = api;
        _videoLibraryState = videoLibraryState;
        _sseClient = sseClient;
        _dialogService = dialogService;

        _sseClient.ProgressReceived += OnSseProgressReceived;

        void HandleReload()
        {
            if (_isShuttingDown) return;
            _ = RequestClipReloadAsync();
        }

        void HandleProjectEnd()
        {
            if (_isShuttingDown) return;
            VideoImportPath = string.Empty;
            ClearClips();
        }

        WeakReferenceMessenger.Default.Register<VideoImportedMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<VideoLibraryRefreshMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<MediaLibraryRefreshMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<ProjectClosingMessage>(this, (_, _) => HandleProjectEnd());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) => HandleProjectEnd());
        WeakReferenceMessenger.Default.Register<AppShutdownMessage>(this, (_, _) => BeginShutdown());
    }

    partial void OnSelectedClipChanged(VideoClipModel? value)
    {
        SelectedClipScenes.Clear();
        if (value != null && value.IsAnalyzed)
        {
            _ = LoadScenesAsync(value.Id);
        }
    }

    private async Task LoadScenesAsync(int clipId)
    {
        try
        {
            IsLoadingScenes = true;
            var scenes = await _api.GetAsync<List<SceneInfo>>($"/video/scenes/{clipId}");
            if (scenes != null)
            {
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    foreach (var s in scenes) SelectedClipScenes.Add(s);
                });
            }
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Fehler beim Laden der Szenen: {ex.Message}");
        }
        finally
        {
            IsLoadingScenes = false;
        }
    }

    [RelayCommand]
    private void BrowseVideoPath()
    {
        var files = _dialogService.OpenFiles(
            "Video-Pfade auswählen",
            "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv|Alle Dateien|*.*"
        );

        if (files.Count > 0)
        {
            VideoImportPath = string.Join(";", files);
        }
    }

    [RelayCommand]
    private async Task ImportVideoFromPathAsync()
    {
        if (string.IsNullOrWhiteSpace(VideoImportPath)) return;

        var paths = VideoImportPath.Split(new[] { ';', '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries)
                                  .Select(p => p.Trim())
                                  .Where(p => !string.IsNullOrEmpty(p))
                                  .ToList();

        if (paths.Count == 0) return;

        IsAnalyzingAll = true;
        IsImporting = true;
        ImportProgress = 0.0;
        StatusText = $"Importiere {paths.Count} Videos von Pfad...";

        try
        {
            var result = await _api.ImportVideosAsync(paths);
            if (result != null)
            {
                StatusText = $"{result.Count} Videos erfolgreich importiert";
                VideoImportPath = string.Empty;
                await LoadClipsAsync();
                WeakReferenceMessenger.Default.Send(new VideoImportedMessage());
                WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Fehler beim Pfad-Import: {ex.Message}";
        }
        finally
        {
            IsAnalyzingAll = false;
            IsImporting = false;
        }
    }

    private void OnSseProgressReceived(object? sender, ProgressEventArgs e)
    {
        if (e.EventType is "analysis_progress" or "import_progress")
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                StatusText = e.Message;
                if (e.Percent >= 0)
                {
                    if (e.EventType == "import_progress")
                        ImportProgress = e.Percent;
                    else
                        CurrentClipProgress = e.Percent;
                }
                if (!string.IsNullOrEmpty(e.Step))
                    CurrentStep = e.Step;
                if (e.StepIndex > 0) CurrentStepIndex = e.StepIndex;
                if (e.StepTotal > 0) CurrentStepTotal = e.StepTotal;
            });
        }
    }

    [RelayCommand]
    private async Task DeleteSelectedAsync()
    {
        if (SelectedClips.Count == 0 || IsDeleting) return;
        IsDeleting = true;
        try
        {
            var ids = SelectedClips.Select(c => c.Id).ToList();
            StatusText = $"Loesche {ids.Count} Video-Clips...";
            var resp = ids.Count == 1
                ? await _api.DeleteVideoClipAsync(ids[0])
                : await _api.DeleteVideoClipsBatchAsync(ids);
            if (resp != null)
            {
                StatusText = $"{resp.DeletedCount} Video-Clips geloescht.";
                _videoLibraryState.Clear();
                await LoadClipsAsync();
                WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
            }
            else StatusText = "Delete fehlgeschlagen.";
        }
        finally { IsDeleting = false; }
    }

    [RelayCommand]
    private async Task DeleteAllVideosAsync()
    {
        if (VideoClips.Count == 0 || IsDeleting) return;
        IsDeleting = true;
        try
        {
            var ids = VideoClips.Select(c => c.Id).ToList();
            StatusText = $"Loesche ALLE {ids.Count} Video-Clips...";
            var resp = await _api.DeleteVideoClipsBatchAsync(ids);
            if (resp != null)
            {
                StatusText = $"{resp.DeletedCount} Video-Clips geloescht.";
                _videoLibraryState.Clear();
                await LoadClipsAsync();
                WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
            }
            else StatusText = "Delete-All fehlgeschlagen.";
        }
        finally { IsDeleting = false; }
    }

    [RelayCommand]
    private void SelectAllVideos()
    {
        SelectedClips.Clear();
        foreach (var c in VideoClips) SelectedClips.Add(c);
    }

    [RelayCommand]
    private async Task AnalyzeMarkedAsync()
    {
        if (SelectedClips.Count == 0 || IsAnalyzing) return;
        var clips = SelectedClips.ToList();
        IsAnalyzingAll = true;
        IsAnalyzing = true;
        var total = clips.Count;
        var done = 0;
        try
        {
            foreach (var clip in clips)
            {
                if (clip.IsAnalyzed) { done++; continue; }
                StatusText = $"Markierte: Analysiere {done + 1}/{total}: {clip.Name}...";
                AnalyzeAllProgress = (double)done / total * 100.0;
                var result = await _api.AnalyzeVideoAsync(clip.Id);
                if (result != null)
                {
                    clip.IsAnalyzed = true;
                    // L-M6: Auto-Reload scenes wenn der analysierte Clip aktuell selektiert ist.
                    if (SelectedClip != null && SelectedClip.Id == clip.Id)
                    {
                        await LoadScenesAsync(clip.Id).ConfigureAwait(false);
                    }
                }
                done++;
            }
            AnalyzeAllProgress = 100.0;
            StatusText = $"Markierte fertig: {total} Clips.";
            UpdateAnalyzedCounts();
        }
        finally
        {
            IsAnalyzingAll = false;
            IsAnalyzing = false;
        }
    }

    public void UpdateSelectedClips(System.Collections.IList selectedItems)
    {
        SelectedClips.Clear();
        foreach (var o in selectedItems)
            if (o is VideoClipModel m) SelectedClips.Add(m);
        DeleteSelectedCommand.NotifyCanExecuteChanged();
        AnalyzeMarkedCommand.NotifyCanExecuteChanged();
    }

    private void UpdateAnalyzedCounts()
    {
        AnalyzedCount = VideoClips.Count(c => c.IsAnalyzed);
        PendingCount = VideoClips.Count - AnalyzedCount;
    }

    [RelayCommand]
    private async Task ImportVideosAsync()
    {
        var files = _dialogService.OpenFiles(
            "Videos zur Bibliothek hinzufügen",
            "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv|Alle Dateien|*.*"
        );

        if (files.Count == 0) return;

        await ProcessVideoImportAsync(files);
    }

    [RelayCommand]
    private async Task ImportFolderAsync()
    {
        var folder = _dialogService.OpenFolder("Video-Ordner importieren");
        if (string.IsNullOrEmpty(folder)) return;

        StatusText = $"Scanne Ordner: {folder}...";
        var supported = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv",
        };

        try
        {
            var files = Directory.GetFiles(folder, "*.*", SearchOption.AllDirectories)
                .Where(f => supported.Contains(Path.GetExtension(f)))
                .ToList();

            if (files.Count == 0)
            {
                StatusText = "Keine unterstützten Video-Dateien im Ordner gefunden.";
                return;
            }

            await ProcessVideoImportAsync(files);
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Scannen des Ordners: " + ex.Message;
        }
    }

    private async Task ProcessVideoImportAsync(List<string> files)
    {
        IsAnalyzingAll = true;
        IsImporting = true;
        ImportProgress = 0.0;
        StatusText = $"Bereite Import von {files.Count} Dateien vor...";

        var validFiles = new List<string>();
        foreach (var file in files)
        {
            try
            {
                using var fs = File.OpenRead(file);
                validFiles.Add(file);
            }
            catch { /* Datei gesperrt oder nicht lesbar */ }
        }

        if (validFiles.Count == 0)
        {
            StatusText = "Import abgebrochen: Dateien konnten nicht gelesen werden.";
            IsAnalyzingAll = false;
            IsImporting = false;
            return;
        }

        try
        {
            StatusText = $"Importiere {validFiles.Count} Videos...";
            ImportProgress = 0.01;  // sichtbarer Start (0.00% Label)
            await Task.Delay(120).ConfigureAwait(true);  // UI render bevor Backend-Call
            // Backend emittiert per-file import_progress events - OnSseProgressReceived
            // setzt ImportProgress automatisch waehrend ImportVideosAsync laeuft.
            var result = await _api.ImportVideosAsync(validFiles);

            if (result != null)
            {
                StatusText = $"{result.Count} Videos erfolgreich importiert";
                ImportProgress = 100.0;
                await Task.Delay(450).ConfigureAwait(true);  // 100% kurz halten
                await LoadClipsAsync();
                WeakReferenceMessenger.Default.Send(new VideoImportedMessage());
                WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }
            else
            {
                StatusText = "Import fehlgeschlagen (Backend meldet Fehler)";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Kritischer Import-Fehler: {ex.Message}";
        }
        finally
        {
            IsAnalyzingAll = false;
            IsImporting = false;
        }
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

        bool acquired = false;
        if (!await _loadGate.WaitAsync(0, cancellationToken))
        {
            _reloadQueued = true;
            return;
        }
        acquired = true;

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
                        // L-M4: Motion-Felder fuer Detail-Card (null falls nicht analysiert).
                        AvgMotion = c.AvgMotion,
                        PeakMotion = c.PeakMotion,
                        MotionCategory = c.MotionCategory,
                        // L-N3: video_hash treibt HasCacheHash -> "CACHED"-Badge.
                        VideoHash = c.VideoHash,
                    };

                    if (_thumbnailCache.TryGetValue(c.Id, out var cachedThumb))
                        clip.Thumbnail = cachedThumb;
                    else if (_thumbnailFailureCache.Contains(c.Id))
                        clip.Thumbnail = null;

                    VideoClips.Add(clip);
                }
            });
            StatusText = $"{VideoClips.Count} Clips geladen";
            UpdateAnalyzedCounts();

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
            if (acquired)
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

                // L-M6: Auto-Reload scenes nach Analyse - OnSelectedClipChanged triggert
                // nur bei Selection-Wechsel, nicht bei IsAnalyzed-Update der aktuellen Selection.
                if (SelectedClip != null && SelectedClip.IsAnalyzed)
                {
                    await LoadScenesAsync(SelectedClip.Id).ConfigureAwait(false);
                }
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
                    // L-M6: Auto-Reload scenes wenn der analysierte Clip aktuell selektiert ist.
                    if (SelectedClip != null && SelectedClip.Id == clip.Id)
                    {
                        await LoadScenesAsync(clip.Id).ConfigureAwait(false);
                    }
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

        if (previous != null)
        {
            try { previous.Cancel(); } catch (ObjectDisposedException) { }
            try { previous.Dispose(); } catch (ObjectDisposedException) { }
        }
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

        if (active != null)
        {
            try { active.Cancel(); } catch (ObjectDisposedException) { }
            try { active.Dispose(); } catch (ObjectDisposedException) { }
        }
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
        _sseClient.ProgressReceived -= OnSseProgressReceived;
        WeakReferenceMessenger.Default.UnregisterAll(this);
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
