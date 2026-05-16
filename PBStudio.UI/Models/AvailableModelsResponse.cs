using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Ollama Model Manager — kuratierte Modell-Liste (GET /models/available).
// Spiegelt backend/routers/models_router.py::AvailableModelsResponse.
// Jede Entry traegt das ``installed``-Flag, das das Backend serverseitig
// gegen die echte /api/tags-Liste setzt.
// =====================================================================

/// <summary>Antwort von <c>GET /models/available</c>.</summary>
public record AvailableModelsResponse(
    bool OllamaAvailable,
    string BaseUrl,
    List<AvailableModelEntry> Available);

/// <summary>Ein kuratierter Eintrag: Default-Modelle, die PB Studio empfiehlt.</summary>
public record AvailableModelEntry(
    string Name,
    string Description,
    string SuggestedMode,
    double SizeEstimateGb,
    bool Vision,
    bool Installed);
