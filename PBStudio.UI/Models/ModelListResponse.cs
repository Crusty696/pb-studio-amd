using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Providerübergreifendes Live-Inventar (GET /models/list).
// Spiegelt backend/routers/models_router.py::ModelListResponse 1:1.
// snake_case Mapping greift via globaler JsonNamingPolicy in ApiClient.
// =====================================================================

/// <summary>Antwort von <c>GET /models/list</c>.</summary>
public record ModelListResponse(
    bool OllamaAvailable,
    string BaseUrl,
    List<ModelListEntry> Models,
    string? Error = null,
    bool LmstudioAvailable = false,
    List<ProviderStatusEntry>? Providers = null,
    int InventoryGeneration = 0,
    string VerifiedAt = "");

public record ProviderStatusEntry(
    string Provider,
    string Status,
    string BaseUrl,
    string VerifiedAt,
    string StatusReason = "",
    string CatalogStatus = "not_verified",
    string? DiscoverUrl = null);

/// <summary>Providergebundener, live verifizierter Modelleintrag.</summary>
public record ModelListEntry(
    string Name,
    long SizeBytes = 0,
    double SizeMb = 0.0,
    double SizeGb = 0.0,
    string ModifiedAt = "",
    string? Family = null,
    string? ParameterSize = null,
    string? QuantizationLevel = null,
    string Description = "",
    bool IsActive = false,
    List<string>? ActiveTasks = null,
    bool Vision = false,
    string Provider = "lmstudio",
    bool Installed = true,
    bool Loaded = false,
    bool Downloadable = false,
    bool Usable = false,
    List<string>? Capabilities = null,
    List<string>? InventorySources = null,
    string VerifiedAt = "",
    string StatusReason = "");
