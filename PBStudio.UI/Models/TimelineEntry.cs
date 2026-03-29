namespace PBStudio.UI.Models;

/// <summary>Timeline-Eintrag für UI-Darstellung.</summary>
public class TimelineEntryModel
{
    public string ClipId { get; set; } = "";
    public string ClipName { get; set; } = "";
    public string FilePath { get; set; } = "";
    public double StartTime { get; set; }
    public double EndTime { get; set; }
    public double ClipStart { get; set; }
    public string TriggerType { get; set; } = "";
    public double TriggerStrength { get; set; }
    /// <summary>Optionaler Segment-Typ aus dem Pacing-Engine (z.B. "intro", "verse", "chorus").
    /// R14: Feld aus Python TimelineEntrySchema ergänzt — verhindert Silent Data Loss beim Mapping.</summary>
    public string? SegmentType { get; set; }
    public double Duration => EndTime - StartTime;
    public string TimeRangeText => $"{TimeSpan.FromSeconds(StartTime):mm\\:ss} - {TimeSpan.FromSeconds(EndTime):mm\\:ss}";
}
