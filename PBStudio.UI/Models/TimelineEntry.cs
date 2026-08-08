using System.Collections.ObjectModel;
using System.Text.Json;
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

    /// <summary>Plan Phase 5: Brain-Final-Score 0..1 (rot..grün Confidence-Balken).</summary>
    [ObservableProperty] private double _brainConfidence;

    /// <summary>Optionaler DB-Cut-ID (gesetzt wenn use_brain=true persistiert hat).</summary>
    [ObservableProperty] private int _cutId;
    [ObservableProperty] private double _featureConfidence;
    [ObservableProperty] private string _semanticStatus = "unavailable";
    [ObservableProperty] private string? _semanticReason;
    [ObservableProperty] private Dictionary<string, JsonElement>? _triggerProvenance;
    [ObservableProperty] private Dictionary<string, JsonElement>? _brainAxisStatus;
    [ObservableProperty] private Dictionary<string, JsonElement>? _metadata;

    /// <summary>R-Brain-09: lazy-geladener Tooltip-Text fuer den Confidence-Balken.
    /// null = noch nicht geladen, "" = wird geladen / Platzhalter, sonst formatierter Inhalt.</summary>
    [ObservableProperty] private string? _brainExplainTooltip;

    /// <summary>R-Brain-09: zeigt an, ob /brain/explain gerade laeuft (UI-Spinner).</summary>
    [ObservableProperty] private bool _isBrainExplainLoading;

    /// <summary>R-Brain-09: true sobald /brain/explain einmal erfolgreich oder per Fehler beantwortet wurde.
    /// Wird auf false zurueckgesetzt, wenn Feedback fuer diesen Cut eingeht (Cache-Invalidate).</summary>
    public bool IsBrainExplainLoaded { get; set; }

    /// <summary>N base64 JPEG data URLs from /video/thumbstrip/{id}. null until loaded.</summary>
    [ObservableProperty] private ObservableCollection<System.Windows.Media.ImageSource>? _thumbnailFrames;

    /// <summary>Downsampled mono peaks (0..1) from /video/clipwave/{id}. null until loaded.</summary>
    [ObservableProperty] private ObservableCollection<float>? _audioPeaks;

    /// <summary>Set to true after both /thumbstrip and /clipwave have returned (or failed).</summary>
    public bool IsAssetsLoaded { get; set; }

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
