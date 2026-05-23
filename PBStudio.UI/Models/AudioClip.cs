using System.Collections.Generic;
using System.Linq;
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
    // L-N4: Stem-Separation Outputs vom Backend (vocals/drums/bass/other -> path).
    // HasStems treibt STEMS-Badge + Open-Folder-Button im View.
    [ObservableProperty] private Dictionary<string, string>? _stemsPaths;

    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public bool HasCacheHash => !string.IsNullOrWhiteSpace(AudioHash);
    public bool HasStems => StemsPaths != null && StemsPaths.Count > 0;
    public string? StemsFolderPath
    {
        get
        {
            if (!HasStems) return null;
            var rawPath = StemsPaths!.Values.First();
            if (string.IsNullOrEmpty(rawPath)) return null;
            var normalized = rawPath.Replace('/', '\\');
            return System.IO.Path.GetDirectoryName(normalized);
        }
    }

    partial void OnDurationSecondsChanged(double value) => OnPropertyChanged(nameof(DurationText));
    partial void OnAudioHashChanged(string? value) => OnPropertyChanged(nameof(HasCacheHash));
    partial void OnStemsPathsChanged(Dictionary<string, string>? value)
    {
        OnPropertyChanged(nameof(HasStems));
        OnPropertyChanged(nameof(StemsFolderPath));
    }
}
