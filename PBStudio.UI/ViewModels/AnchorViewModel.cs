using System.Collections.ObjectModel;
using System.Linq;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Anchor-Bearbeitung (Beat-Marker + Video-Zuordnung).</summary>
public partial class AnchorViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private const double WaveformWidth = 720.0;
    private const double WaveformHeight = 180.0;
    private const int MaxWaveformBars = 180;

    [ObservableProperty] private string _statusText = "Anchors werden hier definiert";
    [ObservableProperty] private double _currentPosition;
    [ObservableProperty] private AnchorPoint? _selectedAnchor;
    [ObservableProperty] private AudioClipModel? _selectedAudioClip;
    [ObservableProperty] private bool _isLoadingWaveform;
    [ObservableProperty] private double _timelineDuration = 300;
    [ObservableProperty] private double _positionMarkerX;

    public ObservableCollection<AnchorPoint> Anchors { get; } = [];
    public ObservableCollection<AudioClipModel> AvailableAudioClips { get; } = [];
    public ObservableCollection<WaveformBar> WaveformBars { get; } = [];
    public ObservableCollection<BeatMarker> BeatMarkers { get; } = [];

    public AnchorViewModel(IApiClient api)
    {
        _api = api;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "backend-ready" or "audio-library-refresh" or "audio-imported" or "media-library-refresh")
                _ = LoadAudioSourcesAsync();
        });
    }

    partial void OnSelectedAudioClipChanged(AudioClipModel? value)
    {
        TimelineDuration = value?.DurationSeconds > 0 ? value.DurationSeconds : 300;
        CurrentPosition = 0;
        _ = LoadWaveformAndBeatsAsync();
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

    [RelayCommand]
    private async Task LoadAudioSourcesAsync()
    {
        var clips = await _api.GetAudioClipsAsync();
        if (clips == null)
        {
            StatusText = "Audio-Quellen laden fehlgeschlagen";
            return;
        }

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

        if (SelectedAudioClip == null && AvailableAudioClips.Count > 0)
            SelectedAudioClip = AvailableAudioClips.FirstOrDefault(c => c.IsAnalyzed) ?? AvailableAudioClips[0];

        StatusText = $"{AvailableAudioClips.Count} Audio-Quellen verfügbar";
    }

    [RelayCommand]
    private async Task ReloadWaveformAsync()
    {
        await LoadWaveformAndBeatsAsync();
    }

    [RelayCommand]
    private void AddAnchor()
    {
        Anchors.Add(new AnchorPoint
        {
            Time = CurrentPosition,
            Label = $"Anchor {Anchors.Count + 1}",
        });
        StatusText = $"Anchor bei {CurrentPosition:F2}s hinzugefügt";
    }

    [RelayCommand]
    private void RemoveAnchor(AnchorPoint? anchor)
    {
        if (anchor != null)
        {
            Anchors.Remove(anchor);
            StatusText = "Anchor entfernt";
        }
    }

    private async Task LoadWaveformAndBeatsAsync()
    {
        WaveformBars.Clear();
        BeatMarkers.Clear();

        if (SelectedAudioClip == null)
        {
            StatusText = "Keine Audio-Quelle ausgewählt";
            return;
        }

        IsLoadingWaveform = true;
        StatusText = $"Lade Waveform: {SelectedAudioClip.Name}...";

        try
        {
            var waveform = await _api.GetWaveformAsync(SelectedAudioClip.Id, bands: 3);
            var beats = await _api.GetBeatsAsync(SelectedAudioClip.Id);

            TimelineDuration = waveform?.DurationSeconds > 0
                ? waveform.DurationSeconds
                : SelectedAudioClip.DurationSeconds > 0
                    ? SelectedAudioClip.DurationSeconds
                    : 300;

            BuildWaveformBars(waveform);
            BuildBeatMarkers(beats, TimelineDuration);

            StatusText = $"Waveform geladen: {WaveformBars.Count} Bars | {BeatMarkers.Count} Beats";
        }
        catch (Exception ex)
        {
            StatusText = $"Waveform/Beats laden fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsLoadingWaveform = false;
        }
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
