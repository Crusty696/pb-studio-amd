using CommunityToolkit.Mvvm.ComponentModel;

namespace PBStudio.UI.Models;

/// <summary>Timeline-Eintrag für UI-Darstellung.</summary>
public partial class TimelineEntryModel : ObservableObject
{
    [ObservableProperty] private string _clipId = "";
    [ObservableProperty] private string _clipName = "";
    [ObservableProperty] private string _filePath = "";
    [ObservableProperty] private double _startTime;
    [ObservableProperty] private double _endTime;
    [ObservableProperty] private double _clipStart;
    [ObservableProperty] private string _triggerType = "";
    [ObservableProperty] private double _triggerStrength;

    /// <summary>Optionaler Segment-Typ aus dem Pacing-Engine (z.B. "intro", "verse", "chorus").</summary>
    [ObservableProperty] private string? _segmentType;

    public double Duration => EndTime - StartTime;
    public string TimeRangeText => $"{TimeSpan.FromSeconds(StartTime):mm\\:ss} - {TimeSpan.FromSeconds(EndTime):mm\\:ss}";

    // Visuelle Properties für die interaktive Timeline (Option C)
    public double GetX(double pixelsPerSecond) => StartTime * pixelsPerSecond;
    public double GetWidth(double pixelsPerSecond) => Duration * pixelsPerSecond;

    // Hilfsmethode für schnelles Refresh der UI bei Zoom-Änderung
    public void NotifyPositionChanged()
    {
        OnPropertyChanged(nameof(StartTime));
        OnPropertyChanged(nameof(EndTime));
        OnPropertyChanged(nameof(Duration));
        OnPropertyChanged(nameof(TimeRangeText));
    }
}
