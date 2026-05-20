// S-H1b (Audit V2) Task 7 — PARTIAL MIGRATION:
//
// BrainAxisContribution -> aliased to NSwag-generated (clean types).
// BrainExplainResponse  -> KEPT MANUAL.
//
// Reason: backend Pydantic models use Optional[str] for `narrative` and
// `segment_type`. Pydantic emits these as OpenAPI 3.1 `anyOf: [string, null]`,
// which NSwag 14 cannot resolve to `string?` — it generates opaque empty
// classes `Narrative` / `Segment_type` (only AdditionalProperties). Switching
// the BrainExplainResponse to the NSwag-generated type would:
//   1. fail at compile time (tooltip code does `e.Narrative.Trim()` — Narrative
//      is now an object, not a string),
//   2. fail at runtime (System.Text.Json cannot deserialize a JSON string into
//      an object with no constructor binding).
// Fix lives upstream (FastAPI schema customisation or NSwag custom mapping);
// until then this hybrid keeps BrainExplain working with the canonical
// BrainAxisContribution shape.
global using BrainAxisContribution = PBStudio.UI.Generated.BrainAxisContribution;

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
