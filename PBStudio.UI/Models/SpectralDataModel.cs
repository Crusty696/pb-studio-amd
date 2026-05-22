using System.Collections.Generic;

namespace PBStudio.UI.Models;

/// <summary>
/// Modell für Spektral-Analyse-Daten.
/// </summary>
public class SpectralDataModel
{
    public int ClipId { get; set; }
    public List<double> Times { get; set; } = new();
    public Dictionary<string, List<double>> Bands { get; set; } = new();
    public List<double> Centroids { get; set; } = new();
    public Dictionary<string, List<double>> FrequencyRanges { get; set; } = new();
}
