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
    // --- Brain (Plan Phase 5) ---

    public Task<BrainSuggestResponse?> BrainSuggestAsync(int audioClipId, List<int> videoClipIds, int topN = 20)
        => PostAsync<BrainSuggestResponse>("/brain/suggest", new
        {
            audio_clip_id = audioClipId,
            video_clip_ids = videoClipIds,
            top_n = topN,
        });

    public async Task<BrainFeedbackResponse?> BrainFeedbackAsync(int cutId, string rating)
    {
        var operationKey = (
            ProjectIdentity: Volatile.Read(ref _activeProjectIdentity),
            CutId: cutId,
            Rating: rating);
        var operationId = _pendingBrainFeedbackOperations.GetOrAdd(
            operationKey,
            static _ => Guid.NewGuid());
        try
        {
            using var response = await _http.PostAsJsonAsync(
                "/brain/feedback",
                new
                {
                    cut_id = cutId,
                    rating,
                    operation_id = operationId,
                    project_identity = operationKey.ProjectIdentity,
                },
                JsonOptions,
                _shutdownCts.Token).ConfigureAwait(false);
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadFromJsonAsync<BrainFeedbackResponse>(
                    JsonOptions,
                    _shutdownCts.Token).ConfigureAwait(false);
                if (result is not null)
                    _pendingBrainFeedbackOperations.TryRemove(operationKey, out _);
                return result;
            }

            var raw = await response.Content.ReadAsStringAsync(
                _shutdownCts.Token).ConfigureAwait(false);
            var detail = TryReadErrorDetail(raw)
                ?? $"Feedback abgelehnt (HTTP {(int)response.StatusCode}).";
            _logger.LogWarning(
                "POST /brain/feedback abgelehnt: {Status} {Detail}",
                (int)response.StatusCode,
                detail);
            if ((int)response.StatusCode < 500)
                _pendingBrainFeedbackOperations.TryRemove(operationKey, out _);
            return new BrainFeedbackResponse("rejected", 0, 0, detail);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "POST /brain/feedback fehlgeschlagen");
            return new BrainFeedbackResponse("failed", 0, 0, ex.Message);
        }
    }

    private static string? TryReadErrorDetail(string raw)
    {
        try
        {
            using var document = JsonDocument.Parse(raw);
            if (!document.RootElement.TryGetProperty("detail", out var detail))
                return null;
            return detail.ValueKind == JsonValueKind.String
                ? detail.GetString()
                : detail.GetRawText();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    public Task<BrainLearningSessionResponse?> BrainLearningSessionAsync()
        => PostAsync<BrainLearningSessionResponse>("/brain/learning_session", null);

    public Task<BrainStatsResponse?> BrainStatsAsync()
        => GetAsync<BrainStatsResponse>("/brain/stats");

    public Task<BrainResetResponse?> BrainResetRequestAsync()
        => PostOwnerAuthorizedAsync<BrainResetResponse>("/brain/reset", null);

    public Task<BrainResetResponse?> BrainResetConfirmAsync(string confirmationToken)
        => PostOwnerAuthorizedAsync<BrainResetResponse>(
            "/brain/reset",
            new { confirmation_token = confirmationToken });

    // R-Brain-09: Erklaerung fuer Confidence-Balken in der Timeline.
    // narrative=true (Default): Backend versucht eine providergebundene LLM-Erklaerung;
    // bei Fehler bleibt response.Narrative=null und der Tooltip faellt auf die
    // strukturierte Anzeige zurueck (kein Breaking-Change).
    public Task<BrainExplainResponse?> BrainExplainAsync(int cutId, int topN = 3, bool narrative = true, CancellationToken ct = default)
        => GetAsync<BrainExplainResponse>(
            $"/brain/explain/{cutId}?top_n={topN}&narrative={(narrative ? "true" : "false")}",
            ct);
}
