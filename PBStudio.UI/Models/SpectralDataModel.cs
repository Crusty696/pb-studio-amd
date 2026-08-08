using System.Collections.Generic;

namespace PBStudio.UI.Models;

/// <summary>
/// UI-Modell für Spektral-Analyse-Daten. Transportfelder stammen ausschließlich
/// aus dem durch OpenAPI generierten <see cref="Generated.SpectralData"/>.
/// </summary>
public class SpectralDataModel
{
    public int ClipId { get; set; }
    public List<double> Times { get; set; } = new();
    public Dictionary<string, List<double>> Bands { get; set; } = new();
    public List<double> Centroids { get; set; } = new();
    public Dictionary<string, List<double>> FrequencyRanges { get; set; } = new();
    public Dictionary<string, double> BandMeans { get; set; } = new();
    public Dictionary<string, double> BandVariances { get; set; } = new();
    public List<object> Events { get; set; } = new();

    public static SpectralDataModel FromTransport(Generated.SpectralData value)
    {
        ArgumentNullException.ThrowIfNull(value);

        return new SpectralDataModel
        {
            ClipId = value.Clip_id,
            Times = value.Times?.ToList() ?? new List<double>(),
            Bands = value.Bands?.ToDictionary(
                pair => pair.Key,
                pair => pair.Value.ToList()) ?? new Dictionary<string, List<double>>(),
            Centroids = value.Centroids?.ToList() ?? new List<double>(),
            FrequencyRanges = value.Frequency_ranges?.ToDictionary(
                pair => pair.Key,
                pair => pair.Value.ToList()) ?? new Dictionary<string, List<double>>(),
            BandMeans = value.Band_means is null
                ? new Dictionary<string, double>()
                : new Dictionary<string, double>(value.Band_means),
            BandVariances = value.Band_variances is null
                ? new Dictionary<string, double>()
                : new Dictionary<string, double>(value.Band_variances),
            Events = value.Events?.ToList() ?? new List<object>(),
        };
    }
}
