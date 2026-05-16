namespace PBStudio.UI.Models;

// =====================================================================
// Ollama Pull-Progress — geyieldet aus IApiClient.PullModelAsync.
// Spiegelt die JSON-Lines, die Ollama via /api/pull streamt.
// Backend leitet sie 1:1 als SSE event=pull_progress weiter.
//
// Felder sind alle optional, da Ollama je nach Phase nur Teilmengen sendet:
//   * Anfang:    { "status": "pulling manifest" }
//   * Layer:     { "status": "pulling <digest>", "completed": 12345, "total": 67890, "digest": "sha256:..." }
//   * Verify:    { "status": "verifying sha256 digest" }
//   * Ende:      { "status": "success" }
//   * Fehler:    Error wird gesetzt (vom Backend-Fallback bei OllamaError)
// =====================================================================

/// <summary>Ein einzelnes Progress-Event waehrend eines Ollama-Pulls.</summary>
public record PullProgressEvent(
    string? Status = null,
    long? Completed = null,
    long? Total = null,
    string? Digest = null,
    string? Error = null)
{
    /// <summary>Prozentuale Vollendung wenn <c>completed</c> und <c>total</c> vorhanden.</summary>
    public double? Percent =>
        Total.HasValue && Total.Value > 0 && Completed.HasValue
            ? Completed.Value * 100.0 / Total.Value
            : null;

    /// <summary>True falls dieses Event den Pull als beendet markiert (success oder error).</summary>
    public bool IsTerminal =>
        !string.IsNullOrEmpty(Error)
        || (Status is not null && Status.Equals("success", System.StringComparison.OrdinalIgnoreCase));
}
