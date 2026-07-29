namespace PBStudio.UI.Models;

/// <summary>
/// Modell für die visuelle Darstellung eines Beats auf der Timeline im DJ-Stil (Rekordbox/Traktor).
/// </summary>
public class BeatMarkerViewModel
{
    /// <summary>
    /// Position in Sekunden auf der globalen Timeline.
    /// </summary>
    public double Time { get; set; }

    /// <summary>
    /// Fortlaufender Index des Beats in diesem Track.
    /// </summary>
    public int Index { get; set; }

    /// <summary>
    /// Stärke des Beats (BPM Energy).
    /// </summary>
    public double Strength { get; set; }

    /// <summary>
    /// Typ des Beats ("downbeat" oder "beat").
    /// </summary>
    public string BeatType { get; set; } = "";

    /// <summary>
    /// True nur bei einem vom Backend als gemessen gelieferten Downbeat.
    /// </summary>
    public bool IsDownbeat =>
        BeatType.Equals("downbeat", StringComparison.OrdinalIgnoreCase) ||
        BeatType.Equals("bar", StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// Marker für einen gemessenen Downbeat; keine synthetische Taktnummer.
    /// </summary>
    public string Label => IsDownbeat ? "D" : string.Empty;
}
