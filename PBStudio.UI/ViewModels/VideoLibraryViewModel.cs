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
    private readonly ProjectService _projectService;
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
    private int? _activeAnalysisClipId;
    private readonly SemaphoreSlim _analysisGate = new(1, 1);
    private readonly object _analysisCancellationLock = new();
    private CancellationTokenSource? _activeAnalysisCts;
    private ProjectOperationContext? _activeAnalysisProjectContext;
    private long _analysisSequence;
    private int _sceneLoadSequence;

    private const int ThumbnailBatchSize = 12;
    private static readonly TimeSpan ThumbnailBatchPause = TimeSpan.FromMilliseconds(150);
    private readonly record struct AnalysisTarget(int Id, string Name, string Path);
    private readonly record struct AnalysisScope(
        long Sequence,
        ProjectOperationContext Project,
        CancellationTokenSource Cancellation);

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
    [ObservableProperty] private bool _stepDetectScenes = true;
    [ObservableProperty] private bool _stepAnalyzeMotion = true;
    [ObservableProperty] private bool _stepGenerateEmbeddings = true;
    [ObservableProperty] private bool _stepGenerateCaptions = true;

    public ObservableCollection<VideoClipModel> VideoClips { get; } = [];
    public ObservableCollection<SceneInfo> SelectedClipScenes { get; } = [];
    public ObservableCollection<VideoClipModel> SelectedClips { get; } = [];

    public VideoLibraryViewModel(
        IApiClient api,
        VideoLibraryStateService videoLibraryState,
        ProjectService projectService,
        SSEClient sseClient,
        IDialogService dialogService)
    {
        _api = api;
        _videoLibraryState = videoLibraryState;
        _projectService = projectService;
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
        Interlocked.Increment(ref _sceneLoadSequence);
        IsLoadingScenes = false;
        SelectedClipScenes.Clear();
        if (value != null && value.IsAnalyzed)
        {
            _ = LoadScenesAsync(value.Id);
        }
    }

    private async Task LoadScenesAsync(int clipId)
    {
        var sequence = Interlocked.Increment(ref _sceneLoadSequence);
        ProjectOperationContext projectContext;
        try
        {
            projectContext = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            return;
        }

        try
        {
            IsLoadingScenes = true;
            var scenes = await _api.GetAsync<List<SceneInfo>>(
                $"/video/scenes/{clipId}",
                projectContext.CancellationToken);
            if (scenes != null
                && sequence == Volatile.Read(ref _sceneLoadSequence)
                && _projectService.IsCurrent(projectContext)
                && SelectedClip?.Id == clipId)
            {
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    if (sequence != Volatile.Read(ref _sceneLoadSequence)
                        || !_projectService.IsCurrent(projectContext)
                        || SelectedClip?.Id != clipId)
                    {
                        return;
                    }

                    // AP3.3 (Audit 2026-06-10): Clear vor Add — Re-Analyse desselben
                    // Clips hängte die Szenen sonst doppelt an. SceneIndex (1-basiert)
                    // client-seitig setzen, Backend sendet keinen Index.
                    SelectedClipScenes.Clear();
                    var idx = 1;
                    foreach (var s in scenes)
                    {
                        s.SceneIndex = idx++;
                        SelectedClipScenes.Add(s);
                    }
                });
            }
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Fehler beim Laden der Szenen: {ex.Message}");
        }
        finally
        {
            if (sequence == Volatile.Read(ref _sceneLoadSequence)
                && _projectService.IsCurrent(projectContext))
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
        if (e.EventType == "analysis_progress")
        {
            if (!IsActiveAnalysisEvent(e.ClipId))
                return;
        }
        else if (e.EventType == "import_progress")
        {
            if (!IsImporting || e.TaskId != "video_import")
                return;
        }
        else
        {
            return;
        }

        if (e.EventType is "analysis_progress" or "import_progress")
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                if (e.EventType == "analysis_progress" && !IsActiveAnalysisEvent(e.ClipId))
                    return;

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

    private bool IsActiveAnalysisEvent(int clipId)
    {
        lock (_analysisCancellationLock)
        {
            return IsAnalyzing
                && _activeAnalysisClipId == clipId
                && _activeAnalysisProjectContext is { } projectContext
                && _projectService.IsCurrent(projectContext)
                && _activeAnalysisCts is { IsCancellationRequested: false };
        }
    }

    [RelayCommand]
    private async Task DeleteSelectedAsync()
    {
        var markedClips = VideoClips.Where(c => c.IsMarked).ToList();
        if (markedClips.Count == 0 || IsDeleting) return;
        var confirmationMessage = markedClips.Count == 1
            ? $"Video-Clip \"{markedClips[0].Name}\" (ID {markedClips[0].Id}) dauerhaft löschen?"
            : $"{markedClips.Count} ausgewählte Video-Clips dauerhaft löschen?";
        if (!_dialogService.ConfirmDestructiveAction("Video-Clips löschen", confirmationMessage))
            return;

        IsDeleting = true;
        try
        {
            var ids = markedClips.Select(c => c.Id).ToList();
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
        catch (Exception ex)
        {
            StatusText = $"Löschen fehlgeschlagen: {ex.Message}";
        }
        finally { IsDeleting = false; }
    }

    [RelayCommand]
    private async Task DeleteAllVideosAsync()
    {
        if (VideoClips.Count == 0 || IsDeleting) return;
        var clips = VideoClips.ToList();
        if (!_dialogService.ConfirmDestructiveAction(
                "Alle Video-Clips löschen",
                $"ALLE {clips.Count} Video-Clips dauerhaft löschen?"))
        {
            return;
        }

        IsDeleting = true;
        try
        {
            var ids = clips.Select(c => c.Id).ToList();
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
        catch (Exception ex)
        {
            StatusText = $"Löschen fehlgeschlagen: {ex.Message}";
        }
        finally { IsDeleting = false; }
    }

    [RelayCommand]
    private void SelectAllVideos()
    {
        bool anyUnmarked = VideoClips.Any(c => !c.IsMarked);
        foreach (var c in VideoClips)
        {
            c.IsMarked = anyUnmarked;
        }
        DeleteSelectedCommand.NotifyCanExecuteChanged();
        AnalyzeMarkedCommand.NotifyCanExecuteChanged();
    }

    /// <summary>Schreibt die Motion-Ergebnisse aus dem Analyse-Response ins Clip-Model,
    /// damit die Detail-Card direkt nach der Analyse Motion zeigt (sonst "Keine Motion-Daten"
    /// bis zum naechsten Full-Reload, obwohl das Backend die Daten bereits persistiert hat).</summary>
    private static void ApplyMotionResult(VideoClipModel clip, VideoAnalysisResult result)
    {
        var motionStatus = result.StageStatus != null
            && result.StageStatus.TryGetValue("motion", out var motionValue)
                ? motionValue
                : null;
        if (motionStatus is "failed" or "partial")
        {
            clip.AvgMotion = null;
            clip.PeakMotion = null;
            clip.MotionCategory = null;
        }
        else if (result.Motion != null)
        {
            clip.AvgMotion = result.Motion.AvgMotion;
            clip.PeakMotion = result.Motion.PeakMotion;
            clip.MotionCategory = result.Motion.MotionCategory;
        }
        else if (result.AvgMotion > 0)
        {
            clip.AvgMotion = result.AvgMotion;
        }

        var embeddingStatus = result.StageStatus != null
            && result.StageStatus.TryGetValue("embedding", out var embeddingValue)
                ? embeddingValue
                : null;
        if (!string.Equals(embeddingStatus, "skipped", StringComparison.OrdinalIgnoreCase))
        {
            clip.HasEmbedding = result.HasEmbedding;
            clip.EmbeddingDim = result.EmbeddingDim > 0 ? result.EmbeddingDim : null;
            clip.EmbeddingSamples = result.EmbeddingSamples > 0 ? result.EmbeddingSamples : null;
        }
    }

    private static bool IsCompleted(VideoAnalysisResult result)
        => string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase);

    private static string AnalysisFailure(VideoAnalysisResult result)
    {
        if (result.StageErrors is { Count: > 0 })
            return string.Join(", ", result.StageErrors.Select(item => $"{item.Key}: {item.Value}"));
        return $"Backend-Status: {result.Status}";
    }

    private async Task ExecuteAnalysisAsync(
        bool isBatch,
        Func<AnalysisScope, Task> operation)
    {
        ProjectOperationContext projectContext;
        try
        {
            projectContext = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            StatusText = "Analyse nicht gestartet: kein stabiler Projektkontext.";
            return;
        }

        using var analysisCts = CancellationTokenSource.CreateLinkedTokenSource(
            projectContext.CancellationToken);
        if (!await _analysisGate.WaitAsync(0))
        {
            StatusText = "Analyse nicht gestartet: bereits ein Videoanalyse-Job aktiv.";
            return;
        }

        var scope = new AnalysisScope(
            Interlocked.Increment(ref _analysisSequence),
            projectContext,
            analysisCts);
        lock (_analysisCancellationLock)
        {
            _activeAnalysisCts = analysisCts;
            _activeAnalysisProjectContext = projectContext;
            _activeAnalysisClipId = null;
        }
        IsAnalyzing = true;
        IsAnalyzingAll = isBatch;

        try
        {
            await operation(scope);
        }
        catch (OperationCanceledException) when (analysisCts.IsCancellationRequested)
        {
            if (IsAnalysisScopeCurrent(scope))
                StatusText = "Videoanalyse abgebrochen.";
        }
        catch (Exception ex)
        {
            if (IsAnalysisScopeCurrent(scope))
                StatusText = $"Videoanalyse fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            var ownsCurrent = false;
            lock (_analysisCancellationLock)
            {
                if (ReferenceEquals(_activeAnalysisCts, analysisCts)
                    && scope.Sequence == Volatile.Read(ref _analysisSequence))
                {
                    _activeAnalysisCts = null;
                    _activeAnalysisProjectContext = null;
                    _activeAnalysisClipId = null;
                    ownsCurrent = true;
                }
            }

            if (ownsCurrent)
            {
                IsAnalyzingAll = false;
                IsAnalyzing = false;
            }
            _analysisGate.Release();
        }
    }

    private bool IsAnalysisScopeCurrent(AnalysisScope scope)
    {
        lock (_analysisCancellationLock)
        {
            return scope.Sequence == Volatile.Read(ref _analysisSequence)
                && ReferenceEquals(_activeAnalysisCts, scope.Cancellation)
                && !scope.Cancellation.IsCancellationRequested
                && _projectService.IsCurrent(scope.Project);
        }
    }

    private bool SetActiveAnalysisClip(AnalysisScope scope, int clipId)
    {
        lock (_analysisCancellationLock)
        {
            if (scope.Sequence != Volatile.Read(ref _analysisSequence)
                || !ReferenceEquals(_activeAnalysisCts, scope.Cancellation)
                || scope.Cancellation.IsCancellationRequested
                || !_projectService.IsCurrent(scope.Project))
            {
                return false;
            }

            _activeAnalysisClipId = clipId;
            return true;
        }
    }

    private VideoClipModel? ResolveAnalysisTarget(
        AnalysisScope scope,
        AnalysisTarget target)
    {
        if (!IsAnalysisScopeCurrent(scope))
            return null;

        return VideoClips.FirstOrDefault(clip =>
            clip.Id == target.Id
            && string.Equals(clip.Path, target.Path, StringComparison.OrdinalIgnoreCase));
    }

    private static AnalysisTarget CaptureAnalysisTarget(VideoClipModel clip)
        => new(clip.Id, clip.Name, clip.Path);

    private bool ApplyAnalysisResult(
        AnalysisScope scope,
        AnalysisTarget target,
        VideoAnalysisResult result,
        out VideoClipModel? clip)
    {
        clip = null;
        if (result.ClipId != target.Id)
            return false;

        clip = ResolveAnalysisTarget(scope, target);
        if (clip == null)
            return false;

        clip.IsAnalyzed = IsCompleted(result);
        ApplyMotionResult(clip, result);
        return true;
    }

    private void CancelActiveAnalysis()
    {
        CancellationTokenSource? active;
        lock (_analysisCancellationLock)
        {
            Interlocked.Increment(ref _analysisSequence);
            active = _activeAnalysisCts;
            _activeAnalysisCts = null;
            _activeAnalysisProjectContext = null;
            _activeAnalysisClipId = null;
        }

        if (active != null)
        {
            try { active.Cancel(); } catch (ObjectDisposedException) { }
        }
    }

    [RelayCommand]
    private async Task AnalyzeMarkedAsync()
    {
        var markedClips = VideoClips
            .Where(c => c.IsMarked)
            .Select(CaptureAnalysisTarget)
            .ToList();
        if (markedClips.Count == 0 || IsAnalyzing) return;
        await ExecuteAnalysisAsync(isBatch: true, async scope =>
        {
            var total = markedClips.Count;
            var done = 0;
            var succeeded = 0;
            var failed = 0;
            var skipped = 0;
            var failures = new List<string>();
            foreach (var target in markedClips)
            {
                scope.Cancellation.Token.ThrowIfCancellationRequested();
                var currentClip = ResolveAnalysisTarget(scope, target);
                if (currentClip == null)
                    return;
                if (currentClip.IsAnalyzed) { skipped++; done++; continue; }
                if (!SetActiveAnalysisClip(scope, target.Id))
                    return;
                StatusText = $"Markierte: Analysiere {done + 1}/{total}: {target.Name}...";
                AnalyzeAllProgress = (double)done / total * 100.0;
                try
                {
                    var result = await _api.AnalyzeVideoAsync(
                        target.Id,
                        StepDetectScenes,
                        StepAnalyzeMotion,
                        StepGenerateEmbeddings,
                        StepGenerateCaptions
                    );
                    scope.Cancellation.Token.ThrowIfCancellationRequested();
                    if (!IsAnalysisScopeCurrent(scope))
                        return;
                    if (result == null)
                    {
                        failed++;
                        failures.Add($"{target.Name}: leere Backend-Antwort");
                    }
                    else if (!ApplyAnalysisResult(scope, target, result, out var appliedClip))
                    {
                        failed++;
                        failures.Add($"{target.Name}: Antwort passt nicht zu Zielclip/Projekt");
                    }
                    else if (!IsCompleted(result))
                    {
                        failed++;
                        failures.Add($"{target.Name}: {AnalysisFailure(result)}");
                    }
                    else
                    {
                        succeeded++;
                        if (SelectedClip?.Id == target.Id
                            && ReferenceEquals(SelectedClip, appliedClip))
                        {
                            try
                            {
                                await LoadScenesAsync(target.Id);
                            }
                            catch (Exception ex)
                            {
                                failures.Add($"{target.Name}: Szenenansicht {ex.Message}");
                            }
                        }
                    }
                }
                catch (OperationCanceledException) when (scope.Cancellation.IsCancellationRequested)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    failed++;
                    failures.Add($"{target.Name}: {ex.Message}");
                }
                done++;
            }
            if (!IsAnalysisScopeCurrent(scope))
                return;
            WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
            WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            AnalyzeAllProgress = 100.0;
            StatusText = $"Markierte fertig: {succeeded} erfolgreich, {failed} fehlgeschlagen, {skipped} übersprungen."
                + (failures.Count > 0 ? $" Fehler: {string.Join(" | ", failures.Take(3))}" : "");
            UpdateAnalyzedCounts();
        });
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
                // Review-Fix MEDIUM (2026-07-09): Selektion + Markierungen
                // ueberleben den Self-Refresh nach Analyse (L-M6-Erhalt).
                var previousSelectedId = SelectedClip?.Id;
                var previousMarked = VideoClips.Where(c => c.IsMarked).Select(c => c.Id).ToHashSet();

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
                        AvgMotion = c.AvgMotion,
                        PeakMotion = c.PeakMotion,
                        MotionCategory = c.MotionCategory,
                        VideoHash = c.VideoHash,
                        TagSource = c.TagSource,
                        HasEmbedding = c.HasEmbedding || c.HasVideoEmbedding,
                        EmbeddingDim = c.EmbeddingDim,
                        EmbeddingSamples = c.EmbeddingSamples,
                        IsMarked = previousMarked.Contains(c.Id),
                    };

                    clip.PropertyChanged += (s, e) =>
                    {
                        if (e.PropertyName == nameof(VideoClipModel.IsMarked))
                        {
                            DeleteSelectedCommand.NotifyCanExecuteChanged();
                            AnalyzeMarkedCommand.NotifyCanExecuteChanged();
                        }
                    };

                    if (_thumbnailCache.TryGetValue(c.Id, out var cachedThumb))
                        clip.Thumbnail = cachedThumb;
                    else if (_thumbnailFailureCache.Contains(c.Id))
                        clip.Thumbnail = null;

                    VideoClips.Add(clip);
                }

                if (previousSelectedId != null)
                {
                    SelectedClip = VideoClips.FirstOrDefault(c => c.Id == previousSelectedId);
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
        var target = CaptureAnalysisTarget(SelectedClip);

        await ExecuteAnalysisAsync(isBatch: false, async scope =>
        {
            if (!SetActiveAnalysisClip(scope, target.Id))
                return;
            StatusText = $"Analysiere: {target.Name}...";
            try
            {
                var result = await _api.AnalyzeVideoAsync(
                target.Id,
                StepDetectScenes,
                StepAnalyzeMotion,
                StepGenerateEmbeddings,
                StepGenerateCaptions
                );
                scope.Cancellation.Token.ThrowIfCancellationRequested();
                if (!IsAnalysisScopeCurrent(scope))
                    return;

                if (result != null
                    && ApplyAnalysisResult(scope, target, result, out var appliedClip)
                    && IsCompleted(result))
                {
                    StatusText = $"Analyse fertig: {result.SceneCount} Scenes | Motion: {result.AvgMotion:F1}";
                    WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
                    WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());

                    // L-M6: Auto-Reload scenes nach Analyse - OnSelectedClipChanged triggert
                    // nur bei Selection-Wechsel, nicht bei IsAnalyzed-Update der aktuellen Selection.
                    if (SelectedClip?.Id == target.Id
                        && ReferenceEquals(SelectedClip, appliedClip))
                    {
                        await LoadScenesAsync(target.Id);
                    }
                }
                else if (result != null)
                {
                    if (result.ClipId != target.Id)
                        StatusText = "Analyse verworfen: Antwort passt nicht zu Zielclip/Projekt.";
                    else
                        StatusText = $"Analyse partiell/fehlgeschlagen: {AnalysisFailure(result)}";
                }
                else
                {
                    StatusText = "Analyse fehlgeschlagen";
                }
            }
            catch (OperationCanceledException) when (scope.Cancellation.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception ex)
            {
                if (IsAnalysisScopeCurrent(scope))
                    StatusText = $"Analyse fehlgeschlagen: {ex.Message}";
            }
        });
    }

    [RelayCommand]
    private async Task AnalyzeAllAsync()
    {
        if (VideoClips.Count == 0) return;
        var targets = VideoClips.Select(CaptureAnalysisTarget).ToList();
        await ExecuteAnalysisAsync(isBatch: true, async scope =>
        {
            var total = targets.Count;
            var done = 0;
            var succeeded = 0;
            var failed = 0;
            var skipped = 0;
            var failures = new List<string>();

            foreach (var target in targets)
            {
                scope.Cancellation.Token.ThrowIfCancellationRequested();
                var currentClip = ResolveAnalysisTarget(scope, target);
                if (currentClip == null)
                    return;
                if (currentClip.IsAnalyzed) { skipped++; done++; continue; }
                if (!SetActiveAnalysisClip(scope, target.Id))
                    return;

                StatusText = $"Analysiere {done + 1}/{total}: {target.Name}...";
                AnalyzeAllProgress = (double)done / total * 100;

                try
                {
                    var result = await _api.AnalyzeVideoAsync(
                        target.Id,
                        StepDetectScenes,
                        StepAnalyzeMotion,
                        StepGenerateEmbeddings,
                        StepGenerateCaptions
                    );
                    scope.Cancellation.Token.ThrowIfCancellationRequested();
                    if (!IsAnalysisScopeCurrent(scope))
                        return;
                    if (result == null)
                    {
                        failed++;
                        failures.Add($"{target.Name}: leere Backend-Antwort");
                    }
                    else if (!ApplyAnalysisResult(scope, target, result, out var appliedClip))
                    {
                        failed++;
                        failures.Add($"{target.Name}: Antwort passt nicht zu Zielclip/Projekt");
                    }
                    else if (!IsCompleted(result))
                    {
                        failed++;
                        failures.Add($"{target.Name}: {AnalysisFailure(result)}");
                    }
                    else
                    {
                        succeeded++;
                        if (SelectedClip?.Id == target.Id
                            && ReferenceEquals(SelectedClip, appliedClip))
                        {
                            try
                            {
                                await LoadScenesAsync(target.Id);
                            }
                            catch (Exception ex)
                            {
                                failures.Add($"{target.Name}: Szenenansicht {ex.Message}");
                            }
                        }
                    }
                }
                catch (OperationCanceledException) when (scope.Cancellation.IsCancellationRequested)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    failed++;
                    failures.Add($"{target.Name}: {ex.Message}");
                }
                done++;
            }

            if (!IsAnalysisScopeCurrent(scope))
                return;
            WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
            WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            AnalyzeAllProgress = 100;
            StatusText = $"Batch fertig: {succeeded} erfolgreich, {failed} fehlgeschlagen, {skipped} übersprungen."
                + (failures.Count > 0 ? $" Fehler: {string.Join(" | ", failures.Take(3))}" : "");
            UpdateAnalyzedCounts();
        });
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
        CancelActiveAnalysis();
        Interlocked.Increment(ref _loadVersion);
        Interlocked.Increment(ref _sceneLoadSequence);
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
        CancelActiveAnalysis();
        Interlocked.Increment(ref _loadVersion);
        Interlocked.Increment(ref _sceneLoadSequence);
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
