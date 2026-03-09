using System.Windows.Media.Imaging;

namespace PBStudio.UI.Models;

/// <summary>Video-Clip Model für die UI-Darstellung.</summary>
public class VideoClipModel
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
    public BitmapImage? Thumbnail { get; set; }
    public bool IsAnalyzed { get; set; }
    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
    public string ResolutionText => $"{Width}x{Height}";
}
