using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Ollama Model Manager — Auto-Selection-Empfehlung (GET /models/recommendations).
// Spiegelt backend/routers/models_router.py::RecommendationResponse.
// Wird vom ModelManagerViewModel angezeigt und vom SettingsViewModel als
// Vorschau-Text genutzt ("Aktuell wuerde Auto-Selection X waehlen").
// =====================================================================

/// <summary>Antwort von <c>GET /models/recommendations</c>.</summary>
public record ModelRecommendationResponse(
    string Task,
    string Mode,
    string? Model,
    string Reason,
    List<string> PreferenceList,
    string? Override,
    List<string> Installed,
    string? Provider = null,
    List<string>? RequiredCapabilities = null,
    List<string>? VerifiedCapabilities = null,
    string? SelectionSource = null,
    string? SelectedAt = null);
