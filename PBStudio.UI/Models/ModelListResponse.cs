using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Ollama Model Manager — installierte Modelle (GET /models/list).
// Spiegelt backend/routers/models_router.py::ModelListResponse 1:1.
// snake_case Mapping greift via globaler JsonNamingPolicy in ApiClient.
// =====================================================================

/// <summary>Antwort von <c>GET /models/list</c>.</summary>
public record ModelListResponse(
    bool OllamaAvailable,
    string BaseUrl,
    List<ModelListEntry> Models,
    string? Error = null);

/// <summary>Einzelnes installiertes Ollama-Modell (entspricht <c>/api/tags</c>).</summary>
public record ModelListEntry(
    string Name,
    long SizeBytes = 0,
    double SizeMb = 0.0,
    double SizeGb = 0.0,
    string ModifiedAt = "",
    string? Family = null,
    string? ParameterSize = null,
    string? QuantizationLevel = null);
