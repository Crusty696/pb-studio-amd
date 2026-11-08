using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

public partial class ApiClient
{
    // --- Health ---

    public async Task<HealthStatus?> GetHealthAsync()
    {
        try
        {
            return await _http.GetFromJsonAsync<HealthStatus>("/health", JsonOptions).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Health-Check fehlgeschlagen");
            return null;
        }
    }

    public async Task<GpuStatus?> GetGpuStatusAsync()
        => await GetAsync<GpuStatus>("/gpu/status").ConfigureAwait(false);

    public Task<GpuCleanupResponse?> CleanupGpuAsync(CancellationToken ct = default)
        => PostAsync<GpuCleanupResponse>("/gpu/cleanup", null, ct);

    #region VRAM Telemetry
    // Kompatibilitätsmethode für die bestehende Multi-Modell-UI-Shape.
    // Die shape-spezifischen Methoden darunter bilden den Transportvertrag ab.
    public async Task<VramHealthResponse?> GetVramTelemetryAsync(
        string? modelId = null,
        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(modelId))
            return await GetVramTelemetrySnapshotAsync(ct).ConfigureAwait(false);

        var single = await GetVramModelTelemetryAsync(modelId, ct).ConfigureAwait(false);
        return single?.ToMultiModelSnapshot();
    }

    public Task<VramHealthResponse?> GetVramTelemetrySnapshotAsync(CancellationToken ct = default)
        => GetAsync<VramHealthResponse>("/health/vram", ct);

    public Task<VramHealthSingleResponse?> GetVramModelTelemetryAsync(
        string modelId,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(modelId);
        return GetAsync<VramHealthSingleResponse>(
            $"/health/vram?model_id={Uri.EscapeDataString(modelId)}",
            ct);
    }

    public async Task<VramLimitResponse?> UpdateVramLimitAsync(int limitMb, CancellationToken ct = default)
    {
        return await PostAsync<VramLimitResponse>("/health/vram/limit", new VramLimitRequest(limitMb)).ConfigureAwait(false);
    }

    #endregion
}
