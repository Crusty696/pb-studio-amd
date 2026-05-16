using System.Collections.Generic;

namespace PBStudio.UI.Models;

/// <summary>
/// Antwort fuer GET /brain/explain/{cut_id} (R-Brain-09).
/// Spiegelt backend/schemas/brain_schemas.py::BrainExplainResponse.
/// UX: Tooltip beim Hover ueber den Confidence-Balken in der Timeline.
/// </summary>
public record BrainExplainResponse(
    int CutId,
    string ClipId,
    double StartTime,
    double EndTime,
    string? SegmentType,
    double FinalScore,
    List<string> ContextKeys,
    List<BrainAxisContribution> TopAxes,
    List<BrainAxisContribution> BottomAxes,
    List<string> ColdStartAxes,
    string? Narrative = null
);

/// <summary>
/// Pro-Achse-Aufschluesselung: bridge_value (raw) * posterior (gelerntes Gewicht) = score.
/// Spiegelt backend/schemas/brain_schemas.py::BrainAxisContribution.
/// </summary>
public record BrainAxisContribution(
    string Axis,
    double BridgeValue,
    double Posterior,
    double Score,
    int NSamples
);
