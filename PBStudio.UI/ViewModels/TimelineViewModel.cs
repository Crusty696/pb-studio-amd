using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Timeline-Vorschau.</summary>
public partial class TimelineViewModel : ObservableObject, IDisposable
{
    private static readonly SemaphoreSlim TimelinePersistenceGate = new(1, 1);
    private readonly TimelineStateService _timelineState;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly ProjectService _projectService;
    // AP3.5 (Audit 2026-06-10): IApiClient statt konkretem ApiClient — die
    // Transient-Registrierung erzeugte hier eine ZWEITE ApiClient-Instanz mit
    // eigenem Shutdown-Token, die BeginShutdown() der Singleton-Instanz nie erreichte.
    private readonly IApiClient _api;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private readonly SemaphoreSlim _syncGate = new(1, 1);
    private int _loadVersion;
    private int _waveformSequence;
    private volatile bool _reloadQueued;
    private bool _disposed;
    private bool _isSyncingSelection;
    private readonly object _assetLoadLock = new();
    private readonly Dictionary<TimelineEntryModel, Task> _assetLoads = [];
    private CancellationTokenSource? _assetLoadCts = new();
    private readonly object _projectOperationLock = new();
    private CancellationTokenSource? _syncTimelineCts;
    private CancellationTokenSource? _previewCts;
    private int _syncTimelineSequence;
    private int _previewSequence;
    private bool _timelineReadyForMutation;
    private long _editVersion;
    private long _savedEditVersion;
    private double _viewportWidth = 1920.0;
    private readonly HashSet<TimelineEntryModel> _assetWindowEntries = [];
    private const double MinClipDuration = 0.1;
    private const double TimelineEditEpsilon = 0.0001;
    private const int MaxAssetClipCount = 24;

    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private string? _audioPath;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isLoadingWaveform;
    [ObservableProperty] private TimelineEntryModel? _selectedEntry;
    [ObservableProperty] private double _selectedTimelinePosition;
    [ObservableProperty] private double _pixelsPerSecond = 100.0;
    [ObservableProperty] private double _horizontalOffset = 0.0;
    [ObservableProperty] private bool _showWaveform = true;
    [ObservableProperty] private bool _showBeatgrid = true;

    // /pacing/preview — Backend rendert 640×360 Slice der aktuellen Timeline.
    [ObservableProperty] private double _previewStartSec = 0.0;
    [ObservableProperty] private double _previewDurationSec = 10.0;
    [ObservableProperty] private bool _isGeneratingPreview;
    [ObservableProperty] private string? _previewVideoPath;
    [ObservableProperty] private string _previewStatus = "";

    // Audit L-M5: Motion-Curve Sparkline-Overlay fuer den selektierten Timeline-Entry.
    // Wird per SelectedEntry-Wechsel asynchron von GET /video/motion/{id} geladen.
    [ObservableProperty] private ObservableCollection<double>? _motionCurve;
    private int _motionLoadSequence;

    public event Action<string>? PreviewReady;

    private SpectralDataModel? _rawSpectralData;
    public ObservableCollection<Point> SpectralPoints { get; } = [];

    public double TimelineWidth => TotalDuration * PixelsPerSecond;

    partial void OnPixelsPerSecondChanged(double value)
    {
        OnPropertyChanged(nameof(TimelineWidth));
        UpdateSpectralPoints();
        UpdateViewportEntries();
    }

    partial void OnHorizontalOffsetChanged(double value)
    {
        UpdateViewportEntries();
    }

    /// <summary>
    /// Spec 00009 T008 / STF-001: Dynamic Downsampling fuer SpectralPoints.
    /// Wenn rawCount &gt; Threshold: Stride-basierte Mittelwert-Aggregation, sonst 1:1-Copy.
    /// Performance-Ziel (AD-004): &lt;16ms downsample-time bei 1000 raw points.
    /// Siehe specs/00009-data-depth-visualization/spec.md AD-004.
    /// </summary>
    private void UpdateSpectralPoints()
    {
        if (_rawSpectralData == null || _rawSpectralData.Centroids == null || _rawSpectralData.Centroids.Count == 0)
        {
            SpectralPoints.Clear();
            return;
        }

        // Dynamisches Downsampling basierend auf PixelsPerSecond (PPS)
        // Ziel: ca. 1 Punkt pro 2 Pixel
        double targetDensity = 0.5; // Punkte pro Pixel
        int targetPoints = (int)(TimelineWidth * targetDensity);
        int rawCount = _rawSpectralData.Centroids.Count;

        if (targetPoints >= rawCount)
        {
            // Alle Punkte anzeigen
            Application.Current.Dispatcher.Invoke(() =>
            {
                SpectralPoints.Clear();
                for (int i = 0; i < rawCount; i++)
                {
                    SpectralPoints.Add(new Point(_rawSpectralData.Times[i], _rawSpectralData.Centroids[i]));
                }
            });
        }
        else
        {
            // Downsampling via Mittelwert
            int step = rawCount / Math.Max(1, targetPoints);
            Application.Current.Dispatcher.Invoke(() =>
            {
                SpectralPoints.Clear();
                for (int i = 0; i < rawCount; i += step)
                {
                    double sumCentroid = 0;
                    int count = 0;
                    for (int j = 0; j < step && (i + j) < rawCount; j++)
                    {
                        sumCentroid += _rawSpectralData.Centroids[i + j];
                        count++;
                    }
                    SpectralPoints.Add(new Point(_rawSpectralData.Times[i], sumCentroid / count));
                }
            });
        }
    }

    public ObservableCollection<TimelineEntryModel> TimelineEntries { get; } = [];
    public ObservableCollection<TimelineEntryModel> VisibleTimelineEntries { get; } = [];
    public ObservableCollection<WaveformBarModel> WaveformBars { get; } = [];
    public ObservableCollection<double> BeatMarkers { get; } = [];
    public ObservableCollection<BeatMarkerViewModel> UIBeatMarkers { get; } = [];
    public ObservableCollection<double> SnapMarkers { get; } = [];
    public ObservableCollection<SongSegmentModel> SongSegments { get; } = [];

    public TimelineViewModel(
        TimelineStateService timelineState,
        AudioLibraryStateService audioLibraryState,
        IApiClient api,
        ProjectService projectService)
    {
        _timelineState = timelineState;
        _audioLibraryState = audioLibraryState;
        _api = api;
        _projectService = projectService;
        _projectService.ProjectTransitionStarted += OnProjectTransitionStarted;

        WeakReferenceMessenger.Default.Register<TimelineRefreshMessage>(this, (_, _) => _ = RequestTimelineRefreshAsync());
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => _ = RequestTimelineRefreshAsync());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
        {
            _timelineState.Clear();
            ResetTimelineState();
        });

        // R-Brain-09: Confidence-Balken + Tooltip live aktualisieren, wenn ein
        // 4-Klick-Feedback irgendwo (BrainViewModel oder LearningSessionViewModel)
        // gesendet wurde. Greift gezielt nur den betroffenen Cut.
        WeakReferenceMessenger.Default.Register<BrainFeedbackAppliedMessage>(this, (_, message) =>
        {
            _ = OnBrainFeedbackAppliedAsync(message.CutId);
        });
    }

    public bool HasTimeline => TimelineEntries.Count > 0;
    public string SelectedClipName => SelectedEntry?.ClipName ?? "Kein Clip ausgewählt";
    public string SelectedTrigger => SelectedEntry == null ? "–" : $"{SelectedEntry.TriggerType} ({SelectedEntry.TriggerStrength:F2})";
    public string SelectedClipStart => SelectedEntry == null ? "–" : $"{SelectedEntry.ClipStart:F2}s";
    public string SelectedTimeRange => SelectedEntry?.TimeRangeText ?? "–";
    public string SelectedFilePath => SelectedEntry?.FilePath ?? "–";
    public string SelectedEvidence => SelectedEntry == null
        ? "–"
        : $"Feature confidence: {SelectedEntry.FeatureConfidence:P0} | " +
          $"Semantic: {SelectedEntry.SemanticStatus}" +
          (string.IsNullOrWhiteSpace(SelectedEntry.SemanticReason)
              ? string.Empty
              : $" ({SelectedEntry.SemanticReason})");
    public bool CanPreviewSelectedClip =>
        SelectedEntry != null
        && LocalMediaPathPolicy.TryCreateFileUri(SelectedEntry.FilePath, out _);
    public string SelectedPreviewRange => SelectedEntry == null
        ? "–"
        : $"Clip {TimeSpan.FromSeconds(SelectedEntry.ClipStart):mm\\:ss} - {TimeSpan.FromSeconds(SelectedEntry.ClipStart + SelectedEntry.Duration):mm\\:ss}";
    public string SelectedTimelinePositionText => !HasTimeline
        ? "–"
        : $"{TimeSpan.FromSeconds(SelectedTimelinePosition):mm\\:ss} / {TimeSpan.FromSeconds(TotalDuration):mm\\:ss}";

    public string SelectionIndexText
    {
        get
        {
            if (SelectedEntry == null)
                return "Kein Cut selektiert";

            var index = TimelineEntries.IndexOf(SelectedEntry);
            return index < 0 ? "Kein Cut selektiert" : $"Cut {index + 1} / {TimelineEntries.Count}";
        }
    }

    partial void OnSelectedEntryChanged(TimelineEntryModel? value)
    {
        if (!_isSyncingSelection)
        {
            _isSyncingSelection = true;
            SelectedTimelinePosition = value?.StartTime ?? 0;
            _isSyncingSelection = false;
        }
        _timelineState.RememberSelection(value?.ClipId, value?.StartTime ?? 0);

        OnPropertyChanged(nameof(SelectedClipName));
        OnPropertyChanged(nameof(SelectedTrigger));
        OnPropertyChanged(nameof(SelectedClipStart));
        OnPropertyChanged(nameof(SelectedTimeRange));
        OnPropertyChanged(nameof(SelectedFilePath));
        OnPropertyChanged(nameof(SelectedEvidence));
        OnPropertyChanged(nameof(CanPreviewSelectedClip));
        OnPropertyChanged(nameof(SelectedPreviewRange));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();

        // Audit L-M5: Motion-Curve fuer selektierten Entry (fire-and-forget).
        // ClipId ist string (z.B. "42") -> int.TryParse; bei Fehler -> Curve clearen.
        if (value != null && int.TryParse(value.ClipId, NumberStyles.Integer, CultureInfo.InvariantCulture, out var cid))
        {
            _ = LoadMotionCurveAsync(cid);
        }
        else
        {
            Interlocked.Increment(ref _motionLoadSequence);
            MotionCurve = null;
        }

        UpdateViewportEntries();
    }

    /// <summary>
    /// Audit L-M5: Laedt motion_curve via GET /video/motion/{id} und mappt sie auf
    /// die UI-ObservableCollection. Sequence-Token verhindert Race wenn der User
    /// rasch durch Cuts klickt. Bei nicht-analysiertem Clip oder leerer Curve -> null.
    /// </summary>
    private async Task LoadMotionCurveAsync(int clipId)
    {
        var seq = Interlocked.Increment(ref _motionLoadSequence);
        try
        {
            var data = await _api.GetMotionAsync(clipId).ConfigureAwait(false);
            if (seq != _motionLoadSequence) return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (seq != _motionLoadSequence) return;
                if (data?.MotionCurve != null && data.MotionCurve.Count > 0)
                {
                    MotionCurve = new ObservableCollection<double>(data.MotionCurve.Select(f => (double)f));
                }
                else
                {
                    MotionCurve = null;
                }
            });
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"MotionCurve-Load fehlgeschlagen fuer clip {clipId}: {ex.Message}");
            if (seq == _motionLoadSequence)
            {
                await Application.Current.Dispatcher.InvokeAsync(() => MotionCurve = null);
            }
        }
    }

    /// <summary>
    /// Loads /video/thumbstrip and /video/clipwave for the entry's clip in parallel.
    /// Skips if already loaded. Fire-and-forget pattern: errors are logged and the
    /// entry's visual just falls back to the background rectangle.
    /// </summary>
    private Task QueueClipAssetLoad(TimelineEntryModel entry)
    {
        lock (_assetLoadLock)
        {
            if (_disposed || entry.IsAssetsLoaded || _assetLoadCts == null)
                return Task.CompletedTask;
            if (_assetLoads.TryGetValue(entry, out var existing))
                return existing;

            var load = LoadClipAssetsAsync(entry, _assetLoadCts.Token);
            _assetLoads[entry] = load;
            return load;
        }
    }

    private async Task LoadClipAssetsAsync(TimelineEntryModel entry, CancellationToken ct)
    {
        if (entry == null || entry.IsAssetsLoaded) return;
        if (!int.TryParse(entry.ClipId.Replace("clip_", ""),
                          NumberStyles.Integer, CultureInfo.InvariantCulture, out var cid))
        {
            entry.IsAssetsLoaded = true;
            return;
        }

        try
        {
            var stripTask = _api.GetThumbStripAsync(cid, n: 8, cancellationToken: ct);
            var waveTask = _api.GetClipWaveAsync(cid, n: 256, cancellationToken: ct);
            await Task.WhenAll(stripTask, waveTask).ConfigureAwait(false);
            ct.ThrowIfCancellationRequested();

            var decodedFrames = new List<System.Windows.Media.ImageSource>();
            if (stripTask.Result?.Frames is { Count: > 0 } frames)
            {
                foreach (var f in frames)
                {
                    ct.ThrowIfCancellationRequested();
                    try
                    {
                        var b64 = f.Replace("data:image/jpeg;base64,", "");
                        byte[] bytes = Convert.FromBase64String(b64);
                        using var ms = new System.IO.MemoryStream(bytes);
                        var bmp = new System.Windows.Media.Imaging.BitmapImage();
                        bmp.BeginInit();
                        bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad;
                        bmp.StreamSource = ms;
                        bmp.EndInit();
                        bmp.Freeze();
                        decodedFrames.Add(bmp);
                    }
                    catch (FormatException)
                    {
                        // Einzelnes beschädigtes Frame überspringen.
                    }
                }
            }
            var decodedPeaks = waveTask.Result?.Peaks is { Count: > 0 } peaks
                ? new ObservableCollection<float>(peaks.Select(p => (float)p))
                : null;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (ct.IsCancellationRequested)
                    return;
                if (decodedFrames.Count > 0)
                    entry.ThumbnailFrames = new ObservableCollection<System.Windows.Media.ImageSource>(decodedFrames);
                if (decodedPeaks != null)
                    entry.AudioPeaks = decodedPeaks;
                entry.IsAssetsLoaded = true;
            });
        }
        catch (OperationCanceledException)
        {
            // Projektwechsel/Dispose: alter Load darf neuen Timeline-State nicht berühren.
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Clip-Assets-Load fehlgeschlagen fuer clip {cid}: {ex.Message}");
            if (!ct.IsCancellationRequested)
                entry.IsAssetsLoaded = true;  // mark so we don't retry every render
        }
    }

    partial void OnSelectedTimelinePositionChanged(double value)
    {
        OnPropertyChanged(nameof(SelectedTimelinePositionText));

        if (_isSyncingSelection || TimelineEntries.Count == 0)
            return;

        var nearestEntry = TimelineEntries
            .OrderBy(entry => value >= entry.StartTime && value <= entry.EndTime ? 0 : 1)
            .ThenBy(entry => Math.Abs(entry.StartTime - value))
            .FirstOrDefault();

        if (nearestEntry == null || ReferenceEquals(nearestEntry, SelectedEntry))
            return;

        _isSyncingSelection = true;
        SelectedEntry = nearestEntry;
        _isSyncingSelection = false;
    }

    public void MarkTimelineDirty()
    {
        if (_timelineReadyForMutation)
            Interlocked.Increment(ref _editVersion);
    }

    public void UpdateViewport(double horizontalOffset, double viewportWidth)
    {
        _viewportWidth = Math.Max(1.0, viewportWidth);
        HorizontalOffset = Math.Max(0.0, horizontalOffset);
        UpdateViewportEntries();
    }

    private void UpdateViewportEntries()
    {
        if (_disposed)
            return;

        var pixelsPerSecond = Math.Max(1.0, PixelsPerSecond);
        var visibleStart = Math.Max(0.0, HorizontalOffset / pixelsPerSecond);
        var visibleDuration = Math.Max(1.0, _viewportWidth / pixelsPerSecond);
        var visibleEnd = visibleStart + visibleDuration;
        var overscan = Math.Max(2.0, visibleDuration * 0.5);
        var viewportCenter = visibleStart + (visibleDuration / 2.0);

        var desiredVisible = EntriesInRange(
            visibleStart - overscan,
            visibleEnd + overscan);

        if (SelectedEntry != null && !desiredVisible.Contains(SelectedEntry))
            desiredVisible.Add(SelectedEntry);

        if (VisibleTimelineEntries.Count != desiredVisible.Count
            || !VisibleTimelineEntries.SequenceEqual(desiredVisible))
        {
            VisibleTimelineEntries.Clear();
            foreach (var entry in desiredVisible)
                VisibleTimelineEntries.Add(entry);
        }

        var desiredAssets = desiredVisible
            .Where(entry => entry.EndTime >= visibleStart
                && entry.StartTime <= visibleEnd)
            .OrderBy(entry => Math.Abs(
                ((entry.StartTime + entry.EndTime) / 2.0) - viewportCenter))
            .Take(MaxAssetClipCount)
            .ToHashSet();

        if (_assetWindowEntries.SetEquals(desiredAssets))
            return;

        ResetAssetLoads();
        foreach (var entry in _assetWindowEntries)
        {
            if (desiredAssets.Contains(entry))
                continue;
            entry.ThumbnailFrames = null;
            entry.AudioPeaks = null;
            entry.IsAssetsLoaded = false;
        }

        _assetWindowEntries.Clear();
        foreach (var entry in desiredAssets)
        {
            _assetWindowEntries.Add(entry);
            if (!entry.IsAssetsLoaded)
                _ = QueueClipAssetLoad(entry);
        }
    }

    private List<TimelineEntryModel> EntriesInRange(double startTime, double endTime)
    {
        var low = 0;
        var high = TimelineEntries.Count;
        while (low < high)
        {
            var middle = low + ((high - low) / 2);
            if (TimelineEntries[middle].EndTime < startTime)
                low = middle + 1;
            else
                high = middle;
        }

        var entries = new List<TimelineEntryModel>();
        for (var index = low; index < TimelineEntries.Count; index++)
        {
            var entry = TimelineEntries[index];
            if (entry.StartTime > endTime)
                break;
            if (entry.EndTime >= startTime)
                entries.Add(entry);
        }
        return entries;
    }

    private bool CanSelectPreviousCut() =>
        SelectedEntry != null && TimelineEntries.IndexOf(SelectedEntry) > 0;

    private bool CanSelectNextCut() =>
        SelectedEntry != null && TimelineEntries.IndexOf(SelectedEntry) >= 0 && TimelineEntries.IndexOf(SelectedEntry) < TimelineEntries.Count - 1;

    [RelayCommand(CanExecute = nameof(CanSelectPreviousCut))]
    private void PreviousCut()
    {
        if (SelectedEntry == null)
            return;

        var index = TimelineEntries.IndexOf(SelectedEntry);
        if (index > 0)
            SelectedEntry = TimelineEntries[index - 1];
    }

    [RelayCommand(CanExecute = nameof(CanSelectNextCut))]
    private void NextCut()
    {
        if (SelectedEntry == null)
            return;

        var index = TimelineEntries.IndexOf(SelectedEntry);
        if (index >= 0 && index < TimelineEntries.Count - 1)
            SelectedEntry = TimelineEntries[index + 1];
    }

    public bool SelectFirstCut()
    {
        if (TimelineEntries.Count == 0)
            return false;

        SelectedEntry = TimelineEntries
            .OrderBy(entry => entry.StartTime)
            .First();
        return true;
    }

    public bool SelectLastCut()
    {
        if (TimelineEntries.Count == 0)
            return false;

        SelectedEntry = TimelineEntries
            .OrderBy(entry => entry.StartTime)
            .Last();
        return true;
    }

    public bool ScrubTimelineBy(double deltaSeconds)
    {
        if (TimelineEntries.Count == 0 || TotalDuration <= 0)
            return false;

        var nextPosition = ClampRoundedTimelineTime(
            SelectedTimelinePosition + deltaSeconds,
            0,
            TotalDuration);
        if (Math.Abs(nextPosition - SelectedTimelinePosition) < TimelineEditEpsilon)
            return false;

        SelectedTimelinePosition = nextPosition;
        StatusText = $"Abspielposition: {TimeSpan.FromSeconds(nextPosition):mm\\:ss\\.f}";
        return true;
    }

    public bool NudgeSelectedCutBy(double deltaSeconds)
    {
        if (SelectedEntry == null)
            return false;

        var entry = SelectedEntry;
        var duration = entry.Duration;
        var previous = FindPreviousEntry(entry);
        var next = FindNextEntry(entry);
        var minimumStart = previous?.EndTime ?? 0;
        var maximumStart = next?.StartTime - duration
            ?? (TotalDuration > 0 ? TotalDuration - duration : double.PositiveInfinity);
        maximumStart = Math.Max(minimumStart, maximumStart);

        var newStart = ClampRoundedTimelineTime(
            entry.StartTime + deltaSeconds,
            minimumStart,
            maximumStart);
        if (Math.Abs(newStart - entry.StartTime) < TimelineEditEpsilon)
        {
            StatusText = "Cut kann wegen angrenzender Clips nicht weiter verschoben werden.";
            return false;
        }

        entry.StartTime = newStart;
        var maximumEnd = next?.StartTime
            ?? (TotalDuration > 0 ? TotalDuration : double.PositiveInfinity);
        entry.EndTime = Math.Min(maximumEnd, newStart + duration);
        entry.NotifyPositionChanged();
        SetSelectionPositionWithoutChangingEntry(newStart);
        StatusText = $"Cut verschoben: {newStart:F1}s";
        return true;
    }

    public bool TrimSelectedCutStartBy(double deltaSeconds)
    {
        if (SelectedEntry == null)
            return false;

        var entry = SelectedEntry;
        var previous = FindPreviousEntry(entry);
        var minimumStart = Math.Max(
            previous?.EndTime ?? 0,
            entry.StartTime - entry.ClipStart);
        var maximumStart = entry.EndTime - MinClipDuration;
        maximumStart = Math.Max(minimumStart, maximumStart);
        var newStart = ClampRoundedTimelineTime(
            entry.StartTime + deltaSeconds,
            minimumStart,
            maximumStart);
        if (Math.Abs(newStart - entry.StartTime) < TimelineEditEpsilon)
        {
            StatusText = "Linke Schnittkante hat ihre sichere Grenze erreicht.";
            return false;
        }

        var actualDelta = newStart - entry.StartTime;
        entry.StartTime = newStart;
        entry.ClipStart = Math.Max(
            0,
            RoundTimelineTime(entry.ClipStart + actualDelta));
        entry.NotifyPositionChanged();
        SetSelectionPositionWithoutChangingEntry(newStart);
        StatusText = $"Linke Schnittkante: {newStart:F1}s";
        return true;
    }

    public bool TrimSelectedCutEndBy(double deltaSeconds)
    {
        if (SelectedEntry == null)
            return false;

        var entry = SelectedEntry;
        var next = FindNextEntry(entry);
        var minimumEnd = entry.StartTime + MinClipDuration;
        var maximumEnd = next?.StartTime
            ?? (TotalDuration > 0 ? TotalDuration : double.PositiveInfinity);
        maximumEnd = Math.Max(minimumEnd, maximumEnd);
        var newEnd = ClampRoundedTimelineTime(
            entry.EndTime + deltaSeconds,
            minimumEnd,
            maximumEnd);
        if (Math.Abs(newEnd - entry.EndTime) < TimelineEditEpsilon)
        {
            StatusText = "Rechte Schnittkante hat ihre sichere Grenze erreicht.";
            return false;
        }

        entry.EndTime = newEnd;
        entry.NotifyPositionChanged();
        StatusText = $"Rechte Schnittkante: {newEnd:F1}s";
        return true;
    }

    public void RejectUnsafeTimelineRemoval()
    {
        StatusText = SelectedEntry == null
            ? "Kein Cut zum Entfernen ausgewählt."
            : "Cut nicht entfernt: bestätigter Timeline-Löschvertrag fehlt.";
    }

    private TimelineEntryModel? FindPreviousEntry(TimelineEntryModel entry) =>
        TimelineEntries
            .Where(other => !ReferenceEquals(other, entry)
                && other.EndTime <= entry.StartTime + TimelineEditEpsilon)
            .OrderByDescending(other => other.EndTime)
            .FirstOrDefault();

    private TimelineEntryModel? FindNextEntry(TimelineEntryModel entry) =>
        TimelineEntries
            .Where(other => !ReferenceEquals(other, entry)
                && other.StartTime >= entry.EndTime - TimelineEditEpsilon)
            .OrderBy(other => other.StartTime)
            .FirstOrDefault();

    private void SetSelectionPositionWithoutChangingEntry(double value)
    {
        _isSyncingSelection = true;
        SelectedTimelinePosition = value;
        _isSyncingSelection = false;
    }

    private static double RoundTimelineTime(double value) =>
        Math.Round(value, 3, MidpointRounding.AwayFromZero);

    private static double ClampRoundedTimelineTime(
        double value,
        double minimum,
        double maximum)
    {
        var rounded = RoundTimelineTime(Math.Clamp(value, minimum, maximum));
        return Math.Clamp(rounded, minimum, maximum);
    }

    public Task ActivateAsync() => RefreshTimelineAsync();

    [RelayCommand]
    private async Task RefreshTimelineAsync()
    {
        if (Interlocked.Read(ref _editVersion) != Interlocked.Read(ref _savedEditVersion))
        {
            await SyncTimelineAsync();
            return;
        }

        _reloadQueued = false;
        _timelineReadyForMutation = false;
        var version = Interlocked.Increment(ref _loadVersion);

        if (!await _loadGate.WaitAsync(0))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            ProjectOperationContext operation;
            try
            {
                operation = _projectService.CaptureOperationContext();
            }
            catch (InvalidOperationException)
            {
                if (version == Volatile.Read(ref _loadVersion))
                    StatusText = "Timeline laden ausgesetzt — kein stabiler Projektkontext.";
                return;
            }

            ResetAssetLoads();
            _assetWindowEntries.Clear();
            IsLoading = true;
            StatusText = "Timeline wird geladen...";

            TimelineResponse? timeline;
            await TimelinePersistenceGate.WaitAsync(operation.CancellationToken);
            try
            {
                timeline = await _timelineState.RefreshAsync();
            }
            finally
            {
                TimelinePersistenceGate.Release();
            }
            if (timeline == null)
            {
                if (version == Volatile.Read(ref _loadVersion)
                    && _projectService.IsCurrent(operation))
                    StatusText = "Timeline laden fehlgeschlagen";
                return;
            }

            if (version != Volatile.Read(ref _loadVersion)
                || !_projectService.IsCurrent(operation))
                return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (version != Volatile.Read(ref _loadVersion)
                    || !_projectService.IsCurrent(operation))
                    return;

                var rememberedSelection = _timelineState.GetRememberedSelection();
                TimelineEntries.Clear();
                foreach (var entry in timeline.Entries)
                {
                    TimelineEntries.Add(new TimelineEntryModel
                    {
                        ClipId = entry.ClipId,
                        ClipName = entry.ClipName,
                        FilePath = entry.FilePath,
                        StartTime = entry.StartTime,
                        EndTime = entry.EndTime,
                        ClipStart = entry.ClipStart,
                        TriggerType = entry.TriggerType,
                        TriggerStrength = entry.TriggerStrength,
                        SegmentType = entry.SegmentType,
                        BrainConfidence = entry.BrainConfidence,
                        CutId = entry.CutId ?? 0,
                        FeatureConfidence = entry.FeatureConfidence,
                        SemanticStatus = entry.SemanticStatus,
                        SemanticReason = entry.SemanticReason,
                        TriggerProvenance = entry.TriggerProvenance,
                        BrainAxisStatus = entry.BrainAxisStatus,
                        Metadata = entry.Metadata,
                    });
                }

                TotalDuration = timeline.TotalDuration;
                AudioPath = timeline.AudioPath;
                SelectedEntry = TimelineEntries
                    .Where(entry => entry.ClipId == rememberedSelection.ClipId)
                    .OrderBy(entry => Math.Abs(
                        entry.StartTime - rememberedSelection.StartTime))
                    .FirstOrDefault()
                    ?? TimelineEntries.FirstOrDefault();
                SelectedTimelinePosition = SelectedEntry?.StartTime ?? 0;

                StatusText = TimelineEntries.Count == 0
                    ? "Timeline ist leer"
                    : $"Timeline: {TimelineEntries.Count} Clips, {TotalDuration:F1}s";
                OnPropertyChanged(nameof(HasTimeline));
                OnPropertyChanged(nameof(SelectedTimelinePositionText));
                OnPropertyChanged(nameof(SelectionIndexText));
                OnPropertyChanged(nameof(TimelineWidth));
                PreviousCutCommand.NotifyCanExecuteChanged();
                NextCutCommand.NotifyCanExecuteChanged();
                _timelineReadyForMutation = true;
                var cleanVersion = Interlocked.Increment(ref _editVersion);
                Interlocked.Exchange(ref _savedEditVersion, cleanVersion);
                UpdateViewportEntries();

                if (!string.IsNullOrEmpty(AudioPath))
                {
                    _ = LoadWaveformAsync(AudioPath);
                }
            });
        }
        catch (OperationCanceledException)
        {
            // Projektwechsel/Dispose: ein neuer Projektkontext besitzt den UI-State.
        }
        finally
        {
            IsLoading = false;
            _loadGate.Release();
            if (_reloadQueued)
                await RefreshTimelineAsync();
        }
    }

    [RelayCommand]
    public async Task GeneratePreviewAsync()
    {
        if (IsGeneratingPreview) return;
        if (TimelineEntries.Count == 0)
        {
            PreviewStatus = "Keine Timeline — generiere zuerst eine Cut-Liste.";
            return;
        }

        ProjectOperationContext operation;
        try
        {
            operation = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            PreviewStatus = "Preview abgebrochen — Projektwechsel läuft.";
            return;
        }

        var startSec = PreviewStartSec;
        var durationSec = PreviewDurationSec;
        var (sequence, operationCts) = BeginPreviewOperation(operation);
        IsGeneratingPreview = true;
        PreviewStatus = $"Rendere Preview ({durationSec:F0}s ab {startSec:F1}s)…";
        try
        {
            var resp = await _api.GenerateTimelinePreviewAsync(
                startSec,
                durationSec,
                operationCts.Token);
            if (!IsCurrentPreview(sequence, operationCts, operation))
                return;
            if (resp == null || string.IsNullOrEmpty(resp.PreviewPath))
            {
                PreviewStatus = "Preview fehlgeschlagen — Backend lieferte keinen Pfad.";
                return;
            }

            if (!LocalMediaPathPolicy.TryCreateFileUri(resp.PreviewPath, out _))
            {
                PreviewStatus = "Preview-Pfad ist keine freigegebene lokale Datei.";
                return;
            }

            PreviewVideoPath = resp.PreviewPath;
            PreviewStatus = $"Preview bereit: {resp.Resolution} · {resp.Duration:F1}s";
            PreviewReady?.Invoke(resp.PreviewPath);
        }
        catch (OperationCanceledException)
        {
            // Projektwechsel oder neuere Preview besitzt den sichtbaren Zustand.
        }
        catch (Exception ex)
        {
            if (IsCurrentPreview(sequence, operationCts, operation))
                PreviewStatus = "Fehler: " + ex.Message;
        }
        finally
        {
            if (CompletePreviewOperation(sequence, operationCts))
                IsGeneratingPreview = false;
        }
    }

    [RelayCommand]
    public async Task SyncTimelineAsync()
    {
        await _syncGate.WaitAsync();
        try
        {
        if (!_timelineReadyForMutation)
        {
            StatusText = "Speichern übersprungen — Timeline wird noch geladen.";
            return;
        }

        var editVersion = Interlocked.Read(ref _editVersion);
        if (editVersion == Interlocked.Read(ref _savedEditVersion))
            return;

        ProjectOperationContext operation;
        try
        {
            operation = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            StatusText = "Speichern abgebrochen — Projektwechsel läuft.";
            return;
        }

        var entries = SnapshotTimelineEntries();
        var refreshCanonicalTimeline = false;
        var (sequence, operationCts) = BeginSyncOperation(operation);
        try
        {
            StatusText = "Speichere Änderungen...";
            await TimelinePersistenceGate.WaitAsync(operationCts.Token);
            StatusResponse? response;
            try
            {
                response = await _api.UpdateTimelineAsync(entries, operationCts.Token);
            }
            finally
            {
                TimelinePersistenceGate.Release();
            }
            if (!IsCurrentSync(sequence, operationCts, operation))
                return;

            if (response?.Success == true)
            {
                Interlocked.Exchange(ref _savedEditVersion, editVersion);
                refreshCanonicalTimeline = editVersion == Interlocked.Read(ref _editVersion);
                StatusText = "Änderungen gespeichert";
            }
            else
            {
                StatusText = "Speichern fehlgeschlagen: " + (response?.Message ?? "Unbekannter Fehler");
            }
        }
        catch (OperationCanceledException)
        {
            // Projektwechsel oder neuerer Autosave besitzt den sichtbaren Zustand.
        }
        catch (Exception ex)
        {
            if (IsCurrentSync(sequence, operationCts, operation))
                StatusText = "Fehler beim Synchronisieren: " + ex.Message;
        }
        finally
        {
            CompleteSyncOperation(sequence, operationCts);
        }
        if (refreshCanonicalTimeline)
            await RefreshTimelineAsync();
        }
        finally
        {
            _syncGate.Release();
        }
    }

    private List<TimelineEntryModel> SnapshotTimelineEntries() =>
        TimelineEntries.Select(entry => new TimelineEntryModel
        {
            ClipId = entry.ClipId,
            ClipName = entry.ClipName,
            FilePath = entry.FilePath,
            StartTime = entry.StartTime,
            EndTime = entry.EndTime,
            ClipStart = entry.ClipStart,
            TriggerType = entry.TriggerType,
            TriggerStrength = entry.TriggerStrength,
            SegmentType = entry.SegmentType,
            BrainConfidence = entry.BrainConfidence,
            CutId = entry.CutId,
            FeatureConfidence = entry.FeatureConfidence,
            SemanticStatus = entry.SemanticStatus,
            SemanticReason = entry.SemanticReason,
            TriggerProvenance = entry.TriggerProvenance == null
                ? null
                : new Dictionary<string, System.Text.Json.JsonElement>(
                    entry.TriggerProvenance),
            BrainAxisStatus = entry.BrainAxisStatus == null
                ? null
                : new Dictionary<string, System.Text.Json.JsonElement>(
                    entry.BrainAxisStatus),
            Metadata = entry.Metadata == null
                ? null
                : new Dictionary<string, System.Text.Json.JsonElement>(
                    entry.Metadata),
        }).ToList();

    private (int Sequence, CancellationTokenSource Cts) BeginSyncOperation(
        ProjectOperationContext operation)
    {
        var current = CancellationTokenSource.CreateLinkedTokenSource(
            operation.CancellationToken);
        CancellationTokenSource? previous;
        int sequence;
        lock (_projectOperationLock)
        {
            previous = _syncTimelineCts;
            _syncTimelineCts = current;
            sequence = ++_syncTimelineSequence;
        }
        previous?.Cancel();
        return (sequence, current);
    }

    private (int Sequence, CancellationTokenSource Cts) BeginPreviewOperation(
        ProjectOperationContext operation)
    {
        var current = CancellationTokenSource.CreateLinkedTokenSource(
            operation.CancellationToken);
        CancellationTokenSource? previous;
        int sequence;
        lock (_projectOperationLock)
        {
            previous = _previewCts;
            _previewCts = current;
            sequence = ++_previewSequence;
        }
        previous?.Cancel();
        return (sequence, current);
    }

    private bool IsCurrentSync(
        int sequence,
        CancellationTokenSource owner,
        ProjectOperationContext operation)
    {
        lock (_projectOperationLock)
        {
            if (sequence != _syncTimelineSequence
                || !ReferenceEquals(_syncTimelineCts, owner)
                || owner.IsCancellationRequested)
            {
                return false;
            }
        }
        return _projectService.IsCurrent(operation);
    }

    private bool IsCurrentPreview(
        int sequence,
        CancellationTokenSource owner,
        ProjectOperationContext operation)
    {
        lock (_projectOperationLock)
        {
            if (sequence != _previewSequence
                || !ReferenceEquals(_previewCts, owner)
                || owner.IsCancellationRequested)
            {
                return false;
            }
        }
        return _projectService.IsCurrent(operation);
    }

    private void CompleteSyncOperation(
        int sequence,
        CancellationTokenSource owner)
    {
        lock (_projectOperationLock)
        {
            if (sequence == _syncTimelineSequence
                && ReferenceEquals(_syncTimelineCts, owner))
            {
                _syncTimelineCts = null;
            }
        }
        owner.Dispose();
    }

    private bool CompletePreviewOperation(
        int sequence,
        CancellationTokenSource owner)
    {
        bool owned;
        lock (_projectOperationLock)
        {
            owned = sequence == _previewSequence
                && ReferenceEquals(_previewCts, owner);
            if (owned)
                _previewCts = null;
        }
        owner.Dispose();
        return owned;
    }

    private void OnProjectTransitionStarted(object? sender, EventArgs e) =>
        CancelProjectOperations();

    private void CancelProjectOperations()
    {
        CancellationTokenSource? sync;
        CancellationTokenSource? preview;
        lock (_projectOperationLock)
        {
            sync = _syncTimelineCts;
            preview = _previewCts;
            _syncTimelineCts = null;
            _previewCts = null;
            _syncTimelineSequence++;
            _previewSequence++;
        }
        sync?.Cancel();
        preview?.Cancel();
        _timelineReadyForMutation = false;
        IsGeneratingPreview = false;
    }

    private async Task LoadWaveformAsync(string audioPath)
    {
        var seq = Interlocked.Increment(ref _waveformSequence);

        try
        {
            IsLoadingWaveform = true;

            // Suche Audio ID über State Service
            var clips = await _audioLibraryState.RefreshAsync();
            
            string normalizedAudioPath = System.IO.Path.GetFullPath(audioPath).ToLowerInvariant();
            var audioClip = clips?.FirstOrDefault(c => 
                System.IO.Path.GetFullPath(c.Path).ToLowerInvariant() == normalizedAudioPath);

            if (audioClip == null || seq != _waveformSequence) return;

            var waveform = await _api.GetWaveformAsync(audioClip.Id, bands: 1);
            var beats = await _api.GetBeatsAsync(audioClip.Id);
            var onsets = await _api.GetOnsetsAsync(audioClip.Id);
            var structure = await _api.GetAsync<List<SongSegmentModel>>($"/audio/structure/{audioClip.Id}");
            var transport = await _api.GetSpectralAsync(audioClip.Id);
            var spectral = transport is null
                ? null
                : SpectralDataModel.FromTransport(transport);

            if (waveform == null || seq != _waveformSequence) return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (seq != Volatile.Read(ref _waveformSequence))
                    return;

                WaveformBars.Clear();
                BeatMarkers.Clear();
                UIBeatMarkers.Clear();
                SnapMarkers.Clear();
                SongSegments.Clear();
                _rawSpectralData = spectral;

                if (structure != null)
                {
                    foreach (var seg in structure) SongSegments.Add(seg);
                }

                if (spectral != null)
                {
                    UpdateSpectralPoints();
                }

                if (beats != null)
                {
                    int beatIndex = 0;
                    foreach (var b in beats)
                    {
                        BeatMarkers.Add(b.Time);
                        SnapMarkers.Add(b.Time);
                        UIBeatMarkers.Add(new BeatMarkerViewModel
                        {
                            Time = b.Time,
                            Index = beatIndex++,
                            Strength = b.Strength,
                            BeatType = b.BeatType
                        });
                    }
                }

                if (onsets != null)
                {
                    foreach (var o in onsets)
                    {
                        if (!SnapMarkers.Contains(o))
                            SnapMarkers.Add(o);
                    }
                }

                var rawData = waveform.Bands?.FirstOrDefault();
                if (rawData == null || rawData.Count == 0) return;

                double duration = waveform.DurationSeconds;
                int count = rawData.Count;
                double secondsPerPoint = duration / count;

                int step = Math.Max(1, count / 1000);
                const double laneHeight = 80.0;
                const double mid = laneHeight / 2.0;

                for (int i = 0; i < count; i += step)
                {
                    double val = rawData[i];
                    double h = Math.Max(2, val * mid * 1.8);
                    WaveformBars.Add(new WaveformBarModel
                    {
                        X = (i * secondsPerPoint),
                        Height = h,
                        Y = mid - (h / 2.0),
                        Width = (secondsPerPoint * step)
                    });
                }
            });
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Fehler beim Laden der Timeline-Waveform: {ex.Message}");
        }
        finally
        {
            if (seq == Volatile.Read(ref _waveformSequence))
                IsLoadingWaveform = false;
        }
    }

    private async Task RequestTimelineRefreshAsync()
    {
        _reloadQueued = true;
        await RefreshTimelineAsync();
    }

    // ---------- R-Brain-09: Brain-Explain Tooltip + Live-Refresh ----------

    /// <summary>
    /// Lazy-Load des /brain/explain/{cut_id} Inhalts fuer den Confidence-Tooltip.
    /// Wird von der View beim ToolTipOpening aufgerufen. Cached pro Eintrag.
    /// </summary>
    public async Task LoadBrainExplainAsync(TimelineEntryModel entry, CancellationToken ct = default)
    {
        if (entry == null) return;
        if (entry.IsBrainExplainLoaded || entry.IsBrainExplainLoading) return;

        if (entry.CutId <= 0)
        {
            // Cut ist nicht in der DB persistiert (z.B. Pacing ohne use_brain).
            entry.BrainExplainTooltip = "Erklärung nicht verfügbar (kein cut_id).";
            entry.IsBrainExplainLoaded = true;
            return;
        }

        entry.IsBrainExplainLoading = true;
        entry.BrainExplainTooltip = "Lade Erklärung…";

        try
        {
            var explain = await _api.BrainExplainAsync(entry.CutId, topN: 3, ct: ct).ConfigureAwait(false);
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                entry.BrainExplainTooltip = explain == null
                    ? "Erklärung nicht verfügbar."
                    : FormatExplainTooltip(explain);
                entry.IsBrainExplainLoaded = true;
            });
        }
        catch (OperationCanceledException)
        {
            // Schluck — User hat den Hover beendet, oder App schliesst.
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"BrainExplain fuer Cut {entry.CutId} fehlgeschlagen: {ex.Message}");
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                entry.BrainExplainTooltip = "Erklärung nicht verfügbar.";
                entry.IsBrainExplainLoaded = true;
            });
        }
        finally
        {
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                entry.IsBrainExplainLoading = false;
            });
        }
    }

    /// <summary>
    /// Reagiert auf BrainFeedbackAppliedMessage: invalidiert den Tooltip-Cache fuer den
    /// betroffenen Cut und laedt /brain/explain neu — final_score aktualisiert auch
    /// den Confidence-Balken (BrainConfidence).
    /// </summary>
    private async Task OnBrainFeedbackAppliedAsync(int cutId)
    {
        if (cutId <= 0) return;

        var entry = TimelineEntries.FirstOrDefault(e => e.CutId == cutId);
        if (entry == null) return;

        // Cache invalidieren, damit der naechste Hover (oder die jetzige Re-Fetch) frische Daten zieht.
        await Application.Current.Dispatcher.InvokeAsync(() =>
        {
            entry.IsBrainExplainLoaded = false;
            entry.BrainExplainTooltip = null;
        });

        try
        {
            var explain = await _api.BrainExplainAsync(cutId, topN: 3).ConfigureAwait(false);
            if (explain == null) return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                // BrainConfidence aktualisiert den Balken (rot..gruen) live.
                entry.BrainConfidence = explain.FinalScore;
                entry.BrainExplainTooltip = FormatExplainTooltip(explain);
                entry.IsBrainExplainLoaded = true;
            });
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Live-Refresh fuer Cut {cutId} fehlgeschlagen: {ex.Message}");
        }
    }

    private static string FormatExplainTooltip(BrainExplainResponse e)
    {
        var sb = new StringBuilder();

        // ---- LLM-Narrativ (falls vorhanden) zuerst, damit es prominent steht.
        if (!string.IsNullOrWhiteSpace(e.Narrative))
        {
            sb.AppendLine(e.Narrative.Trim());
            sb.AppendLine();
            sb.AppendLine("────────────");
            sb.AppendLine();
        }

        sb.Append("Brain-Confidence: ").Append((e.FinalScore * 100).ToString("F0")).AppendLine(" %");
        if (!string.IsNullOrEmpty(e.SegmentType))
            sb.Append("Segment: ").AppendLine(e.SegmentType);

        sb.AppendLine();
        sb.AppendLine("Top-Achsen:");
        if (e.TopAxes != null && e.TopAxes.Count > 0)
        {
            foreach (var ax in e.TopAxes.Take(3))
            {
                sb.Append("  • ")
                  .Append(ax.Axis)
                  .Append(": ")
                  .Append((ax.Score * 100).ToString("F0"))
                  .Append(" %  (post=")
                  .Append((ax.Posterior * 100).ToString("F0"))
                  .Append(" %, bridge=")
                  .Append((ax.Bridge_value * 100).ToString("F0"))
                  .Append(" %, n=")
                  .Append(ax.N_samples)
                  .AppendLine(")");
            }
        }
        else
        {
            sb.AppendLine("  (keine Daten)");
        }

        if (e.BottomAxes != null && e.BottomAxes.Count > 0)
        {
            sb.AppendLine();
            sb.AppendLine("Bottom-Achsen (ziehen Score):");
            foreach (var ax in e.BottomAxes.Take(3))
            {
                sb.Append("  • ")
                  .Append(ax.Axis)
                  .Append(": ")
                  .Append((ax.Score * 100).ToString("F0"))
                  .Append(" %  (post=")
                  .Append((ax.Posterior * 100).ToString("F0"))
                  .Append(" %, n=")
                  .Append(ax.N_samples)
                  .AppendLine(")");
            }
        }

        if (e.ColdStartAxes != null && e.ColdStartAxes.Count > 0)
        {
            sb.AppendLine();
            sb.Append("Cold-Start (< 10 Samples): ").AppendLine(string.Join(", ", e.ColdStartAxes.Take(6)));
            if (e.ColdStartAxes.Count > 6)
                sb.Append("  … +").Append(e.ColdStartAxes.Count - 6).AppendLine(" weitere");
        }

        if (e.ContextKeys != null && e.ContextKeys.Count > 0)
        {
            sb.AppendLine();
            sb.Append("Kontexte: ");
            // Leere Strings (Level-0 global) als "global" anzeigen, sonst original.
            var keys = e.ContextKeys.Select(k => string.IsNullOrEmpty(k) ? "global" : k);
            sb.AppendLine(string.Join(" → ", keys));
        }

        return sb.ToString().TrimEnd();
    }

    /// <summary>
    /// Audit L-TI-4: re-sortiert <see cref="TimelineEntries"/> nach <see cref="TimelineEntryModel.StartTime"/>
    /// aufsteigend. Wird nach einem Drag-Commit (MouseUp in TimelineView) aufgerufen, weil Drag die
    /// zeitliche Position ändert ohne den Collection-Index zu aktualisieren — sonst divergiert
    /// Index- von Zeit-Reihenfolge (NextCut/PreviousCut, Render-Order broken).
    /// In-place via ObservableCollection.Move um Bindings/Selection nicht zu verlieren.
    /// </summary>
    public void SortEntriesByTime()
    {
        if (TimelineEntries == null || TimelineEntries.Count < 2) return;

        var sorted = TimelineEntries.OrderBy(e => e.StartTime).ToList();

        // Early-out wenn bereits sortiert (kein Move-Event-Spam an Bindings).
        bool needsResort = false;
        for (int i = 0; i < sorted.Count; i++)
        {
            if (!ReferenceEquals(sorted[i], TimelineEntries[i]))
            {
                needsResort = true;
                break;
            }
        }
        if (!needsResort) return;

        for (int i = 0; i < sorted.Count; i++)
        {
            int currentIdx = TimelineEntries.IndexOf(sorted[i]);
            if (currentIdx != i)
            {
                TimelineEntries.Move(currentIdx, i);
            }
        }

        // Selection-Index-Anzeige & Nav-Commands aktualisieren (Index hat sich evtl. geaendert).
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
        UpdateViewportEntries();
    }

    private void ResetTimelineState()
    {
        CancelProjectOperations();
        ResetAssetLoads();
        Interlocked.Increment(ref _loadVersion);
        Interlocked.Increment(ref _waveformSequence);
        Interlocked.Increment(ref _motionLoadSequence);
        _reloadQueued = false;
        TimelineEntries.Clear();
        VisibleTimelineEntries.Clear();
        _assetWindowEntries.Clear();
        WaveformBars.Clear();
        BeatMarkers.Clear();
        UIBeatMarkers.Clear();
        SnapMarkers.Clear();
        SongSegments.Clear();
        TotalDuration = 0;
        AudioPath = null;
        SelectedEntry = null;
        SelectedTimelinePosition = 0;
        MotionCurve = null;
        PreviewVideoPath = null;
        PreviewStatus = "";
        IsLoading = false;
        IsLoadingWaveform = false;
        StatusText = "Kein Projekt geöffnet";
        var resetVersion = Interlocked.Increment(ref _editVersion);
        Interlocked.Exchange(ref _savedEditVersion, resetVersion);
        OnPropertyChanged(nameof(HasTimeline));
        OnPropertyChanged(nameof(CanPreviewSelectedClip));
        OnPropertyChanged(nameof(SelectedPreviewRange));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        OnPropertyChanged(nameof(TimelineWidth));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _projectService.ProjectTransitionStarted -= OnProjectTransitionStarted;
        CancelProjectOperations();
        Interlocked.Increment(ref _loadVersion);
        Interlocked.Increment(ref _waveformSequence);
        Interlocked.Increment(ref _motionLoadSequence);
        _reloadQueued = false;
        CancelAssetLoads();
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }

    private void ResetAssetLoads()
    {
        CancellationTokenSource? previous;
        lock (_assetLoadLock)
        {
            previous = _assetLoadCts;
            _assetLoadCts = new CancellationTokenSource();
            _assetLoads.Clear();
        }
        previous?.Cancel();
        previous?.Dispose();
    }

    private void CancelAssetLoads()
    {
        CancellationTokenSource? previous;
        lock (_assetLoadLock)
        {
            previous = _assetLoadCts;
            _assetLoadCts = null;
            _assetLoads.Clear();
        }
        previous?.Cancel();
        previous?.Dispose();
    }
}
