using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Live verifizierte Downloadzustände und allgemeine Discover-Aktionen.
// Spiegelt backend/routers/models_router.py::AvailableModelsResponse.
// Keine statische Modellkarte gilt als herunterladbar.
// =====================================================================

/// <summary>Antwort von <c>GET /models/available</c>.</summary>
public record AvailableModelsResponse(
    bool OllamaAvailable,
    string BaseUrl,
    List<AvailableModelEntry> Available,
    bool LmstudioAvailable = false,
    List<DiscoverAction>? DiscoverActions = null,
    int InventoryGeneration = 0,
    string VerifiedAt = "");

public record DiscoverAction(
    string Provider,
    string Label,
    string Url,
    string CatalogStatus);

/// <summary>Ein live gegen ein Provider-Manifest verifizierter Eintrag.</summary>
public record AvailableModelEntry(
    string Name,
    string Description,
    string SuggestedMode,
    double SizeEstimateGb,
    bool Vision,
    bool Installed,
    string Provider = "lmstudio",
    bool Loaded = false,
    bool Downloadable = false,
    bool Usable = false,
    List<string>? Capabilities = null,
    string VerifiedAt = "",
    string StatusReason = "");
