using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Anchor-Bearbeitung (Beat-Marker + Video-Zuordnung).</summary>
public partial class AnchorViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly ProjectService _projectService;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private readonly SemaphoreSlim _anchorIoGate = new(1, 1);
    private readonly CancellationTokenSource _shutdownCts = new();
    private bool _disposed;
    private bool _isAnchorIoBusy;
    private int _anchorIoOperations;
    private readonly HashSet<int> _beatsUnavailableClipIds = [];
    private int _loadSequence;
    private volatile bool _reloadQueued;
    private const double WaveformWidth = 720.0;
    private const double WaveformHeight = 180.0;
    private const int MaxWaveformBars = 180;

    [ObservableProperty] private string _statusText = "Anchors werden hier definiert";
    [ObservableProperty] private double _currentPosition;
    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(RemoveAnchorCommand))]
    private AnchorPoint? _selectedAnchor;
    [ObservableProperty] private AudioClipModel? _selectedAudioClip;
    [ObservableProperty] private bool _isLoadingWaveform;
    [ObservableProperty] private double _timelineDuration = 300;
    [ObservableProperty] private double _positionMarkerX;

    public ObservableCollection<AnchorPoint> Anchors { get; } = [];
    public ObservableCollection<AudioClipModel> AvailableAudioClips { get; } = [];
    public ObservableCollection<WaveformBar> WaveformBars { get; } = [];
    public ObservableCollection<BeatMarker> BeatMarkers { get; } = [];

    public AnchorViewModel(
        IApiClient api,
        AudioLibraryStateService audioLibraryState,
        ProjectService projectService)
    {
        _api = api;
        _audioLibraryState = audioLibraryState;
        _projectService = projectService;

        WeakReferenceMessenger.Default.Register<AudioLibraryRefreshMessage>(this, (_, _) => _ = RequestAudioReloadAsync());
        WeakReferenceMessenger.Default.Register<AudioImportedMessage>(this, (_, _) => _ = RequestAudioReloadAsync());
        WeakReferenceMessenger.Default.Register<MediaLibraryRefreshMessage>(this, (_, _) => _ = RequestAudioReloadAsync());
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) =>
        {
            _ = RequestAudioReloadAsync();
            // Audit 2026-08-06 (T4.3): gespeicherte Anker beim Projektwechsel laden.
            _ = LoadAnchorsAsync();
        });
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            RunOnUiThread(ResetProjectState));

        // Root-Cause-Fix (2026-07-09): Scoped-VM (seit T019/3752db1) entsteht
        // erst beim Tab-Load und verpasst die ProjectOpenedMessage vom
        // App-Start -> Audio-Quellen blieben leer. Initial-Load holt nach.
        _ = RequestAudioReloadAsync();
        _ = LoadAnchorsAsync();
    }

    partial void OnSelectedAudioClipChanged(AudioClipModel? value)
    {
        TimelineDuration = value?.DurationSeconds > 0 ? value.DurationSeconds : 300;
        CurrentPosition = 0;
        _ = LoadWaveformAndBeatsAsync(forceBeatReload: false);
    }

    partial void OnCurrentPositionChanged(double value)
    {
        var max = TimelineDuration > 0 ? TimelineDuration : 300;
        if (value < 0)
            CurrentPosition = 0;
        else if (value > max)
            CurrentPosition = max;
        else
            UpdatePositionMarker();
    }

    partial void OnTimelineDurationChanged(double value)
    {
        UpdatePositionMarker();
    }

    private async Task LoadAudioSourcesAsync()
    {
        if (_disposed)
            return;

        _reloadQueued = false;

        if (!await _loadGate.WaitAsync(0))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            var clips = await _audioLibraryState.RefreshAsync();
            if (_disposed)
                return;

            if (clips == null)
            {
                StatusText = "Audio-Quellen laden fehlgeschlagen";
                return;
            }

            var selectedClipId = SelectedAudioClip?.Id;

            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                if (_disposed)
                    return;

                AvailableAudioClips.Clear();
                foreach (var clip in clips)
                {
                    AvailableAudioClips.Add(new AudioClipModel
                    {
                        Id = clip.Id,
                        Name = clip.Name,
                        Path = clip.Path,
                        DurationSeconds = clip.DurationSeconds,
                        SampleRate = clip.SampleRate,
                        Channels = clip.Channels,
                        Format = clip.Format,
                        Bpm = clip.Bpm,
                        Key = clip.Key ?? "",
                        BeatCount = clip.BeatCount,
                        IsAnalyzed = clip.IsAnalyzed,
                    });
                }
            });

            if (_disposed)
                return;

            var nextSelection = selectedClipId.HasValue
                ? AvailableAudioClips.FirstOrDefault(c => c.Id == selectedClipId.Value)
                : AvailableAudioClips.FirstOrDefault(c => c.IsAnalyzed) ?? AvailableAudioClips.FirstOrDefault();

            if (nextSelection?.Id != SelectedAudioClip?.Id)
            {
                SelectedAudioClip = nextSelection;
            }
            else if (nextSelection != null && (WaveformBars.Count == 0 || BeatMarkers.Count == 0))
            {
                _ = LoadWaveformAndBeatsAsync(forceBeatReload: false);
            }

            StatusText = $"{AvailableAudioClips.Count} Audio-Quellen verfügbar";
        }
        finally
        {
            _loadGate.Release();
        }

        if (_reloadQueued && !_disposed)
            await LoadAudioSourcesAsync();
    }

    [RelayCommand]
    private async Task ReloadWaveformAsync()
    {
        if (SelectedAudioClip != null)
            _beatsUnavailableClipIds.Remove(SelectedAudioClip.Id);

        await LoadWaveformAndBeatsAsync(forceBeatReload: true);
    }

    [RelayCommand(CanExecute = nameof(CanEditAnchors))]
    private async Task AddAnchorAsync()
    {
        if (!TryCaptureAnchorContext(out var context, reportFailure: true))
            return;

        var anchor = new AnchorPoint
        {
            Time = CurrentPosition,
            Label = $"Anchor {Anchors.Count + 1}",
        };

        Anchors.Add(anchor);
        SelectedAnchor = anchor;
        StatusText = $"Anchor bei {CurrentPosition:F2}s hinzugefügt";
        await PersistAnchorsAsync(context);
    }

    [RelayCommand(CanExecute = nameof(CanRemoveAnchor))]
    private async Task RemoveAnchorAsync()
    {
        if (SelectedAnchor == null)
            return;
        if (!TryCaptureAnchorContext(out var context, reportFailure: true))
            return;

        Anchors.Remove(SelectedAnchor);
        SelectedAnchor = null;
        StatusText = "Anchor entfernt";
        await PersistAnchorsAsync(context);
    }

    private bool CanEditAnchors() =>
        !_disposed && !_isAnchorIoBusy && _projectService.HasProject;

    private bool CanRemoveAnchor() => SelectedAnchor != null && CanEditAnchors();

    /// <summary>
    /// Speichert die Anker im Projekt.
    ///
    /// Audit 2026-08-06 (T4.3): Vorher mutierten AddAnchor/RemoveAnchor nur die
    /// ObservableCollection. Es gab keine Route, kein Schema, keine Persistenz —
    /// und beim Projektwechsel wurde die Liste geleert. Was der User hier anlegte,
    /// beeinflusste weder Schnitte noch Render und ueberlebte keinen Tab-Wechsel.
    /// Jetzt liegen die Anker als anchors.json im Projekt und werden von der
    /// Pacing-Engine als manuelle Anker konsumiert.
    /// </summary>
    private async Task PersistAnchorsAsync(ProjectOperationContext context)
    {
        var gateAcquired = false;
        using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(
            context.CancellationToken,
            _shutdownCts.Token);
        BeginAnchorIo();
        try
        {
            await _anchorIoGate.WaitAsync(linkedCts.Token).ConfigureAwait(true);
            gateAcquired = true;
            if (!_projectService.IsCurrent(context))
                return;

            var payload = Anchors
                .Select(a => new AnchorEntry(a.Time, a.Label, a.VideoClipId))
                .ToList();
            var result = await _api.SetProjectAnchorsAsync(payload, linkedCts.Token).ConfigureAwait(true);
            if (result is null)
            {
                var reason = _api.LastErrorDetail;
                _projectService.TryCommit(context, () =>
                    StatusText = string.IsNullOrWhiteSpace(reason)
                        ? "Anker konnten nicht gespeichert werden"
                        : $"Anker nicht gespeichert: {reason}");
            }
        }
        catch (OperationCanceledException) when (linkedCts.IsCancellationRequested)
        {
            // Projektwechsel/Dispose: Ergebnis darf nicht mehr publiziert werden.
        }
        catch (Exception ex)
        {
            _projectService.TryCommit(context, () =>
                StatusText = $"Anker nicht gespeichert: {ex.Message}");
        }
        finally
        {
            if (gateAcquired)
                _anchorIoGate.Release();
            EndAnchorIo();
        }
    }

    /// <summary>Laedt die im Projekt gespeicherten Anker.</summary>
    private async Task LoadAnchorsAsync()
    {
        if (!TryCaptureAnchorContext(out var context, reportFailure: false))
            return;

        var gateAcquired = false;
        using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(
            context.CancellationToken,
            _shutdownCts.Token);
        BeginAnchorIo();
        try
        {
            await _anchorIoGate.WaitAsync(linkedCts.Token).ConfigureAwait(true);
            gateAcquired = true;
            if (!_projectService.IsCurrent(context))
                return;

            var result = await _api.GetProjectAnchorsAsync(linkedCts.Token).ConfigureAwait(true);
            if (result?.Anchors is null)
                return;

            _projectService.TryCommit(context, () =>
            {
                Anchors.Clear();
                foreach (var entry in result.Anchors)
                {
                    Anchors.Add(new AnchorPoint
                    {
                        Time = entry.Time,
                        Label = entry.Label ?? "",
                        VideoClipId = entry.VideoClipId,
                    });
                }
                StatusText = Anchors.Count > 0
                    ? $"{Anchors.Count} Anker geladen"
                    : "Keine Anker im Projekt";
            });
        }
        catch (OperationCanceledException) when (linkedCts.IsCancellationRequested)
        {
            // Projektwechsel/Dispose: Ergebnis darf nicht mehr publiziert werden.
        }
        catch (Exception ex)
        {
            _projectService.TryCommit(context, () =>
                StatusText = $"Anker nicht geladen: {ex.Message}");
        }
        finally
        {
            if (gateAcquired)
                _anchorIoGate.Release();
            EndAnchorIo();
        }
    }

    private bool TryCaptureAnchorContext(
        out ProjectOperationContext context,
        bool reportFailure)
    {
        try
        {
            context = _projectService.CaptureOperationContext();
            return true;
        }
        catch (ObjectDisposedException)
        {
            context = default;
            return false;
        }
        catch (InvalidOperationException)
        {
            context = default;
            if (reportFailure)
                StatusText = "Kein stabiles Projekt geoeffnet";
            return false;
        }
    }

    private void SetAnchorIoBusy(bool value)
    {
        _isAnchorIoBusy = value;
        AddAnchorCommand.NotifyCanExecuteChanged();
        RemoveAnchorCommand.NotifyCanExecuteChanged();
    }

    private void BeginAnchorIo()
    {
        if (Interlocked.Increment(ref _anchorIoOperations) == 1)
            SetAnchorIoBusy(true);
    }

    private void EndAnchorIo()
    {
        if (Interlocked.Decrement(ref _anchorIoOperations) == 0)
            SetAnchorIoBusy(false);
    }

    private static void RunOnUiThread(Action action)
    {
        var dispatcher = System.Windows.Application.Current?.Dispatcher;
        if (dispatcher == null || dispatcher.CheckAccess())
            action();
        else
            dispatcher.Invoke(action);
    }

    private async Task LoadWaveformAndBeatsAsync(bool forceBeatReload)
    {
        var clip = SelectedAudioClip;
        if (clip == null)
        {
            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                WaveformBars.Clear();
                BeatMarkers.Clear();
            });
            StatusText = "Keine Audio-Quelle ausgewählt";
            return;
        }

        var loadSequence = Interlocked.Increment(ref _loadSequence);

        // R15/MEDIUM: Acquired-Flag explizit tracken — finally darf nur dann Release() rufen,
        // wenn WaitAsync erfolgreich war. Bei Cancellation (OperationCanceledException) wird
        // das Semaphor NICHT akquiriert; ein Release() würde den Lock eines anderen Callers freigeben.
        bool acquired = false;
        try
        {
            await _loadGate.WaitAsync(_shutdownCts.Token);
            acquired = true;
        }
        catch (OperationCanceledException)
        {
            return;
        }

        try
        {
            if (loadSequence != _loadSequence)
                return;

            clip = SelectedAudioClip;
            if (clip == null)
            {
                System.Windows.Application.Current.Dispatcher.Invoke(() =>
                {
                    WaveformBars.Clear();
                    BeatMarkers.Clear();
                });
                StatusText = "Keine Audio-Quelle ausgewählt";
                return;
            }

            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                WaveformBars.Clear();
                BeatMarkers.Clear();
            });
            IsLoadingWaveform = true;
            StatusText = $"Lade Waveform: {clip.Name}...";

            var waveform = await _api.GetWaveformAsync(clip.Id, bands: 3);
            if (loadSequence != _loadSequence || SelectedAudioClip?.Id != clip.Id)
                return;

            var beats = await LoadBeatsAsync(clip, forceBeatReload);
            if (loadSequence != _loadSequence || SelectedAudioClip?.Id != clip.Id)
                return;

            TimelineDuration = waveform?.DurationSeconds > 0
                ? waveform.DurationSeconds
                : clip.DurationSeconds > 0
                    ? clip.DurationSeconds
                    : 300;

            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                BuildWaveformBars(waveform);
                BuildBeatMarkers(beats, TimelineDuration);
            });

            var beatStatus = beats?.Count > 0
                ? $"{BeatMarkers.Count} Beats"
                : clip.IsAnalyzed
                    ? "0 Beats"
                    : "Beat-Analyse ausstehend";
            StatusText = $"Waveform geladen: {WaveformBars.Count} Bars | {beatStatus}";
        }
        catch (OperationCanceledException)
        {
            // Shutdown or sequence superseded — silent exit
        }
        catch (Exception ex)
        {
            StatusText = $"Waveform/Beats laden fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsLoadingWaveform = false;
            if (acquired)
                _loadGate.Release();
        }

        if (_reloadQueued)
            await LoadAudioSourcesAsync();
    }

    private async Task<List<BeatData>?> LoadBeatsAsync(AudioClipModel clip, bool forceBeatReload)
    {
        if (!forceBeatReload && _beatsUnavailableClipIds.Contains(clip.Id))
            return null;

        if (!clip.IsAnalyzed)
            return null;

        var beats = await _api.GetBeatsAsync(clip.Id);
        if (beats != null)
        {
            _beatsUnavailableClipIds.Remove(clip.Id);
            clip.BeatCount = beats.Count;
            return beats;
        }

        var analysis = await _api.AnalyzeAudioAsync(clip.Id);
        if (analysis != null)
        {
            clip.IsAnalyzed = true;
            clip.Bpm = analysis.Bpm;
            clip.Key = analysis.Key ?? string.Empty;
            clip.BeatCount = analysis.BeatCount;
            _beatsUnavailableClipIds.Remove(clip.Id);
            return analysis.Beats;
        }

        clip.IsAnalyzed = false;
        clip.BeatCount = 0;
        _beatsUnavailableClipIds.Add(clip.Id);
        return null;
    }

    private void BuildWaveformBars(WaveformData? waveform)
    {
        WaveformBars.Clear();

        var source = waveform?.Bands?.FirstOrDefault();
        if (source == null || source.Count == 0)
            return;

        var step = Math.Max(1, source.Count / MaxWaveformBars);
        var reduced = new List<float>();
        for (var i = 0; i < source.Count; i += step)
        {
            var slice = source.Skip(i).Take(step).Select(Math.Abs);
            reduced.Add((float)slice.DefaultIfEmpty(0).Average());
        }

        if (reduced.Count == 0)
            return;

        var max = reduced.Max();
        if (max <= 0)
            max = 1;

        var barWidth = WaveformWidth / reduced.Count;
        for (var i = 0; i < reduced.Count; i++)
        {
            var normalized = reduced[i] / max;
            var height = Math.Max(4.0, normalized * WaveformHeight);
            WaveformBars.Add(new WaveformBar
            {
                X = i * barWidth,
                Width = Math.Max(1.5, barWidth - 1),
                Height = height,
                Y = (WaveformHeight - height) / 2.0,
            });
        }
    }

    private void BuildBeatMarkers(List<BeatData>? beats, double durationSeconds)
    {
        BeatMarkers.Clear();

        if (beats == null || beats.Count == 0 || durationSeconds <= 0)
            return;

        foreach (var beat in beats)
        {
            var x = Math.Clamp((beat.Time / durationSeconds) * WaveformWidth, 0, WaveformWidth - 1);
            BeatMarkers.Add(new BeatMarker
            {
                X = x,
                BeatType = beat.BeatType,
                Strength = beat.Strength,
            });
        }
    }

    private void UpdatePositionMarker()
    {
        var duration = TimelineDuration > 0 ? TimelineDuration : 300;
        PositionMarkerX = Math.Clamp((CurrentPosition / duration) * WaveformWidth, 0, WaveformWidth - 2);
    }

    private async Task RequestAudioReloadAsync()
    {
        _reloadQueued = true;
        if (IsLoadingWaveform)
            return;

        await LoadAudioSourcesAsync();
    }

    private void ResetProjectState()
    {
        Interlocked.Increment(ref _loadSequence);
        _reloadQueued = false;
        AvailableAudioClips.Clear();
        WaveformBars.Clear();
        BeatMarkers.Clear();
        Anchors.Clear();
        SelectedAudioClip = null;
        SelectedAnchor = null;
        CurrentPosition = 0;
        TimelineDuration = 300;
        IsLoadingWaveform = false;
        StatusText = "Kein Projekt geöffnet";
        AddAnchorCommand.NotifyCanExecuteChanged();
        RemoveAnchorCommand.NotifyCanExecuteChanged();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        Interlocked.Increment(ref _loadSequence);
        _reloadQueued = false;
        WeakReferenceMessenger.Default.UnregisterAll(this);
        _shutdownCts.Cancel();
    }
}

public partial class AnchorPoint : ObservableObject
{
    [ObservableProperty] private double _time;
    [ObservableProperty] private string _label = "";
    [ObservableProperty] private int? _videoClipId;

    public string TimeText => TimeSpan.FromSeconds(Time).ToString(@"mm\:ss\.ff");

    partial void OnTimeChanged(double value) => OnPropertyChanged(nameof(TimeText));
}

public class WaveformBar
{
    public double X { get; set; }
    public double Y { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
}

public class BeatMarker
{
    public double X { get; set; }
    public string BeatType { get; set; } = "beat";
    public double Strength { get; set; }
}
