// T5c (S-H1b Audit V2): manual stub records replaced by NSwag-generated DTOs.
// VramHistogramBar stays manual (UI-internal Bar-Rendering, not a backend DTO).
//
// Backend Pydantic schemas (backend/schemas/health_schemas.py) drive these:
//   VramHealthResponse, VramHealthSingleResponse, VramBudgetStats, VramModelEntry,
//   VramTelemetryMulti, VramTelemetrySummary, VramTelemetryEntry, VramDurationStats, VramPeakStats
// All in namespace PBStudio.UI.Generated. Snake-case-preserving properties via NSwag
// (e.g. Model_id, Duration_ms, Vram_peak_mb).
global using VramHealthResponse = PBStudio.UI.Generated.VramHealthResponse;
global using VramHealthSingleResponse = PBStudio.UI.Generated.VramHealthSingleResponse;
global using VramBudgetStats = PBStudio.UI.Generated.VramBudgetStats;
global using VramModelEntry = PBStudio.UI.Generated.VramModelEntry;
global using VramTelemetryMulti = PBStudio.UI.Generated.VramTelemetryMulti;
global using VramTelemetrySummary = PBStudio.UI.Generated.VramTelemetrySummary;
global using VramTelemetryEntry = PBStudio.UI.Generated.VramTelemetryEntry;
global using VramDurationStats = PBStudio.UI.Generated.VramDurationStats;
global using VramPeakStats = PBStudio.UI.Generated.VramPeakStats;
global using VramLimitRequest = PBStudio.UI.Generated.VramLimitRequest;
global using VramLimitResponse = PBStudio.UI.Generated.VramLimitResponse;

namespace PBStudio.UI.Models;

/// <summary>
/// Hält die bestehende Multi-Modell-UI-Shape kompatibel, ohne Einzelmodell-JSON
/// in den falschen Transporttyp zu deserialisieren.
/// </summary>
public static class VramTelemetryUiAdapter
{
    public static VramHealthResponse ToMultiModelSnapshot(
        this VramHealthSingleResponse response)
    {
        ArgumentNullException.ThrowIfNull(response);

        var entry = response.Telemetry;
        var models = new Dictionary<string, VramTelemetryEntry>
        {
            [entry.Model_id] = entry,
        };
        var summary = new VramTelemetrySummary(
            duration_buckets_ms: null,
            models_tracked: 1,
            observations: entry.Count ?? 0,
            vram_buckets_mb: null);

        return new VramHealthResponse(
            response.Budget,
            response.Status,
            new VramTelemetryMulti(models, summary));
    }
}
