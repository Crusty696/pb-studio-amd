namespace PBStudio.UI.Models;

/// <summary>
/// Modell für einen Song-Abschnitt (z.B. Chorus, Verse).
/// </summary>
public class SongSegmentModel
{
    public double StartTime { get; set; }
    public double EndTime { get; set; }
    public string Label { get; set; } = "";
    public double Confidence { get; set; }
    public double EnergyScore { get; set; }

    public double Duration => EndTime - StartTime;
}
