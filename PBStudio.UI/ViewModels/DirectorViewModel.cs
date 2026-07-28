using System.Collections.ObjectModel;
using System.Linq;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using System.Text.Json;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Smart Director / Pacing Tab.</summary>
public partial class DirectorViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly VideoLibraryStateService _videoLibraryState;
    private readonly SSEClient _sseClient;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private int _loadVersion;
    private volatile bool _reloadQueued;
    private volatile bool _isShuttingDown;
    private bool _disposed;
    private int? _activePacingAudioClipId;

    [ObservableProperty] private double _expectedBpm = 120.0;
    [ObservableProperty] private double _beatWeight = 1.0;
    [ObservableProperty] private double _onsetWeight = 0.5;
    [ObservableProperty] private double _kickWeight = 1.2;
    [ObservableProperty] private double _snareWeight = 1.0;
    [ObservableProperty] private double _hihatWeight = 0.3;
    [ObservableProperty] private double _energyWeight = 0.8;
    [ObservableProperty] private double _energyThreshold = 0.6;
    [ObservableProperty] private double _minClipLength = 1.0;
    [ObservableProperty] private double _maxClipLength = 8.0;
    [ObservableProperty] private double _onsetSensitivity = 0.5;
    [ObservableProperty] private double _minCutInterval = 0.5;
    [ObservableProperty] private bool _useMotionMatching;
    [ObservableProperty] private bool _useSemanticMatching;
    [ObservableProperty] private bool _useStructureAwareness;
    // Brain-Wiring: UseBrain aktiviert das Reranker-/Lern-System im Backend (pacing_router.py:87
    // → BrainReranker → cut_id-Persistenz). Ohne diese beiden Felder bleibt /brain/explain,
    // /brain/feedback und die Lern-Session funktional tot — siehe pacing_schemas.py:51-52.
    [ObservableProperty] private bool _useBrain;
    [ObservableProperty] private double _brainMinConfidence;
    // Audit E1: Tonart-Matching aktiviert Camelot-Wheel-basierte Key-Compatibility
    // im Pacing-Engine-clip_selector. Backend-Schema: use_key_matching (default false).
    [ObservableProperty] private bool _useKeyMatching;
    // L-K5: Stem-basiertes Pacing — nutzt Demucs-Stems (drums/bass) als
    // Cut-Trigger. Backend-Schema: use_stem_pacing (default false).
    [ObservableProperty] private bool _useStemPacing;
    [ObservableProperty] private double? _durationLimit;
    [ObservableProperty] private string? _canvasPath;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty]
    [NotifyCanExecuteChangedFor(nameof(GenerateCutListCommand))]
    private bool _isGenerating;
    [ObservableProperty] private int _cutCount;
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private AudioClipModel? _selectedAudioClip;
    [ObservableProperty] private int _selectedVideoClipCount;

    public ObservableCollection<AudioClipModel> AvailableAudioClips { get; } = [];
    public ObservableCollection<SelectableVideoClip> AvailableVideoClips { get; } = [];
    public ObservableCollection<TimelineEntryModel> CutList { get; } = [];
    public ObservableCollection<BrainSuggestionViewItem> BrainSuggestions { get; } = [];

    [ObservableProperty] private int _brainSuggestTopN = 20;
    [ObservableProperty] private bool _isLoadingSuggestions;
    [ObservableProperty] private string _suggestionsStatus = "";
    [ObservableProperty] private double _generationProgress;
    [ObservableProperty] private string _currentStep = "";

    public DirectorViewModel(IApiClient api, AudioLibraryStateService audioLibraryState, VideoLibraryStateService videoLibraryState, SSEClient sseClient)
    {
        _api = api;
        _audioLibraryState = audioLibraryState;
        _videoLibraryState = videoLibraryState;
        _sseClient = sseClient;

        _sseClient.ProgressReceived += OnSseProgressReceived;

        void HandleReload()
        {
            if (_isShuttingDown) return;
            _ = RequestClipReloadAsync();
        }

        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<AudioLibraryRefreshMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<VideoLibraryRefreshMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<MediaLibraryRefreshMessage>(this, (_, _) => HandleReload());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
        {
            if (_isShuttingDown) return;
            // Send() kann von Background-Thread (ProjectService) - UI-Touches via Dispatcher
            System.Windows.Application.Current.Dispatcher.Invoke(ResetProjectState);
        });

        // Root-Cause-Fix (2026-07-09): Seit T019 (3752db1) ist dieser VM scoped
        // und wird erst beim Tab-Load erzeugt — die ProjectOpenedMessage vom
        // App-Start ist dann laengst verpasst -> Tab blieb leer, Timeline-
        // Generierung unmoeglich. Initial-Load holt den aktuellen Stand nach.
        HandleReload();
    }

    [RelayCommand]
    private async Task LoadClipsAsync()
    {
        if (_isShuttingDown)
            return;

        _reloadQueued = false;
        var version = Interlocked.Increment(ref _loadVersion);

        if (!await _loadGate.WaitAsync(0))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            var videoClips = await _videoLibraryState.RefreshAsync();
            if (videoClips != null && version == _loadVersion && !_isShuttingDown)
            {
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    if (version != Volatile.Read(ref _loadVersion) || _isShuttingDown)
                        return;

                    // Review-Fix MEDIUM (2026-07-09): User-Deselektionen ueber
                    // Library-Refreshes erhalten — nur NEUE Clips defaulten auf true.
                    var previousSelection = AvailableVideoClips.ToDictionary(c => c.Id, c => c.IsSelected);
                    AvailableVideoClips.Clear();
                    foreach (var clip in videoClips)
                    {
                        AvailableVideoClips.Add(new SelectableVideoClip
                        {
                            Id = clip.Id,
                            Name = clip.Name,
                            DurationSeconds = clip.DurationSeconds,
                            IsSelected = previousSelection.TryGetValue(clip.Id, out var wasSelected) ? wasSelected : true
                        });
                    }
                });
            }

            var audioClips = await _audioLibraryState.RefreshAsync();
            if (audioClips != null && version == _loadVersion && !_isShuttingDown)
            {
                var previousAudioClipId = SelectedAudioClip?.Id;
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    if (version != Volatile.Read(ref _loadVersion) || _isShuttingDown)
                        return;

                    AvailableAudioClips.Clear();
                    foreach (var clip in audioClips)
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
                            // L-FE-13: AudioHash + StemsPaths durchreichen,
                            // sonst ist SelectedAudioClip.HasStems im Director-Kontext
                            // immer false und UseStemPacing-Toggle bleibt blind.
                            // Backend (audio/clips) liefert beide bereits — Audit hatte
                            // sie nur im AudioLibraryVM gemappt, nicht hier.
                            AudioHash = clip.AudioHash,
                            StemsPaths = clip.StemsPaths,
                        });
                    }

                    SelectedAudioClip = AvailableAudioClips.FirstOrDefault(c => c.Id == previousAudioClipId)
                        ?? AvailableAudioClips.FirstOrDefault();
                });
            }

            if (version == _loadVersion && !_isShuttingDown)
            {
                UpdateSelectedCount();
                StatusText = $"{AvailableVideoClips.Count} Video / {AvailableAudioClips.Count} Audio Clips geladen";
            }
        }
        finally
        {
            _loadGate.Release();
        }

        if (_reloadQueued && !_isShuttingDown)
            await LoadClipsAsync();
    }

    private async Task RequestClipReloadAsync()
    {
        _reloadQueued = true;
        await LoadClipsAsync();
    }

    [RelayCommand]
    private void SelectAllVideoClips()
    {
        foreach (var clip in AvailableVideoClips)
            clip.IsSelected = true;
        UpdateSelectedCount();
    }

    [RelayCommand]
    private void DeselectAllVideoClips()
    {
        foreach (var clip in AvailableVideoClips)
            clip.IsSelected = false;
        UpdateSelectedCount();
    }

    public void UpdateSelectedCount()
    {
        SelectedVideoClipCount = AvailableVideoClips.Count(c => c.IsSelected);
    }

    private bool CanGenerateCutList() =>
        !IsGenerating && SelectedAudioClip != null && SelectedVideoClipCount > 0;

    partial void OnSelectedAudioClipChanged(AudioClipModel? value)
    {
        if (value != null && value.Bpm > 0)
        {
            ExpectedBpm = value.Bpm;
        }
        NotifyOnUiThread(() => GenerateCutListCommand.NotifyCanExecuteChanged());
    }

    partial void OnSelectedVideoClipCountChanged(int value)
        => NotifyOnUiThread(() => GenerateCutListCommand.NotifyCanExecuteChanged());

    // B2-Fix (2026-05-19): NotifyCanExecuteChanged braucht UI-Thread-Affinity.
    // Wenn LoadClipsAsync auf Background-Thread laeuft und SelectedVideoClipCount
    // setzt, triggert OnSelectedVideoClipCountChanged ohne Dispatcher → AggregateException
    // (siehe wpf_app.log 17:02:29). Marshal explizit auf UI-Thread.
    private static void NotifyOnUiThread(Action action)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher == null || dispatcher.CheckAccess())
            action();
        else
            dispatcher.BeginInvoke(action);
    }

    [RelayCommand(CanExecute = nameof(CanGenerateCutList))]
    private async Task GenerateCutListAsync()
    {
        if (_isShuttingDown) return;

        if (SelectedAudioClip == null)
        {
            StatusText = "Kein Audio-Clip ausgewählt";
            return;
        }

        var selectedVideoIds = AvailableVideoClips
            .Where(c => c.IsSelected)
            .Select(c => c.Id)
            .ToList();

        if (selectedVideoIds.Count == 0)
        {
            StatusText = "Keine Video-Clips ausgewählt";
            return;
        }

        IsGenerating = true;
        _activePacingAudioClipId = SelectedAudioClip.Id;
        StatusText = "Generiere Cut-Liste...";

        try
        {
            var config = new PacingConfig(
                AudioClipId: SelectedAudioClip.Id,
                VideoClipIds: selectedVideoIds,
                ExpectedBpm: ExpectedBpm,
                UseMotionMatching: UseMotionMatching,
                UseSemanticMatching: UseSemanticMatching,
                UseStructureAwareness: UseStructureAwareness,
                DurationLimit: DurationLimit,
                MinCutInterval: MinCutInterval,
                TriggerSettings: new TriggerSettings(
                    BeatWeight: BeatWeight,
                    OnsetWeight: OnsetWeight,
                    KickWeight: KickWeight,
                    SnareWeight: SnareWeight,
                    HihatWeight: HihatWeight,
                    EnergyWeight: EnergyWeight,
                    EnergyThreshold: EnergyThreshold,
                    MinClipLength: MinClipLength,
                    MaxClipLength: MaxClipLength,
                    OnsetSensitivity: OnsetSensitivity
                ),
                UseBrain: UseBrain,
                BrainMinConfidence: BrainMinConfidence,
                UseKeyMatching: UseKeyMatching,
                UseStemPacing: UseStemPacing,
                CanvasPath: CanvasPath
            );

            var result = await _api.GenerateCutListAsync(config);
            if (result != null && result.Cuts.Count > 0)
            {
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    CutList.Clear();
                    foreach (var cut in result.Cuts)
                    {
                        var meta = cut.Metadata;
                        CutList.Add(new TimelineEntryModel
                        {
                            ClipId = cut.ClipId,
                            StartTime = cut.StartTime,
                            EndTime = cut.EndTime,
                            ClipName = meta?.GetValueOrDefault("clip_name")?.ToString() ?? "",
                            FilePath = meta?.GetValueOrDefault("file_path")?.ToString() ?? "",
                            ClipStart = meta?.TryGetValue("clip_start", out var cs) == true ? ConvertToDoubleSafe(cs) : 0.0,
                            TriggerType = meta?.GetValueOrDefault("trigger_type")?.ToString() ?? "",
                            TriggerStrength = meta?.TryGetValue("trigger_strength", out var ts) == true ? ConvertToDoubleSafe(ts) : 0.0,
                            SegmentType = meta?.GetValueOrDefault("segment_type")?.ToString(),
                        });
                    }
                    CutCount = result.CutCount;
                    TotalDuration = result.TotalDuration;
                });
                StatusText = $"{result.CutCount} Cuts generiert ({result.TotalDuration:F1}s)";
                WeakReferenceMessenger.Default.Send(new TimelineRefreshMessage());
            }
            else
            {
                StatusText = result == null ? "Fehler: Backend-Antwort ungültig" : "Warnung: Keine Schnitte generiert (Audio-Dauer prüfen)";
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    CutList.Clear();
                    CutCount = 0;
                    TotalDuration = 0;
                });
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Cut-Liste generieren fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            _activePacingAudioClipId = null;
            IsGenerating = false;
        }
    }

    [RelayCommand]
    private async Task LoadBrainSuggestionsAsync()
    {
        if (SelectedAudioClip == null)
        {
            SuggestionsStatus = "Kein Audio-Clip ausgewählt.";
            return;
        }

        var videoIds = AvailableVideoClips.Where(c => c.IsSelected).Select(c => c.Id).ToList();

        IsLoadingSuggestions = true;
        SuggestionsStatus = "Lade Top-N Vorschläge…";
        try
        {
            var resp = await _api.BrainSuggestAsync(SelectedAudioClip.Id, videoIds, BrainSuggestTopN);
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                BrainSuggestions.Clear();
                if (resp?.Suggestions == null || resp.Suggestions.Count == 0)
                {
                    SuggestionsStatus = "Keine Vorschläge — Pacing zuerst mit Brain (Lern-Modus) laufen lassen.";
                    return;
                }
                foreach (var s in resp.Suggestions.OrderByDescending(s => s.FinalScore))
                {
                    BrainSuggestions.Add(new BrainSuggestionViewItem(s));
                }
                SuggestionsStatus = $"{BrainSuggestions.Count} Vorschläge.";
            });
        }
        catch (Exception ex)
        {
            SuggestionsStatus = "Fehler: " + ex.Message;
        }
        finally
        {
            IsLoadingSuggestions = false;
        }
    }

    private static double ConvertToDoubleSafe(object? value)
    {
        if (value is null)
            return 0.0;

        if (value is JsonElement json)
        {
            return json.ValueKind switch
            {
                JsonValueKind.Number when json.TryGetDouble(out var number) => number,
                JsonValueKind.String when double.TryParse(json.GetString(), out var parsed) => parsed,
                _ => 0.0,
            };
        }

        try
        {
            return Convert.ToDouble(value);
        }
        catch
        {
            return 0.0;
        }
    }

    private void ResetProjectState()
    {
        _isShuttingDown = false;
        AvailableAudioClips.Clear();
        AvailableVideoClips.Clear();
        CutList.Clear();
        SelectedAudioClip = null;
        SelectedVideoClipCount = 0;
        CutCount = 0;
        TotalDuration = 0;
        IsGenerating = false;
        StatusText = "Kein Projekt geöffnet";
    }

    private void OnSseProgressReceived(object? sender, ProgressEventArgs e)
    {
        if (e.EventType != "pacing_progress" || !IsGenerating ||
            !_activePacingAudioClipId.HasValue ||
            e.ClipId != _activePacingAudioClipId.Value)
            return;

        Application.Current.Dispatcher.Invoke(() =>
        {
            StatusText = e.Message;
            if (e.Percent >= 0) GenerationProgress = e.Percent;
            if (!string.IsNullOrEmpty(e.Step)) CurrentStep = e.Step;
        });
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _isShuttingDown = true;
        Interlocked.Increment(ref _loadVersion);
        _reloadQueued = false;
        _sseClient.ProgressReceived -= OnSseProgressReceived;
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}

/// <summary>Video-Clip mit Auswahl-Checkbox für den Director.</summary>
public partial class SelectableVideoClip : ObservableObject
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public double DurationSeconds { get; set; }
    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");

    [ObservableProperty] private bool _isSelected;
}

/// <summary>Read-only View für /brain/suggest-Antworten in der Director-UI.</summary>
public class BrainSuggestionViewItem
{
    public BrainSuggestionViewItem(BrainSuggestion s)
    {
        CutId = s.CutId ?? 0;
        ClipId = s.ClipId ?? "";
        StartTime = s.StartTime;
        EndTime = s.EndTime;
        FinalScore = s.FinalScore;
        BrainScores = s.BrainScores ?? new Dictionary<string, double>();
    }

    public int CutId { get; }
    public string ClipId { get; }
    public double StartTime { get; }
    public double EndTime { get; }
    public double FinalScore { get; }
    public Dictionary<string, double> BrainScores { get; }

    public string TimeRangeText => $"{TimeSpan.FromSeconds(StartTime):mm\\:ss\\.ff} → {TimeSpan.FromSeconds(EndTime):mm\\:ss\\.ff}";
    public double Duration => Math.Max(0.0, EndTime - StartTime);
    public string ScorePercentText => (FinalScore * 100).ToString("F0") + " %";
}
