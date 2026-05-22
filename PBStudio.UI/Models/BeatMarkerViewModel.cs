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
    /// True, wenn es sich um den Beginn eines Taktes (Downbeat / 1st Beat in Bar) handelt.
    /// In einem standardmäßigen 4/4-Takt ist dies jeder 4. Beat (Index 0, 4, 8, ...).
    /// </summary>
    public bool IsDownbeat => Index % 4 == 0;

    /// <summary>
    /// Taktnummer (z. B. "1", "2", "3" ...) für Downbeats.
    /// </summary>
    public string Label => IsDownbeat ? $"{(Index / 4) + 1}" : string.Empty;
}
