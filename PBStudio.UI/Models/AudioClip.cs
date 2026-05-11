using CommunityToolkit.Mvvm.ComponentModel;

namespace PBStudio.UI.Models;

/// <summary>Audio-Clip Model für die UI-Darstellung.</summary>
public partial class AudioClipModel : ObservableObject
{
    [ObservableProperty] private int _id;
    [ObservableProperty] private string _name = "";
    [ObservableProperty] private string _path = "";
    [ObservableProperty] private double _durationSeconds;
    [ObservableProperty] private int _sampleRate = 44100;
    [ObservableProperty] private int _channels = 2;
    [ObservableProperty] private string _format = "mp3";
    [ObservableProperty] private double _bpm;
    [ObservableProperty] private string _key = "";
    [ObservableProperty] private int _beatCount;
    [ObservableProperty] private bool _isAnalyzed;
    // L-N2: Content-Hash vom Backend; HasCacheHash treibt CACHED-Badge im View.
    [ObservableProperty] private string? _audioHash;

    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public bool HasCacheHash => !string.IsNullOrWhiteSpace(AudioHash);

    partial void OnDurationSecondsChanged(double value) => OnPropertyChanged(nameof(DurationText));
    partial void OnAudioHashChanged(string? value) => OnPropertyChanged(nameof(HasCacheHash));
}
