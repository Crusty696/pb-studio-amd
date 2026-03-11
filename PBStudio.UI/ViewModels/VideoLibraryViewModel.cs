using System.Collections.ObjectModel;
using System.IO;
using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Video-Bibliothek.</summary>
public partial class VideoLibraryViewModel : ObservableObject
{
    private readonly IApiClient _api;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private readonly Dictionary<int, BitmapImage> _thumbnailCache = [];
    private int _loadVersion;

    [ObservableProperty] private VideoClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isAnalyzingAll;
    [ObservableProperty] private double _analyzeAllProgress;
    [ObservableProperty] private bool _isLoadingThumbnails;
    [ObservableProperty] private bool _isLoadingClips;

    public ObservableCollection<VideoClipModel> VideoClips { get; } = [];

    public VideoLibraryViewModel(IApiClient api)
    {
        _api = api;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "backend-ready" or "video-imported" or "video-library-refresh" or "media-library-refresh" or "project-opened")
                _ = LoadClipsAsync();
            else if (message.Value is "project-closed")
                ClearClips();
        });
    }

    [RelayCommand]
    private async Task LoadClipsAsync()
    {
        var version = Interlocked.Increment(ref _loadVersion);
        await _loadGate.WaitAsync();
        try
        {
            IsLoadingClips = true;
            StatusText = "Video-Clips werden geladen...";

            var clips = await _api.GetVideoClipsAsync();
            if (clips == null)
            {
                StatusText = "Video-Clips laden fehlgeschlagen";
                return;
            }

            VideoClips.Clear();
            foreach (var c in clips)
            {
                var clip = new VideoClipModel
                {
                    Id = c.Id,
                    Name = c.Name,
                    Path = c.Path,
                    DurationSeconds = c.DurationSeconds,
                    Width = c.Width,
                    Height = c.Height,
                    Fps = c.Fps,
                    Tags = c.Tags,
                };

                if (_thumbnailCache.TryGetValue(c.Id, out var cachedThumb))
                    clip.Thumbnail = cachedThumb;

                VideoClips.Add(clip);
            }
            StatusText = $"{VideoClips.Count} Clips geladen";

            await LoadAllThumbnailsAsync(version);
        }
        finally
        {
            IsLoadingClips = false;
            _loadGate.Release();
        }
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

    private async Task LoadAllThumbnailsAsync(int version)
    {
        IsLoadingThumbnails = true;
        try
        {
            foreach (var clip in VideoClips.ToList())
            {
                if (version != _loadVersion)
                    return;

                if (_thumbnailCache.TryGetValue(clip.Id, out var cached))
                {
                    clip.Thumbnail = cached;
                    continue;
                }

                var bytes = await _api.GetThumbnailAsync(clip.Id);
                if (bytes != null && bytes.Length > 0)
                {
                    var bmp = BytesToBitmapImage(bytes);
                    _thumbnailCache[clip.Id] = bmp;
                    clip.Thumbnail = bmp;

                    var idx = VideoClips.IndexOf(clip);
                    if (idx >= 0)
                    {
                        VideoClips.RemoveAt(idx);
                        VideoClips.Insert(idx, clip);
                    }
                }
            }
        }
        finally
        {
            IsLoadingThumbnails = false;
        }
    }

    private void ClearClips()
    {
        VideoClips.Clear();
        SelectedClip = null;
        StatusText = "Kein Projekt geöffnet";
        IsLoadingClips = false;
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
