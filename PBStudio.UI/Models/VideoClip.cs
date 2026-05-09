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

    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public string ResolutionText => $"{Width}x{Height}";
}
