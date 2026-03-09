using System.Collections.ObjectModel;
using System.IO;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Video-Bibliothek.</summary>
public partial class VideoLibraryViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private VideoClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isAnalyzingAll;
    [ObservableProperty] private double _analyzeAllProgress;
    [ObservableProperty] private bool _isLoadingThumbnails;

    public ObservableCollection<VideoClipModel> VideoClips { get; } = [];

    public VideoLibraryViewModel(IApiClient api)
    {
        _api = api;
        _ = LoadClipsAsync();
    }

    [RelayCommand]
    private async Task LoadClipsAsync()
    {
        var clips = await _api.GetVideoClipsAsync();
        if (clips == null) return;

        VideoClips.Clear();
        foreach (var c in clips)
        {
            VideoClips.Add(new VideoClipModel
            {
                Id = c.Id,
                Name = c.Name,
                Path = c.Path,
                DurationSeconds = c.DurationSeconds,
                Width = c.Width,
                Height = c.Height,
                Fps = c.Fps,
                Tags = c.Tags,
            });
        }
        StatusText = $"{VideoClips.Count} Clips geladen";

        await LoadAllThumbnailsAsync();
    }

    [RelayCommand]
    private async Task AnalyzeSelectedAsync()
    {
        if (SelectedClip == null) return;

        IsAnalyzing = true;
        StatusText = $"Analysiere: {SelectedClip.Name}...";

        var result = await _api.AnalyzeVideoAsync(SelectedClip.Id);
        if (result != null)
        {
            SelectedClip.IsAnalyzed = true;
            StatusText = $"Analyse fertig: {result.SceneCount} Scenes | Motion: {result.AvgMotion:F1}";
        }
        else
        {
            StatusText = "Analyse fehlgeschlagen";
        }

        IsAnalyzing = false;
    }

    [RelayCommand]
    private async Task AnalyzeAllAsync()
    {
        if (VideoClips.Count == 0) return;

        IsAnalyzingAll = true;
        IsAnalyzing = true;
        var total = VideoClips.Count;
        var done = 0;

        foreach (var clip in VideoClips.ToList())
        {
            if (clip.IsAnalyzed) { done++; continue; }

            StatusText = $"Analysiere {done + 1}/{total}: {clip.Name}...";
            AnalyzeAllProgress = (double)done / total * 100;

            var result = await _api.AnalyzeVideoAsync(clip.Id);
            if (result != null)
            {
                clip.IsAnalyzed = true;
            }
            done++;
        }

        AnalyzeAllProgress = 100;
        StatusText = $"Alle {total} Clips analysiert";
        IsAnalyzingAll = false;
        IsAnalyzing = false;
    }

    private async Task LoadAllThumbnailsAsync()
    {
        IsLoadingThumbnails = true;
        foreach (var clip in VideoClips.ToList())
        {
            var bytes = await _api.GetThumbnailAsync(clip.Id);
            if (bytes != null && bytes.Length > 0)
            {
                clip.Thumbnail = BytesToBitmapImage(bytes);
                var idx = VideoClips.IndexOf(clip);
                if (idx >= 0)
                {
                    VideoClips.RemoveAt(idx);
                    VideoClips.Insert(idx, clip);
                }
            }
        }
        IsLoadingThumbnails = false;
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
