namespace PBStudio.UI.Models;

/// <summary>
/// Nachvollziehbarkeits-Beleg der Modellauswahl.
///
/// Audit 2026-08-05 (H-2): Der Receipt wurde backendseitig vollstaendig gebaut,
/// aber ausschliesslich per <c>logger.info</c> ausgegeben — nie in einer
/// Response, nie persistiert, nie angezeigt. Die Frage "welches Modell hat diese
/// Antwort geliefert, mit welchen Capabilities, aus welcher Quelle" liess sich
/// damit nur ueber <c>backend.log</c> beantworten. IRON RULE 10 verlangt genau
/// diese Nachvollziehbarkeit.
/// </summary>
public record ModelSelectionReceipt(
    string Provider = "",
    string ModelId = "",
    string Task = "",
    string Mode = "",
    List<string>? RequiredCapabilities = null,
    List<string>? VerifiedCapabilities = null,
    string Source = "",
    string Reason = "",
    string SelectedAt = "");

/// <summary>Antwort von <c>POST /models/test</c>.</summary>
public record ModelTestResponse(
    bool Success,
    double LatencyMs = 0.0,
    string Response = "",
    string? Error = null,
    ModelSelectionReceipt? SelectionReceipt = null);
