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
    // --- Pacing ---

    public async Task<CutListResponse?> GenerateCutListAsync(PacingConfig config, CancellationToken cancellationToken = default)
        => await PostAsync<CutListResponse>("/pacing/generate", config, cancellationToken).ConfigureAwait(false);

    public async Task<TimelineResponse?> GetTimelineAsync(CancellationToken cancellationToken = default)
        => await GetAsync<TimelineResponse>("/pacing/timeline", cancellationToken).ConfigureAwait(false);

    public async Task<StatusResponse?> UpdateTimelineAsync(
        List<TimelineEntryModel> entries,
        CancellationToken cancellationToken = default)
    {
        var payload = new
        {
            entries = entries.Select(e => new TimelineEntry(
                e.ClipId,
                e.ClipName,
                e.FilePath,
                e.StartTime,
                e.EndTime,
                e.ClipStart,
                e.TriggerType,
                e.TriggerStrength,
                e.SegmentType,
                e.BrainConfidence,
                e.CutId,
                e.FeatureConfidence,
                e.SemanticStatus,
                e.SemanticReason,
                e.TriggerProvenance,
                e.BrainAxisStatus,
                e.Metadata
            )).ToList()
        };
        return await PostAsync<StatusResponse>(
            "/pacing/timeline",
            payload,
            cancellationToken).ConfigureAwait(false);
    }

    public async Task<PacingPreviewResponse?> GenerateTimelinePreviewAsync(double startSec, double duration, CancellationToken ct = default)
        => await PostAsync<PacingPreviewResponse>("/pacing/preview", new
        {
            start_sec = startSec,
            duration,
        }, ct).ConfigureAwait(false);

    // --- Render ---

    public async Task<RenderProgress?> StartRenderAsync(RenderRequest request)
        => await PostAsync<RenderProgress>("/render/start", request).ConfigureAwait(false);

    public async Task<RenderProgress?> GetRenderStatusAsync(string taskId)
        => await GetAsync<RenderProgress>($"/render/status/{taskId}").ConfigureAwait(false);

    public async Task CancelRenderAsync(string taskId)
        => await PostAsync<object>($"/render/cancel/{taskId}", null).ConfigureAwait(false);
}
