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
    private readonly TimelineStateService _timelineState;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly ApiClient _api;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private int _loadVersion;
    private int _waveformSequence;
    private volatile bool _reloadQueued;
    private bool _disposed;
    private bool _isSyncingSelection;

    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private string? _audioPath;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private bool _isLoadingWaveform;
    [ObservableProperty] private TimelineEntryModel? _selectedEntry;
    [ObservableProperty] private double _selectedTimelinePosition;
    [ObservableProperty] private double _pixelsPerSecond = 100.0;
    [ObservableProperty] private double _horizontalOffset = 0.0;

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
    public ObservableCollection<WaveformBarModel> WaveformBars { get; } = [];
    public ObservableCollection<double> BeatMarkers { get; } = [];
    public ObservableCollection<double> SnapMarkers { get; } = [];
    public ObservableCollection<SongSegmentModel> SongSegments { get; } = [];

    public TimelineViewModel(TimelineStateService timelineState, AudioLibraryStateService audioLibraryState, ApiClient api)
    {
        _timelineState = timelineState;
        _audioLibraryState = audioLibraryState;
        _api = api;

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
    public bool CanPreviewSelectedClip => SelectedEntry != null && File.Exists(SelectedEntry.FilePath);
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

        OnPropertyChanged(nameof(SelectedClipName));
        OnPropertyChanged(nameof(SelectedTrigger));
        OnPropertyChanged(nameof(SelectedClipStart));
        OnPropertyChanged(nameof(SelectedTimeRange));
        OnPropertyChanged(nameof(SelectedFilePath));
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
            MotionCurve = null;
        }

        if (value != null && !value.IsAssetsLoaded)
        {
            _ = LoadClipAssetsAsync(value);
        }
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
    private async Task LoadClipAssetsAsync(TimelineEntryModel entry)
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
            var stripTask = _api.GetThumbStripAsync(cid, n: 8);
            var waveTask = _api.GetClipWaveAsync(cid, n: 256);
            await Task.WhenAll(stripTask, waveTask).ConfigureAwait(false);

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                if (stripTask.Result?.Frames is { Count: > 0 } frames)
                    entry.ThumbnailFrames = new ObservableCollection<string>(frames);
                if (waveTask.Result?.Peaks is { Count: > 0 } peaks)
                    entry.AudioPeaks = new ObservableCollection<float>(peaks);
                entry.IsAssetsLoaded = true;
            });
        }
        catch (Exception ex)
        {
            Debug.WriteLine($"Clip-Assets-Load fehlgeschlagen fuer clip {cid}: {ex.Message}");
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

    [RelayCommand]
    private async Task RefreshTimelineAsync()
    {
        _reloadQueued = false;
        var version = Interlocked.Increment(ref _loadVersion);

        if (!await _loadGate.WaitAsync(0))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            IsLoading = true;
            StatusText = "Timeline wird geladen...";

            var timeline = await _timelineState.RefreshAsync();
            if (timeline == null)
            {
                if (version == _loadVersion)
                    StatusText = "Timeline laden fehlgeschlagen";
                return;
            }

            if (version != _loadVersion)
                return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
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
                    });
                }

                TotalDuration = timeline.TotalDuration;
                AudioPath = timeline.AudioPath;
                SelectedEntry = TimelineEntries.FirstOrDefault();
                SelectedTimelinePosition = SelectedEntry?.StartTime ?? 0;

                // Eagerly load assets for the first N visible clips (rest load on-demand).
                foreach (var e in TimelineEntries.Take(20))
                {
                    _ = LoadClipAssetsAsync(e);
                }

                StatusText = TimelineEntries.Count == 0
                    ? "Timeline ist leer"
                    : $"Timeline: {TimelineEntries.Count} Clips, {TotalDuration:F1}s";
                OnPropertyChanged(nameof(HasTimeline));
                OnPropertyChanged(nameof(SelectedTimelinePositionText));
                OnPropertyChanged(nameof(SelectionIndexText));
                OnPropertyChanged(nameof(TimelineWidth));
                PreviousCutCommand.NotifyCanExecuteChanged();
                NextCutCommand.NotifyCanExecuteChanged();

                if (!string.IsNullOrEmpty(AudioPath))
                {
                    _ = LoadWaveformAsync(AudioPath);
                }
            });
        }
        finally
        {
            IsLoading = false;
            _loadGate.Release();
        }

        if (_reloadQueued)
            await RefreshTimelineAsync();
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

        IsGeneratingPreview = true;
        PreviewStatus = $"Rendere Preview ({PreviewDurationSec:F0}s ab {PreviewStartSec:F1}s)…";
        try
        {
            var resp = await _api.GenerateTimelinePreviewAsync(PreviewStartSec, PreviewDurationSec);
            if (resp == null || string.IsNullOrEmpty(resp.PreviewPath))
            {
                PreviewStatus = "Preview fehlgeschlagen — Backend lieferte keinen Pfad.";
                return;
            }

            if (!File.Exists(resp.PreviewPath))
            {
                PreviewStatus = $"Preview-Datei nicht gefunden: {resp.PreviewPath}";
                return;
            }

            PreviewVideoPath = resp.PreviewPath;
            PreviewStatus = $"Preview bereit: {resp.Resolution} · {resp.Duration:F1}s";
            PreviewReady?.Invoke(resp.PreviewPath);
        }
        catch (Exception ex)
        {
            PreviewStatus = "Fehler: " + ex.Message;
        }
        finally
        {
            IsGeneratingPreview = false;
        }
    }

    [RelayCommand]
    public async Task SyncTimelineAsync()
    {
        try
        {
            StatusText = "Speichere Änderungen...";
            var entries = TimelineEntries.ToList();
            var response = await _api.UpdateTimelineAsync(entries);

            if (response?.Success == true)
            {
                StatusText = "Änderungen gespeichert";
            }
            else
            {
                StatusText = "Speichern fehlgeschlagen: " + (response?.Message ?? "Unbekannter Fehler");
            }
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Synchronisieren: " + ex.Message;
        }
    }

    private async Task LoadWaveformAsync(string audioPath)
    {
        var seq = Interlocked.Increment(ref _waveformSequence);

        try
        {
            IsLoadingWaveform = true;

            // Suche Audio ID über State Service
            var clips = await _audioLibraryState.RefreshAsync();
            var audioClip = clips?.FirstOrDefault(c => string.Equals(c.Path, audioPath, StringComparison.OrdinalIgnoreCase));

            if (audioClip == null || seq != _waveformSequence) return;

            var waveform = await _api.GetWaveformAsync(audioClip.Id, bands: 1);
            var beats = await _api.GetBeatsAsync(audioClip.Id);
            var onsets = await _api.GetOnsetsAsync(audioClip.Id);
            var structure = await _api.GetAsync<List<SongSegmentModel>>($"/audio/structure/{audioClip.Id}");
            var spectral = await _api.GetAsync<SpectralDataModel>($"/audio/spectral/{audioClip.Id}");

            if (waveform == null || seq != _waveformSequence) return;

            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                WaveformBars.Clear();
                BeatMarkers.Clear();
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
                    foreach (var b in beats)
                    {
                        BeatMarkers.Add(b.Time);
                        SnapMarkers.Add(b.Time);
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
                  .Append((ax.BridgeValue * 100).ToString("F0"))
                  .Append(" %, n=")
                  .Append(ax.NSamples)
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
                  .Append(ax.NSamples)
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
    }

    private void ResetTimelineState()
    {
        TimelineEntries.Clear();
        WaveformBars.Clear();
        TotalDuration = 0;
        AudioPath = null;
        SelectedEntry = null;
        SelectedTimelinePosition = 0;
        MotionCurve = null;
        IsLoading = false;
        StatusText = "Kein Projekt geöffnet";
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
        WeakReferenceMessenger.Default.UnregisterAll(this);
        _loadGate.Dispose();
    }
}
