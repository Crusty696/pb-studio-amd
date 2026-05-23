namespace PBStudio.UI.Models;

/// <summary>Antwort von <c>POST /models/test</c>.</summary>
public record ModelTestResponse(
    bool Success,
    double LatencyMs = 0.0,
    string Response = "",
    string? Error = null);
