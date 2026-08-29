using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

/// <summary>
/// Typisierter HTTP Client für Kommunikation mit dem Python FastAPI Backend.
/// Alle Methoden sind async und blockieren das UI nicht.
/// </summary>
public class ApiClient : IApiClient
{
    private readonly HttpClient _http;
    private readonly ILogger<ApiClient> _logger;
    private readonly CancellationTokenSource _shutdownCts = new();
    private readonly ConcurrentDictionary<(string ProjectIdentity, int CutId, string Rating), Guid>
        _pendingBrainFeedbackOperations = new();
    private string _activeProjectIdentity = $"session:{Guid.NewGuid():N}";
    private volatile bool _isShuttingDown;
    private bool _disposed;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public ApiClient(HttpClient http, ILogger<ApiClient> logger)
    {
        _http = http;
        _http.Timeout = TimeSpan.FromMinutes(20);
        _logger = logger;
    }

    public void BeginShutdown()
    {
        if (_isShuttingDown)
            return;

        _isShuttingDown = true;
        _shutdownCts.Cancel();
    }

    /// <summary>
    /// Grund des zuletzt fehlgeschlagenen Requests, wie ihn das Backend im
    /// <c>detail</c>-Feld gemeldet hat. Vor dem Fix wurde dieser Body verworfen,
    /// wodurch jedes 4xx für User und Log grundlos blieb (Audit 2026-08-05, C-1/T0.1).
    /// </summary>
    public string? LastErrorDetail { get; private set; }

    /// <summary>Liest das <c>detail</c>-Feld einer Fehlerantwort und merkt es sich.</summary>
    private async Task<string?> CaptureErrorDetailAsync(
        HttpResponseMessage response,
        CancellationToken token)
    {
        try
        {
            var raw = await response.Content.ReadAsStringAsync(token).ConfigureAwait(false);
            LastErrorDetail = ExtractDetail(raw);
        }
        catch (Exception ex) when (!IsExpectedCancellation(ex, token))
        {
            LastErrorDetail = null;
        }
        return LastErrorDetail;
    }

    /// <summary>
    /// Zieht den lesbaren Fehlergrund aus einem FastAPI-Body. <c>detail</c> ist
    /// entweder ein String (HTTPException) oder eine Liste (Validierungsfehler).
    /// </summary>
    private static string? ExtractDetail(string? rawBody)
    {
        if (string.IsNullOrWhiteSpace(rawBody))
            return null;

        try
        {
            using var doc = JsonDocument.Parse(rawBody);
            if (doc.RootElement.ValueKind == JsonValueKind.Object
                && doc.RootElement.TryGetProperty("detail", out var detail))
            {
                if (detail.ValueKind == JsonValueKind.String)
                    return detail.GetString();

                if (detail.ValueKind == JsonValueKind.Array)
                {
                    var parts = detail.EnumerateArray()
                        .Select(item => item.ValueKind == JsonValueKind.Object
                            && item.TryGetProperty("msg", out var msg)
                                ? msg.GetString()
                                : item.ToString())
                        .Where(part => !string.IsNullOrWhiteSpace(part));
                    var joined = string.Join("; ", parts);
                    return string.IsNullOrWhiteSpace(joined) ? null : joined;
                }

                return detail.ToString();
            }
        }
        catch (JsonException)
        {
            // Kein JSON-Body — der Rohtext ist immer noch besser als gar nichts.
        }

        var trimmed = rawBody.Trim();
        return trimmed.Length > 500 ? trimmed[..500] : trimmed;
    }

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

    // --- Project ---

    public async Task<ProjectInfo?> CreateProjectAsync(string name, string path)
    {
        var project = await PostAsync<ProjectInfo>(
            "/project/create",
            new { name, path }).ConfigureAwait(false);
        if (project is not null)
            SetActiveProjectIdentity(project);
        return project;
    }

    public async Task<ProjectInfo?> OpenProjectAsync(string path)
    {
        var project = await PostAsync<ProjectInfo>(
            "/project/open",
            new { path }).ConfigureAwait(false);
        if (project is not null)
            SetActiveProjectIdentity(project);
        return project;
    }

    public async Task<StatusResponse?> SaveProjectAsync()
        => await PostAsync<StatusResponse>("/project/save", null).ConfigureAwait(false);

    public async Task<StatusResponse?> CloseProjectAsync()
    {
        var result = await PostAsync<StatusResponse>(
            "/project/close",
            null).ConfigureAwait(false);
        if (result is not null)
            ResetActiveProjectIdentity();
        return result;
    }

    /// <summary>
    /// Laedt die manuellen Anker des aktiven Projekts.
    /// Audit 2026-08-06 (T4.3): neu, der ANCHOR-Tab hatte kein Backend.
    /// </summary>
    public Task<AnchorListResponse?> GetProjectAnchorsAsync(CancellationToken ct = default)
        => GetAsync<AnchorListResponse>("/project/anchors", ct);

    /// <summary>Ersetzt die manuellen Anker des aktiven Projekts.</summary>
    public Task<AnchorListResponse?> SetProjectAnchorsAsync(
        List<AnchorEntry> anchors,
        CancellationToken ct = default)
        => PostAsync<AnchorListResponse>("/project/anchors", anchors, ct);

    public async Task<ProjectInfo?> GetProjectInfoAsync()
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "/project/info");

        try
        {
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, _shutdownCts.Token).ConfigureAwait(false);
            if (response.StatusCode == System.Net.HttpStatusCode.BadRequest)
            {
                var detail = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (detail.Contains("Kein Projekt geöffnet", StringComparison.OrdinalIgnoreCase)
                    || detail.Contains("Kein Projekt ge\u00f6ffnet", StringComparison.OrdinalIgnoreCase))
                {
                    ResetActiveProjectIdentity();
                    return null;
                }
            }

            response.EnsureSuccessStatusCode();
            var project = await response.Content.ReadFromJsonAsync<ProjectInfo>(JsonOptions).ConfigureAwait(false);
            if (project is not null)
                SetActiveProjectIdentity(project);
            return project;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "GET {Url} fehlgeschlagen", "/project/info");
            return null;
        }
    }

    // --- Audio ---

    public async Task<AudioClipInfo?> ImportAudioAsync(string path)
        => await PostAsync<AudioClipInfo>("/audio/import", new { path }).ConfigureAwait(false);

    public async Task<List<AudioClipInfo>?> GetAudioClipsAsync(int page = 1, int limit = 200)
        => await GetAsync<List<AudioClipInfo>>($"/audio/clips?page={page}&limit={limit}").ConfigureAwait(false);

    public async Task<AudioAnalysisResult?> AnalyzeAudioAsync(
        int clipId,
        CancellationToken cancellationToken = default)
    {
        var transport = await PostAsync<PBStudio.UI.Generated.AudioAnalysisResult>(
            "/audio/analyze",
            new { clip_id = clipId },
            cancellationToken).ConfigureAwait(false);
        return transport is null ? null : AudioAnalysisResult.FromTransport(transport);
    }

    public async Task<List<BeatData>?> GetBeatsAsync(int clipId)
        => await GetAsync<List<BeatData>>($"/audio/beats/{clipId}").ConfigureAwait(false);

    public async Task<List<double>?> GetOnsetsAsync(int clipId)
        => await GetAsync<List<double>>($"/audio/onsets/{clipId}").ConfigureAwait(false);

    public async Task<StemResult?> SeparateStemsAsync(int clipId, string model = "htdemucs.yaml", CancellationToken cancellationToken = default)
        => await PostAsync<StemResult>("/audio/stems/separate", new { clip_id = clipId, model }, cancellationToken).ConfigureAwait(false);


    // --- Audio (Erweitert) ---

    public async Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3)
        => await GetAsync<WaveformData>($"/audio/waveform/{clipId}?bands={bands}").ConfigureAwait(false);

    public async Task<List<StructureSegment>?> GetStructureAsync(int clipId)
        => await GetAsync<List<StructureSegment>>($"/audio/structure/{clipId}").ConfigureAwait(false);

    public async Task<PBStudio.UI.Generated.SpectralData?> GetSpectralAsync(int clipId)
        => await GetAsync<PBStudio.UI.Generated.SpectralData>($"/audio/spectral/{clipId}").ConfigureAwait(false);

    // --- Video ---

    public async Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths)
        => await PostAsync<List<VideoClipInfo>>("/video/import", new { paths }).ConfigureAwait(false);

    public async Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200, CancellationToken cancellationToken = default)
        => await GetAsync<List<VideoClipInfo>>($"/video/clips?page={page}&limit={limit}", cancellationToken).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteVideoClipAsync(int clipId, CancellationToken cancellationToken = default)
        => await DeleteAsync<DeleteResponse>($"/video/clips/{clipId}", cancellationToken).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteVideoClipsBatchAsync(List<int> clipIds, CancellationToken cancellationToken = default)
        => await DeleteWithBodyAsync<DeleteResponse>("/video/clips", new { clip_ids = clipIds }, cancellationToken).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteAudioClipAsync(int clipId, CancellationToken cancellationToken = default)
        => await DeleteAsync<DeleteResponse>($"/audio/clips/{clipId}", cancellationToken).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteAudioClipsBatchAsync(List<int> clipIds, CancellationToken cancellationToken = default)
        => await DeleteWithBodyAsync<DeleteResponse>("/audio/clips", new { clip_ids = clipIds }, cancellationToken).ConfigureAwait(false);

    public async Task<byte[]?> GetThumbnailAsync(int clipId, CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, $"/video/thumbnails/{clipId}");
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        try
        {
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseContentRead, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            // R16/MEDIUM-002: Use linked token (includes _shutdownCts) for content read too
            return await response.Content.ReadAsByteArrayAsync(token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Thumbnail-Abruf fehlgeschlagen: {ClipId}", clipId);
            return null;
        }
    }

    public async Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId, bool detectScenes = true, bool analyzeMotion = true, bool generateEmbeddings = true, bool generateCaptions = true, CancellationToken cancellationToken = default)
        => await PostAsync<VideoAnalysisResult>("/video/analyze", new { 
            clip_id = clipId,
            detect_scenes = detectScenes,
            analyze_motion = analyzeMotion,
            generate_embeddings = generateEmbeddings,
            generate_captions = generateCaptions
        }, cancellationToken).ConfigureAwait(false);

    public async Task<List<SceneInfo>?> GetScenesAsync(int clipId)
        => await GetAsync<List<SceneInfo>>($"/video/scenes/{clipId}").ConfigureAwait(false);

    public async Task<MotionData?> GetMotionAsync(int clipId)
        => await GetAsync<MotionData>($"/video/motion/{clipId}").ConfigureAwait(false);

    // T6 (Timeline-Multi-Lane): Thumb-Strip + Mini-Wave fuer Per-Clip-Renderings.
    // Backend: backend/routers/video_router.py
    //   GET /video/thumbstrip/{clip_id}?n=8   -> Base64 JPEGs
    //   GET /video/clipwave/{clip_id}?n=256   -> Downsampled Mono-Peaks (0..1)
    public async Task<ThumbstripResponse?> GetThumbStripAsync(int clipId, int n = 8, CancellationToken cancellationToken = default)
        => await GetAsync<ThumbstripResponse>($"/video/thumbstrip/{clipId}?n={n}", cancellationToken).ConfigureAwait(false);

    public async Task<ClipwaveResponse?> GetClipWaveAsync(int clipId, int n = 256, CancellationToken cancellationToken = default)
        => await GetAsync<ClipwaveResponse>($"/video/clipwave/{clipId}?n={n}", cancellationToken).ConfigureAwait(false);

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

    public async Task ShutdownAsync()
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            using var request = new HttpRequestMessage(HttpMethod.Post, "/shutdown")
            {
                Content = JsonContent.Create((object?)null, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, cts.Token).ConfigureAwait(false);
            _logger.LogInformation("Backend graceful shutdown angefordert: {StatusCode}", response.StatusCode);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Backend /shutdown fehlgeschlagen (unkritisch — Prozess wird beendet)");
        }
    }

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
        var operationKey = (Volatile.Read(ref _activeProjectIdentity), cutId, rating);
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

    private void SetActiveProjectIdentity(ProjectInfo project)
    {
        var projectPath = project.Path.Trim();
        try
        {
            projectPath = Path.GetFullPath(projectPath);
        }
        catch (Exception ex) when (ex is ArgumentException
                                   or NotSupportedException
                                   or PathTooLongException)
        {
            _logger.LogWarning(
                ex,
                "Projektpfad konnte fuer Feedback-Idempotenz nicht normalisiert werden: {Path}",
                project.Path);
        }

        projectPath = Path.TrimEndingDirectorySeparator(projectPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar)
            .ToUpperInvariant();
        Volatile.Write(ref _activeProjectIdentity, $"path:{projectPath}");
    }

    private void ResetActiveProjectIdentity()
        => Volatile.Write(
            ref _activeProjectIdentity,
            $"session:{Guid.NewGuid():N}");

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
    // narrative=true (Default): Backend versucht LLM-Erklaerung via Ollama;
    // bei Fehler bleibt response.Narrative=null und der Tooltip faellt auf die
    // strukturierte Anzeige zurueck (kein Breaking-Change).
    public Task<BrainExplainResponse?> BrainExplainAsync(int cutId, int topN = 3, bool narrative = true, CancellationToken ct = default)
        => GetAsync<BrainExplainResponse>(
            $"/brain/explain/{cutId}?top_n={topN}&narrative={(narrative ? "true" : "false")}",
            ct);

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


    #region Model Manager
    // ----------------------------------------------------------------------
    // Ollama-Modell-Management. Backend: backend/routers/models_router.py
    //
    // Pull-Stream: Backend sendet SSE-Frames:
    //   event: pull_progress
    //   data: {"status":"pulling manifest", ...}
    //   <blank line>
    //
    // Wir parsen die SSE-Frames inline (kein dedizierter SSEClient noetig,
    // weil das hier ein per-Aufruf-Stream mit POST-Body ist).
    // ----------------------------------------------------------------------

    public Task<ModelListResponse?> GetInstalledModelsAsync(CancellationToken ct = default)
        => GetAsync<ModelListResponse>("/models/list?refresh=true", ct);

    public Task<AvailableModelsResponse?> GetAvailableModelsAsync(CancellationToken ct = default)
        => GetAsync<AvailableModelsResponse>("/models/available", ct);

    public Task<ModelRecommendationResponse?> GetModelRecommendationAsync(
        string task = "video_captioning",
        string mode = "balance",
        CancellationToken ct = default)
    {
        var url = $"/models/recommendations?task={Uri.EscapeDataString(task)}&mode={Uri.EscapeDataString(mode)}";
        return GetAsync<ModelRecommendationResponse>(url, ct);
    }

    public async Task<bool> ActivateModelAsync(string name, string provider, CancellationToken ct = default)
    {
        try
        {
            var result = await PostOwnerAuthorizedAsync<object>(
                "/models/activate",
                new { name, provider },
                ct).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "ActivateModelAsync {Name} fehlgeschlagen", name);
            return false;
        }
    }

    public async Task<bool> UpdateKiModeAsync(string mode, CancellationToken ct = default)
    {
        try
        {
            var result = await PostOwnerAuthorizedAsync<object>(
                "/models/mode",
                new { mode },
                ct).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "UpdateKiModeAsync {Mode} fehlgeschlagen", mode);
            return false;
        }
    }

    public async Task<ModelTestResponse?> TestModelAsync(string name, string provider, CancellationToken ct = default)
    {
        try
        {
            return await PostOwnerAuthorizedAsync<ModelTestResponse>(
                "/models/test",
                new { name, provider },
                ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "TestModelAsync {Name} fehlgeschlagen", name);
            return new ModelTestResponse(false, 0.0, "", ex.Message);
        }
    }

    /// <summary>
    /// Loescht eine exakt live verifizierte Ollama-Modell-ID.
    /// LM-Studio-Modelle bleiben in der Desktop-App verwaltet.
    /// </summary>
    public async Task<bool> DeleteModelAsync(string name, CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        try
        {
            var url = $"/models/{Uri.EscapeDataString(name)}";
            using var request = new HttpRequestMessage(HttpMethod.Delete, url);
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);

            if ((int)response.StatusCode == 501)
            {
                _logger.LogInformation(
                    "DeleteModel {Name}: Backend antwortete 501 — LM Studio managed Modelle ueber die App",
                    name);
                throw new NotSupportedException(
                    "Modell-Loeschung wird nicht mehr ueber PB Studio unterstuetzt. " +
                    "Bitte oeffne LM Studio -> My Models um das Modell zu entfernen.");
            }

            if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                _logger.LogInformation("DeleteModel: {Name} nicht gefunden", name);
                return false;
            }
            response.EnsureSuccessStatusCode();
            return true;
        }
        catch (NotSupportedException)
        {
            throw;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, ct))
        {
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DeleteModel {Name} fehlgeschlagen", name);
            return false;
        }
    }

    public async IAsyncEnumerable<PullProgressEvent> PullModelAsync(
        string name,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        // Hinweis: yield return darf NICHT in try/catch stehen (CS1626/CS1631).
        // Deshalb wickeln wir IO + Setup in OpenPullStreamAsync / ReadLineSafeAsync, die
        // bei Cancellation/Errors null liefern statt zu werfen.
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        var stream = await OpenPullStreamAsync(name, token, ct).ConfigureAwait(false);
        if (stream is null) yield break;

        try
        {
            using var reader = new System.IO.StreamReader(stream, System.Text.Encoding.UTF8);
            string? currentEvent = null;
            var dataBuffer = new System.Text.StringBuilder();

            while (true)
            {
                var (line, eof, cancelled) = await ReadLineSafeAsync(reader, token, ct).ConfigureAwait(false);
                if (cancelled) yield break;

                if (eof)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var evtFlush = ParseEvent(currentEvent, dataBuffer.ToString());
                        if (evtFlush is not null) yield return evtFlush;
                    }
                    yield break;
                }

                if (line!.Length == 0)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var evt = ParseEvent(currentEvent, dataBuffer.ToString());
                        if (evt is not null)
                        {
                            yield return evt;
                            if (evt.IsTerminal) yield break;
                        }
                    }
                    currentEvent = null;
                    dataBuffer.Clear();
                    continue;
                }

                if (line.StartsWith("event:", StringComparison.Ordinal))
                {
                    currentEvent = line.Substring(6).Trim();
                }
                else if (line.StartsWith("data:", StringComparison.Ordinal))
                {
                    if (dataBuffer.Length > 0) dataBuffer.Append('\n');
                    dataBuffer.Append(line.Substring(5).TrimStart());
                }
                // Andere SSE-Felder (id:, retry:) ignorieren wir.
            }
        }
        finally
        {
            stream.Dispose();
        }
    }

    /// <summary>Setup-Helfer fuer einen live verifizierten Ollama-Pull.</summary>
    private async Task<System.IO.Stream?> OpenPullStreamAsync(string name, CancellationToken token, CancellationToken originalCt)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/models/pull")
        {
            Content = JsonContent.Create(new { name }, options: JsonOptions),
        };
        // request bewusst NICHT disposen — der Lifetime ist an die Response gekoppelt,
        // und das Disposen waehrend der Streamkonsum kann den Socket killen. Der GC raeumt's.
        var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token).ConfigureAwait(false);
        try
        {
            if ((int)response.StatusCode == 501)
            {
                _logger.LogInformation(
                    "PullModel {Name}: Backend antwortete 501 — LM Studio managed Downloads ueber die App",
                    name);
                throw new NotSupportedException(
                    "Modell-Download wird nicht mehr ueber PB Studio unterstuetzt. " +
                    "Bitte oeffne LM Studio -> Discover-Tab um das Modell herunterzuladen.");
            }

            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
        }
        catch (NotSupportedException)
        {
            response.Dispose();
            throw;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, originalCt))
        {
            response.Dispose();
            return null;
        }
        catch (Exception ex)
        {
            response.Dispose();
            _logger.LogWarning(ex, "PullModel({Name}): Stream-Open fehlgeschlagen", name);
            return null;
        }
    }

    /// <summary>Liest eine SSE-Zeile. Return: (line, eof, cancelled).</summary>
    private static async Task<(string? line, bool eof, bool cancelled)> ReadLineSafeAsync(
        System.IO.StreamReader reader,
        CancellationToken token,
        CancellationToken originalCt)
    {
        try
        {
            var line = await reader.ReadLineAsync(token).ConfigureAwait(false);
            return (line, line is null, false);
        }
        catch (OperationCanceledException)
        {
            return (null, false, true);
        }
        catch
        {
            // Netzwerk-Fehler treat as EOF — Verbraucher merkt das am ausbleibenden Terminal-Event.
            return (null, true, false);
        }
    }

    private PullProgressEvent? ParseEvent(string? eventName, string data)
    {
        if (string.IsNullOrWhiteSpace(data)) return null;

        try
        {
            var doc = JsonDocument.Parse(data);
            var root = doc.RootElement;

            // pull_error-Event: Backend sendet {"error": "..."}.
            // pull_progress-Event: Ollama liefert {status, completed, total, digest}.
            string? status = null, digest = null, error = null;
            long? completed = null, total = null;

            if (root.TryGetProperty("status", out var st) && st.ValueKind == JsonValueKind.String)
                status = st.GetString();
            if (root.TryGetProperty("digest", out var dg) && dg.ValueKind == JsonValueKind.String)
                digest = dg.GetString();
            if (root.TryGetProperty("error", out var er) && er.ValueKind == JsonValueKind.String)
                error = er.GetString();
            if (root.TryGetProperty("completed", out var cp) && cp.ValueKind == JsonValueKind.Number && cp.TryGetInt64(out var cpVal))
                completed = cpVal;
            if (root.TryGetProperty("total", out var tt) && tt.ValueKind == JsonValueKind.Number && tt.TryGetInt64(out var ttVal))
                total = ttVal;

            // pull_error-Event hat keinen "status" — wir setzen ihn synthetisch
            if (error is not null && status is null)
                status = "error";

            return new PullProgressEvent(status, completed, total, digest, error);
        }
        catch (JsonException ex)
        {
            _logger.LogDebug(ex, "PullStream: ungueltige JSON-Zeile event={Event}, data={Data}", eventName, data);
            return null;
        }
    }
    #endregion

    // --- Generische Helfer ---

    public async Task<T?> GetAsync<T>(string url, CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.GetAsync(url, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            // R16/MEDIUM-001: Use linked token (includes _shutdownCts) for deserialization too
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "GET {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> DeleteAsync<T>(
        string url,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.DeleteAsync(url, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> DeleteWithBodyAsync<T>(
        string url,
        object body,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            // HttpClient.DeleteAsync supports no body; need explicit HttpRequestMessage
            using var request = new HttpRequestMessage(HttpMethod.Delete, url)
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} (with body) fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> PostAsync<T>(
        string url,
        object? body,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.PostAsJsonAsync(url, body, JsonOptions, token).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                var detail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false);
                _logger.LogWarning(
                    "POST {Url} fehlgeschlagen: {Status} — {Detail}",
                    url,
                    (int)response.StatusCode,
                    detail ?? "(kein Detail im Body)");
                return null;
            }

            LastErrorDetail = null;
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            LastErrorDetail = ex.Message;
            _logger.LogWarning(ex, "POST {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private bool IsExpectedCancellation(Exception ex, CancellationToken cancellationToken = default)
        => ex is OperationCanceledException
           || (_isShuttingDown && ex is ObjectDisposedException)
           || cancellationToken.IsCancellationRequested
           || _shutdownCts.IsCancellationRequested;

    // R16/CRITICAL-004: _shutdownCts was never disposed. IApiClient now extends
    // IDisposable so the DI container (singleton scoped) disposes this on app exit.
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        if (!_isShuttingDown)
        {
            _isShuttingDown = true;
            _shutdownCts.Cancel();
        }
        _shutdownCts.Dispose();
        _pendingBrainFeedbackOperations.Clear();
    }

    // =====================================================================
    // Chat (KI-Chat Track 2026-05-16)
    // =====================================================================

    public async IAsyncEnumerable<ChatStreamEvent> SendChatMessageAsync(
        string message,
        IReadOnlyList<ChatMessage>? history = null,
        string mode = "balance",
        bool saveHistory = true,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        var historyPayload = history?
            .Where(m => m.Role == ChatRole.User || m.Role == ChatRole.Assistant)
            .Select(m => new
            {
                role = m.Role == ChatRole.User ? "user" : "assistant",
                content = m.Content ?? string.Empty,
            })
            .ToList();

        var body = new
        {
            message,
            history = historyPayload,
            mode,
            save_history = saveHistory,
        };

        var stream = await OpenChatStreamAsync(body, token, ct).ConfigureAwait(false);
        if (stream is null) yield break;

        try
        {
            using var reader = new System.IO.StreamReader(stream, System.Text.Encoding.UTF8);
            string? currentEvent = null;
            var dataBuffer = new System.Text.StringBuilder();

            while (true)
            {
                var (line, eof, cancelled) = await ReadLineSafeAsync(reader, token, ct).ConfigureAwait(false);
                if (cancelled) yield break;

                if (eof)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var ev = ParseChatEvent(currentEvent, dataBuffer.ToString());
                        if (ev is not null) yield return ev;
                    }
                    yield break;
                }

                if (line!.Length == 0)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var ev = ParseChatEvent(currentEvent, dataBuffer.ToString());
                        if (ev is not null)
                        {
                            yield return ev;
                            if (ev.Type == ChatEventType.Done)
                            {
                                yield break;
                            }
                        }
                    }
                    currentEvent = null;
                    dataBuffer.Clear();
                    continue;
                }

                if (line.StartsWith("event:", StringComparison.Ordinal))
                {
                    currentEvent = line.Substring(6).Trim();
                }
                else if (line.StartsWith("data:", StringComparison.Ordinal))
                {
                    if (dataBuffer.Length > 0) dataBuffer.Append('\n');
                    dataBuffer.Append(line.Substring(5).TrimStart());
                }
            }
        }
        finally
        {
            stream.Dispose();
        }
    }

    private async Task<System.IO.Stream?> OpenChatStreamAsync(object body, CancellationToken token, CancellationToken originalCt)
    {
        try
        {
            var request = new HttpRequestMessage(HttpMethod.Post, "/chat/message")
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token).ConfigureAwait(false);
            try
            {
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
            }
            catch
            {
                response.Dispose();
                throw;
            }
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, originalCt))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "SendChatMessageAsync: Failed to open stream");
            throw;
        }
    }

    private static ChatStreamEvent? ParseChatEvent(string? eventName, string dataJson)
    {
        if (string.IsNullOrWhiteSpace(dataJson)) return null;
        JsonElement root;
        try
        {
            using var doc = JsonDocument.Parse(dataJson);
            root = doc.RootElement.Clone();
        }
        catch (JsonException)
        {
            return new ChatStreamEvent(ChatEventType.Unknown, eventName ?? "unknown");
        }

        var type = eventName?.ToLowerInvariant() switch
        {
            "model" => ChatEventType.Model,
            "text" => ChatEventType.Text,
            "tool_call" => ChatEventType.ToolCall,
            "tool_confirmation_required" => ChatEventType.ToolConfirmationRequired,
            "tool_result" => ChatEventType.ToolResult,
            "error" => ChatEventType.Error,
            "done" => ChatEventType.Done,
            _ => ChatEventType.Unknown,
        };

        string? Str(string key) => root.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
        string? RawJson(string key) => root.TryGetProperty(key, out var v) ? v.GetRawText() : null;

        return type switch
        {
            ChatEventType.Model => new ChatStreamEvent(type, eventName!, ModelName: Str("model"), ModelReason: Str("reason")),
            ChatEventType.Text => new ChatStreamEvent(type, eventName!, Text: Str("content")),
            ChatEventType.ToolCall => new ChatStreamEvent(type, eventName!, ToolName: Str("name"), ToolArgumentsJson: RawJson("arguments")),
            ChatEventType.ToolConfirmationRequired => new ChatStreamEvent(
                type,
                eventName!,
                ToolName: Str("name"),
                ToolArgumentsJson: RawJson("arguments"),
                ConfirmationId: Str("confirmation_id"),
                ConfirmationExpiresInSeconds: root.TryGetProperty("expires_in_seconds", out var expires)
                    && expires.TryGetDouble(out var seconds) ? seconds : null),
            ChatEventType.ToolResult => new ChatStreamEvent(type, eventName!, ToolName: Str("name"), ToolResultJson: RawJson("result")),
            ChatEventType.Error => new ChatStreamEvent(type, eventName!, ErrorMessage: Str("message"), ErrorStage: Str("stage")),
            ChatEventType.Done => new ChatStreamEvent(type, eventName!, Text: Str("final_text"), DoneReason: Str("reason")),
            _ => new ChatStreamEvent(type, eventName ?? "unknown"),
        };
    }

    private async Task<T?> PostOwnerAuthorizedAsync<T>(
        string url,
        object? body,
        CancellationToken cancellationToken = default) where T : class
    {
        // Bewusst KEINE Capability-Vorabpruefung mehr an dieser Stelle:
        // Der Getter liefert null, solange der 10-Sekunden-Watchdog revalidiert
        // (siehe BackendOwnerCapability, _isVerified wird dabei kurz false).
        // Die alte Pruefung lief ausserhalb des RevalidationGate und brach Requests
        // hart ab, die in dieses Fenster fielen — sichtbar als "Button reagiert nicht".
        // Der OwnerCapabilityRequestHandler wartet am Gate und prueft dort
        // fail-closed; der Sicherheitsgewinn der Vorabpruefung war also null.
        // Audit 2026-08-05, H-1/T1.2.
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken,
                _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, url)
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                var detail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false);
                _logger.LogWarning(
                    "Owner-authorized POST {Url} fehlgeschlagen: {Status} — {Detail}",
                    url,
                    (int)response.StatusCode,
                    detail ?? "(kein Detail im Body)");
                return null;
            }

            LastErrorDetail = null;
            return await response.Content.ReadFromJsonAsync<T>(
                JsonOptions,
                token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            LastErrorDetail = ex.Message;
            _logger.LogWarning(ex, "Owner-authorized POST {Url} fehlgeschlagen", url);
            return null;
        }
    }

    public async Task<bool> DecideChatToolConfirmationAsync(
        string confirmationId, bool approve, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(confirmationId)) return false;
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        var decision = approve ? "approve" : "reject";
        try
        {
            using var response = await _http.PostAsync(
                $"/chat/confirm/{Uri.EscapeDataString(confirmationId)}/{decision}",
                content: null,
                token).ConfigureAwait(false);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, ct))
        {
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Chat tool confirmation failed");
            return false;
        }
    }

    public async Task<bool> ClearChatHistoryAsync(CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.DeleteAsync("/chat/history", token).ConfigureAwait(false);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "ClearChatHistoryAsync failed");
            return false;
        }
    }
}

// --- API Response Models ---

public record HealthStatus(string Status, double UptimeSeconds, bool GpuAvailable);
public record GpuStatus(
    string Name,
    double VramTotalMb,
    double VramUsedMb,
    double TemperatureC,
    string DriverVersion,
    int? AdapterIndex = null,
    string? AdapterLuid = null,
    string? AdapterName = null,
    string? SelectionPolicy = null,
    double DedicatedVramTotalMb = 0,
    bool DirectmlActive = false,
    string MonitoringStatus = "error",
    string? MonitoringError = null);
public record GpuCleanupResponse(
    bool Success,
    int FreedMb,
    string? Error = null);
public record StatusResponse(bool Success, string Message);
public record ProjectInfo(string Name, string Path, int AudioCount, int VideoCount, bool HasTimeline, string? CreatedAt = null, string? ModifiedAt = null, int? DbProjectId = null);
public record AudioClipInfo(
    int Id,
    string Name,
    string Path,
    double DurationSeconds,
    int SampleRate,
    int Channels,
    string Format,
    double Bpm = 0.0,
    string? Key = null,
    int BeatCount = 0,
    bool IsAnalyzed = false,
    // L-N2: Content-Hash fuer Cache-Hit-Badge auf der AudioClip-Card.
    // Persisted im Backend nach Streaming-Hash beim Import; signalisiert
    // dass Embedding/Analyse aus Cache wiederverwendbar sind.
    string? AudioHash = null,
    bool HasAudioEmbedding = false,
    // L-N4: Stem-Separation Outputs — Dict {vocals|instrumental|drums|bass|other -> path}.
    // Gesetzt nach POST /audio/stems/separate. UI rendert STEMS-Badge und
    // "Stems-Ordner oeffnen"-Button wenn nicht null und nicht-leer.
    Dictionary<string, string>? StemsPaths = null,
    string AnalysisStatus = "unavailable",
    Dictionary<string, string>? StageStatus = null,
    Dictionary<string, string>? StageErrors = null);
public record StructureSegment(double StartTime, double EndTime, string Label, double Confidence = 0.0, double EnergyScore = 0.0);
public record SubtrackSegment(double StartTime, double EndTime, double Confidence = 0.0, double? SubBpm = null, string? SubKey = null);
public record AudioAnalysisResult(
    int ClipId,
    double DurationSeconds,
    double Bpm,
    int BeatCount,
    List<BeatData> Beats,
    string? Key = null,
    List<double>? EnergyCurve = null,
    List<StructureSegment>? StructureSegments = null,
    PBStudio.UI.Generated.SpectralData? SpectralData = null,
    List<SubtrackSegment>? SubtrackSegments = null,
    List<double>? TempoCurve = null,
    List<double>? OnsetTimes = null,
    List<double>? KickTimes = null,
    List<double>? SnareTimes = null,
    List<double>? HihatTimes = null,
    string AnalysisStatus = "completed",
    Dictionary<string, string>? StageStatus = null,
    Dictionary<string, string>? StageErrors = null,
    Dictionary<string, JsonElement>? ChunkEvidence = null,
    List<double>? Downbeats = null,
    Dictionary<string, JsonElement>? DownbeatProvenance = null)
{
    public static AudioAnalysisResult FromTransport(
        PBStudio.UI.Generated.AudioAnalysisResult value)
    {
        ArgumentNullException.ThrowIfNull(value);

        var beats = value.Beats?.Select(beat => new BeatData(
            beat.Time,
            beat.Strength ?? 0.0,
            beat.Beat_type ?? string.Empty)).ToList() ?? new List<BeatData>();

        return new AudioAnalysisResult(
            value.Clip_id,
            value.Duration_seconds,
            value.Bpm ?? 0.0,
            value.Beat_count ?? beats.Count,
            beats,
            value.Key,
            value.Energy_curve?.ToList(),
            value.Structure_segments?.Select(segment => new StructureSegment(
                segment.Start_time,
                segment.End_time,
                segment.Label,
                segment.Confidence ?? 0.0,
                segment.Energy_score ?? 0.0)).ToList(),
            value.Spectral_data,
            value.Subtrack_segments?.Select(segment => new SubtrackSegment(
                segment.Start_time,
                segment.End_time,
                segment.Confidence ?? 0.0,
                segment.Sub_bpm,
                segment.Sub_key)).ToList(),
            value.Tempo_curve?.ToList(),
            value.Onset_times?.ToList(),
            value.Kick_times?.ToList(),
            value.Snare_times?.ToList(),
            value.Hihat_times?.ToList(),
            value.Analysis_status ?? "unavailable",
            value.Stage_status is null
                ? null
                : new Dictionary<string, string>(value.Stage_status),
            value.Stage_errors is null
                ? null
                : new Dictionary<string, string>(value.Stage_errors),
            ToJsonDictionary(value.Chunk_evidence),
            value.Downbeats?.ToList(),
            ToJsonDictionary(value.Downbeat_provenance));
    }

    private static Dictionary<string, JsonElement>? ToJsonDictionary(object? value)
    {
        if (value is null)
            return null;

        var element = value is JsonElement json
            ? json
            : JsonSerializer.SerializeToElement(value);
        if (element.ValueKind != JsonValueKind.Object)
            return null;

        return element.EnumerateObject().ToDictionary(
            property => property.Name,
            property => property.Value.Clone());
    }
}
public record BeatData(double Time, double Strength, string BeatType);
public record StemResult(int ClipId, string? VocalsPath, string? InstrumentalPath, string? DrumsPath, string? BassPath, string? OtherPath, string ModelUsed);
public record VideoClipInfo(
    int Id,
    string Name,
    string Path,
    double DurationSeconds,
    int Width,
    int Height,
    double Fps,
    string Codec,
    bool ThumbnailAvailable,
    List<string> Tags,
    bool IsAnalyzed = false,
    double? AvgMotion = null,
    double? PeakMotion = null,
    string? MotionCategory = null,
    string? VideoHash = null,
    string? TagSource = null,
    bool HasVideoEmbedding = false,
    int? EmbeddingDim = null,
    int? EmbeddingSamples = null,
    bool HasEmbedding = false,
    string AnalysisStatus = "unavailable",
    Dictionary<string, string>? StageStatus = null,
    Dictionary<string, string>? StageErrors = null);
public record DeleteResponse(int DeletedCount, List<int> NotFoundIds);
public record VideoAnalysisResult(
    int ClipId,
    int SceneCount,
    double AvgMotion,
    List<string> DominantColors,
    List<string> Tags,
    bool HasEmbedding,
    // Audit 2026-08-05 (H-4): Default war 1152 und damit semantisch invertiert.
    // Das Backend definiert ausdruecklich "0 = kein Embedding vorhanden"
    // (video_schemas.py:79). Fehlte das Feld im Response, meldete die WPF-Seite
    // also "Embedding vorhanden" statt "keins".
    int EmbeddingDim = 0,
    List<SceneInfo>? Scenes = null,
    MotionData? Motion = null,
    int EmbeddingSamples = 0,
    string? AudioKey = null,
    string? TagSource = null,
    List<string>? MoodTags = null,
    double AvgBrightness = 0.5,
    double AvgSaturation = 0.5,
    double AvgColorTemp = 0.0,
    string Status = "completed",
    Dictionary<string, string>? StageStatus = null,
    Dictionary<string, string>? StageErrors = null);
public record CutListResponse(List<CutListEntry> Cuts, double TotalDuration, int CutCount, double AverageCutDuration, List<ModeDegradation>? Degradations = null);
// FR-362: ein angeforderter Pacing-Modus, der mangels Datengrundlage nicht wirkte.
// Leere/fehlende Liste = jeder angeforderte Modus hatte eine echte Grundlage.
public record ModeDegradation(string Mode, string Reason, int ScoredClips, int TotalClips);
public record CutListEntry(string ClipId, double StartTime, double EndTime, Dictionary<string, object>? Metadata);
public record TimelineResponse(List<TimelineEntry> Entries, double TotalDuration, string? AudioPath);
public record TimelineEntry(
    string ClipId,
    string ClipName,
    string FilePath,
    double StartTime,
    double EndTime,
    double ClipStart,
    string TriggerType,
    double TriggerStrength,
    string? SegmentType = null,
    double BrainConfidence = 0.0,
    int? CutId = null,
    double FeatureConfidence = 0.0,
    string SemanticStatus = "unavailable",
    string? SemanticReason = null,
    Dictionary<string, JsonElement>? TriggerProvenance = null,
    Dictionary<string, JsonElement>? BrainAxisStatus = null,
    Dictionary<string, JsonElement>? Metadata = null);
public record PacingConfig(int AudioClipId, List<int> VideoClipIds, double ExpectedBpm, bool UseMotionMatching, bool UseSemanticMatching, bool UseStructureAwareness, double? DurationLimit, double MinCutInterval = 0.5, TriggerSettings? TriggerSettings = null, bool UseBrain = false, double BrainMinConfidence = 0.0, bool UseKeyMatching = false, bool UseStemPacing = false, string? CanvasPath = null);
public record TriggerSettings(double BeatWeight = 1.0, double OnsetWeight = 0.5, double KickWeight = 1.2, double SnareWeight = 1.0, double HihatWeight = 0.3, double EnergyWeight = 0.8, double EnergyThreshold = 0.6, double MinClipLength = 1.0, double MaxClipLength = 8.0, double OnsetSensitivity = 0.5, double ClipLengthVariation = 0.0, double MaxCutInterval = 10.0, string BeatTriggerMode = "all");

public record BrainSuggestion(int? CutId, string ClipId, double StartTime, double EndTime, double FinalScore, Dictionary<string, double> BrainScores);
public record BrainSuggestResponse(List<BrainSuggestion> Suggestions);
public record PacingPreviewResponse(string PreviewPath, double Duration, string Resolution);
public record BrainFeedbackResponse(string Status, int UpdatedBuckets, int TotalClicks, string? Message = null);
public record BrainLearningSessionResponse(List<BrainSuggestion> Cuts);
public record BrainStatsBucket(
    string Axis,
    int ContextLevel,
    string ContextKey,
    double PositiveCount,
    double NegativeCount,
    double Posterior,
    double PosteriorVariance = 0.0);

public record BrainStatsResponse(
    int TotalClicks,
    int ColdStartAxes,
    int LearnedAxes,
    List<BrainStatsBucket> TopPositive,
    List<BrainStatsBucket> TopNegative,
    List<string>? ColdStartAxesList = null);
public record BrainResetResponse(string Status, string? ConfirmationToken);
public record WaveformData(int ClipId, int SampleRate, List<List<float>> Bands, double DurationSeconds);
// AP3.3 (Audit 2026-06-10): SceneIndex client-seitig (Backend sendet keinen Index;
// JSON-Deserialisierung lässt das Feld auf 0, VideoLibraryViewModel setzt es nach Load).
public record SceneInfo(double StartTime, double EndTime, string SceneType, double? Confidence)
{
    public int SceneIndex { get; set; }
}
// L-VIDEO-2 / X1: PeakMotion am Ende mit Default 0.0 fuer backward compat —
// Backend liefert es jetzt im MotionData-Response, frueher wurde es im
// Pydantic-Schema silent gedropped.
public record MotionData(int ClipId, double AvgMotion, List<float> MotionCurve, List<Dictionary<string, object>> PeakFrames, string MotionCategory, double PeakMotion = 0.0);
public record RenderRequest(string OutputPath, string AudioPath, string Quality, int ResolutionWidth, int ResolutionHeight, double Fps, double BitrateMbps = 12.0, bool IncludeAudio = true, string? Encoder = null);
public record RenderProgress(
    string TaskId,
    string Status,
    double Percent,
    int CurrentFrame,
    int TotalFrames,
    double Fps,
    double ElapsedSeconds,
    double EtaSeconds,
    string? OutputPath,
    string? Error,
    string? Message = null,
    string? QueueJobId = null,
    string? RunId = null,
    string? EvidencePath = null,
    string? ValidationPath = null,
    bool ProgressEnd = false,
    string? ValidationStatus = null);
