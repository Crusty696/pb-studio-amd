using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Audio-Bibliothek.</summary>
public partial class AudioLibraryViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private AudioClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isSeparating;
    [ObservableProperty] private double _analysisProgress;
    [ObservableProperty] private double _bpm;
    [ObservableProperty] private int _beatCount;
    [ObservableProperty] private string _key = "";
    [ObservableProperty] private double _durationSeconds;

    public ObservableCollection<AudioClipModel> AudioClips { get; } = [];

    public AudioLibraryViewModel(IApiClient api)
    {
        _api = api;
        _ = LoadAudioClipsAsync();
    }

    partial void OnSelectedClipChanged(AudioClipModel? value)
    {
        if (value == null) return;
        Bpm = value.Bpm;
        BeatCount = value.BeatCount;
        Key = value.Key;
        DurationSeconds = value.DurationSeconds;
    }

    [RelayCommand]
    private async Task LoadAudioClipsAsync()
    {
        var clips = await _api.GetAudioClipsAsync();
        if (clips != null)
        {
            AudioClips.Clear();
            foreach (var clipInfo in clips)
            {
                AudioClips.Add(new AudioClipModel
                {
                    Id = clipInfo.Id,
                    Name = clipInfo.Name,
                    Path = clipInfo.Path,
                    DurationSeconds = clipInfo.DurationSeconds,
                    SampleRate = clipInfo.SampleRate,
                    Channels = clipInfo.Channels,
                    Format = clipInfo.Format,
                });
            }
            StatusText = $"{clips.Count} Audio-Clips geladen";
        }
        else
        {
            StatusText = "Audio-Clips laden fehlgeschlagen";
        }
    }

    [RelayCommand]
    private void SelectAll()
    {
        // ListBox doesn't support multi-select binding easily, so just select first
        if (AudioClips.Count > 0)
            SelectedClip = AudioClips[0];
        StatusText = $"{AudioClips.Count} Clips verfügbar";
    }

    [RelayCommand]
    private void DeselectAll()
    {
        SelectedClip = null;
    }

    [RelayCommand]
    private async Task AnalyzeAllAsync()
    {
        if (AudioClips.Count == 0) return;

        IsAnalyzing = true;
        var total = AudioClips.Count;
        var done = 0;

        foreach (var clip in AudioClips.ToList())
        {
            if (clip.IsAnalyzed) { done++; continue; }

            StatusText = $"Analysiere {done + 1}/{total}: {clip.Name}...";
            AnalysisProgress = (double)done / total * 100;

            var result = await _api.AnalyzeAudioAsync(clip.Id);
            if (result != null)
            {
                clip.Bpm = result.Bpm;
                clip.BeatCount = result.BeatCount;
                clip.Key = result.Key ?? "";
                clip.IsAnalyzed = true;
            }
            done++;
        }

        AnalysisProgress = 100;
        StatusText = $"Alle {total} Clips analysiert";
        IsAnalyzing = false;

        // Aktualisiere Detail-Anzeige
        if (SelectedClip != null) OnSelectedClipChanged(SelectedClip);
    }

    [RelayCommand]
    private async Task AnalyzeSelectedAsync()
    {
        if (SelectedClip == null) return;

        IsAnalyzing = true;
        StatusText = $"Analysiere: {SelectedClip.Name}...";

        var result = await _api.AnalyzeAudioAsync(SelectedClip.Id);
        if (result != null)
        {
            SelectedClip.Bpm = result.Bpm;
            SelectedClip.BeatCount = result.BeatCount;
            SelectedClip.Key = result.Key ?? "";
            SelectedClip.IsAnalyzed = true;
            Bpm = result.Bpm;
            BeatCount = result.BeatCount;
            Key = result.Key ?? "";
            StatusText = $"Analyse fertig: {result.Bpm:F1} BPM | {result.BeatCount} Beats | Tonart: {result.Key ?? "–"}";
        }
        else
        {
            StatusText = "Analyse fehlgeschlagen";
        }

        IsAnalyzing = false;
    }

    [RelayCommand]
    private async Task SeparateStemsAsync()
    {
        if (SelectedClip == null) return;

        IsSeparating = true;
        StatusText = $"Stem-Separation: {SelectedClip.Name}...";

        var result = await _api.SeparateStemsAsync(SelectedClip.Id);
        StatusText = result != null
            ? $"Stems getrennt: {result.ModelUsed}"
            : "Stem-Separation fehlgeschlagen";

        IsSeparating = false;
    }
}
