using System.Windows.Media.Imaging;
using CommunityToolkit.Mvvm.ComponentModel;

namespace PBStudio.UI.Models;

/// <summary>Video-Clip Model für die UI-Darstellung.</summary>
public partial class VideoClipModel : ObservableObject
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Path { get; set; } = "";
    public double DurationSeconds { get; set; }
    public int Width { get; set; } = 1920;
    public int Height { get; set; } = 1080;
    public double Fps { get; set; } = 30.0;
    public string Codec { get; set; } = "";
    public List<string> Tags { get; set; } = [];
    [ObservableProperty] private BitmapImage? _thumbnail;
    [ObservableProperty] private bool _isAnalyzed;
    [ObservableProperty] private string _analysisStatus = "unavailable";
    [ObservableProperty] private Dictionary<string, string>? _stageStatus;
    [ObservableProperty] private Dictionary<string, string>? _stageErrors;
    [ObservableProperty] private bool _isMarked;
    [ObservableProperty] private string? _tagSource;
    /// <summary>R15/C-03: Flag aus Python VideoClipInfo.thumbnail_available — gibt an, ob das
    /// Backend bereits ein Thumbnail für diesen Clip generiert hat.</summary>
    public bool ThumbnailAvailable { get; set; }

    // L-M4: Motion-Felder fuer Detail-Card. null = noch nicht analysiert / kein Motion-Block.
    [ObservableProperty] private double? _avgMotion;
    [ObservableProperty] private double? _peakMotion;
    [ObservableProperty] private string? _motionCategory;
    /// <summary>L-M4: UpperCase Convenience-Projektion der Motion-Kategorie fuer XAML-Bindings
    /// (vermeidet Bedarf nach UpperCaseConverter). Liefert null wenn MotionCategory null ist.</summary>
    public string? MotionCategoryDisplay => MotionCategory?.ToUpperInvariant();

    partial void OnMotionCategoryChanged(string? value)
    {
        OnPropertyChanged(nameof(MotionCategoryDisplay));
    }

    // L-N3: SHA256 media_hash aus VideoClipInfo.VideoHash. Wenn nicht null/whitespace
    // wurde der Clip beim Import gehasht und ein Embedding kann aus Cache wiederverwendet
    // werden. HasCacheHash treibt den "CACHED"-Badge im VideoLibraryView-Card-Template.
    [ObservableProperty] private string? _videoHash;
    public bool HasCacheHash => !string.IsNullOrWhiteSpace(VideoHash);

    partial void OnVideoHashChanged(string? value)
    {
        OnPropertyChanged(nameof(HasCacheHash));
    }

    [ObservableProperty] private bool _hasEmbedding;
    [ObservableProperty] private int? _embeddingDim;
    [ObservableProperty] private int? _embeddingSamples;

    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public string ResolutionText => $"{Width}x{Height}";
    public string AnalysisStatusText => AnalysisStatus switch
    {
        "completed" => "ANALYSIERT",
        "partial" => "TEILANALYSE",
        "failed" => "ANALYSEFEHLER",
        "interrupted" => "UNTERBROCHEN",
        _ => "NICHT ANALYSIERT",
    };
    public string AnalysisDetail
    {
        get
        {
            if (StageErrors is { Count: > 0 })
                return string.Join(" | ", StageErrors.Select(item => $"{item.Key}: {item.Value}"));
            if (StageStatus is { Count: > 0 })
            {
                var open = StageStatus
                    .Where(item => item.Value is "failed" or "partial" or "interrupted")
                    .Select(item => item.Key)
                    .ToList();
                if (open.Count > 0)
                    return $"Fehlende Stufen: {string.Join(", ", open)}";
            }
            return AnalysisStatusText;
        }
    }

    partial void OnAnalysisStatusChanged(string value)
    {
        OnPropertyChanged(nameof(AnalysisStatusText));
        OnPropertyChanged(nameof(AnalysisDetail));
    }

    partial void OnStageStatusChanged(Dictionary<string, string>? value)
        => OnPropertyChanged(nameof(AnalysisDetail));

    partial void OnStageErrorsChanged(Dictionary<string, string>? value)
        => OnPropertyChanged(nameof(AnalysisDetail));
}
