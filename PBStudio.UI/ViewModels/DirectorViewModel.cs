using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using System.Text.Json;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Smart Director / Pacing Tab.</summary>
public partial class DirectorViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly VideoLibraryStateService _videoLibraryState;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private int _loadVersion;
    private volatile bool _reloadQueued;
    private volatile bool _isShuttingDown;
    private bool _disposed;

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
    [ObservableProperty] private bool _useStructureAwareness;
    [ObservableProperty] private double? _durationLimit;
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

    public DirectorViewModel(IApiClient api, AudioLibraryStateService audioLibraryState, VideoLibraryStateService videoLibraryState)
    {
        _api = api;
        _audioLibraryState = audioLibraryState;
        _videoLibraryState = videoLibraryState;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "project-opened" or "audio-library-refresh" or "video-library-refresh" or "media-library-refresh")
                _ = RequestClipReloadAsync();
            else if (message.Value is "project-closed")
                ResetProjectState();
        });
    }

    [RelayCommand]
    private async Task LoadClipsAsync()
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
            var videoClips = await _videoLibraryState.RefreshAsync();
            if (videoClips != null && version == _loadVersion)
            {
                AvailableVideoClips.Clear();
                foreach (var clip in videoClips)
                {
                    AvailableVideoClips.Add(new SelectableVideoClip
                    {
                        Id = clip.Id,
                        Name = clip.Name,
                        DurationSeconds = clip.DurationSeconds,
                    });
                }
            }

            var audioClips = await _audioLibraryState.RefreshAsync();
            if (audioClips != null && version == _loadVersion)
            {
                var previousAudioClipId = SelectedAudioClip?.Id;
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
                    });
                }

                SelectedAudioClip = AvailableAudioClips.FirstOrDefault(c => c.Id == previousAudioClipId)
                    ?? AvailableAudioClips.FirstOrDefault();
            }

            if (version == _loadVersion)
            {
                UpdateSelectedCount();
                StatusText = $"{AvailableVideoClips.Count} Video / {AvailableAudioClips.Count} Audio Clips geladen";
            }
        }
        finally
        {
            _loadGate.Release();
        }

        if (_reloadQueued)
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
        => GenerateCutListCommand.NotifyCanExecuteChanged();

    partial void OnSelectedVideoClipCountChanged(int value)
        => GenerateCutListCommand.NotifyCanExecuteChanged();

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
        StatusText = "Generiere Cut-Liste...";

        try
        {
            var config = new PacingConfig(
                AudioClipId: SelectedAudioClip.Id,
                VideoClipIds: selectedVideoIds,
                ExpectedBpm: ExpectedBpm,
                UseMotionMatching: UseMotionMatching,
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
                )
            );

            var result = await _api.GenerateCutListAsync(config);
            if (result != null)
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
                StatusText = $"{result.CutCount} Cuts generiert ({result.TotalDuration:F1}s)";
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("timeline-refresh"));
            }
            else
            {
                StatusText = "Cut-Liste generieren fehlgeschlagen";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Cut-Liste generieren fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsGenerating = false;
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
        _isShuttingDown = false; // project closed, but app is still running
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

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _isShuttingDown = true;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
        _loadGate.Dispose();
    }
}

/// <summary>Video-Clip mit Auswahl-Checkbox für den Director.</summary>
public class SelectableVideoClip : ObservableObject
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public double DurationSeconds { get; set; }
    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");

    private bool _isSelected;
    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }
}
