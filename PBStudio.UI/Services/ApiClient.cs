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

    public async Task CleanupGpuAsync()
        => await PostAsync<object>("/gpu/cleanup", null).ConfigureAwait(false);

    // --- Project ---

    public async Task<ProjectInfo?> CreateProjectAsync(string name, string path)
        => await PostAsync<ProjectInfo>("/project/create", new { name, path }).ConfigureAwait(false);

    public async Task<ProjectInfo?> OpenProjectAsync(string path)
        => await PostAsync<ProjectInfo>("/project/open", new { path }).ConfigureAwait(false);

    public async Task<StatusResponse?> SaveProjectAsync()
        => await PostAsync<StatusResponse>("/project/save", null).ConfigureAwait(false);

    public async Task<StatusResponse?> CloseProjectAsync()
        => await PostAsync<StatusResponse>("/project/close", null).ConfigureAwait(false);

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
                    return null;
                }
            }

            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<ProjectInfo>(JsonOptions).ConfigureAwait(false);
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

    public async Task<AudioAnalysisResult?> AnalyzeAudioAsync(int clipId)
        => await PostAsync<AudioAnalysisResult>("/audio/analyze", new { clip_id = clipId }).ConfigureAwait(false);

    public async Task<List<BeatData>?> GetBeatsAsync(int clipId)
        => await GetAsync<List<BeatData>>($"/audio/beats/{clipId}").ConfigureAwait(false);

    public async Task<List<double>?> GetOnsetsAsync(int clipId)
        => await GetAsync<List<double>>($"/audio/onsets/{clipId}").ConfigureAwait(false);

    public async Task<StemResult?> SeparateStemsAsync(int clipId, string model = "htdemucs.yaml")
        => await PostAsync<StemResult>("/audio/stems/separate", new { clip_id = clipId, model }).ConfigureAwait(false);


    // --- Audio (Erweitert) ---

    public async Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3)
        => await GetAsync<WaveformData>($"/audio/waveform/{clipId}?bands={bands}").ConfigureAwait(false);

    public async Task<List<StructureSegment>?> GetStructureAsync(int clipId)
        => await GetAsync<List<StructureSegment>>($"/audio/structure/{clipId}").ConfigureAwait(false);

    public async Task<SpectralData?> GetSpectralAsync(int clipId)
        => await GetAsync<SpectralData>($"/audio/spectral/{clipId}").ConfigureAwait(false);

    // --- Video ---

    public async Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths)
        => await PostAsync<List<VideoClipInfo>>("/video/import", new { paths }).ConfigureAwait(false);

    public async Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200, CancellationToken cancellationToken = default)
        => await GetAsync<List<VideoClipInfo>>($"/video/clips?page={page}&limit={limit}", cancellationToken).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteVideoClipAsync(int clipId)
        => await DeleteAsync<DeleteResponse>($"/video/clips/{clipId}").ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteVideoClipsBatchAsync(List<int> clipIds)
        => await DeleteWithBodyAsync<DeleteResponse>("/video/clips", new { clip_ids = clipIds }).ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteAudioClipAsync(int clipId)
        => await DeleteAsync<DeleteResponse>($"/audio/clips/{clipId}").ConfigureAwait(false);

    public async Task<DeleteResponse?> DeleteAudioClipsBatchAsync(List<int> clipIds)
        => await DeleteWithBodyAsync<DeleteResponse>("/audio/clips", new { clip_ids = clipIds }).ConfigureAwait(false);

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

    public async Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId, bool detectScenes = true, bool analyzeMotion = true, bool generateEmbeddings = true, bool generateCaptions = true)
        => await PostAsync<VideoAnalysisResult>("/video/analyze", new { 
            clip_id = clipId,
            detect_scenes = detectScenes,
            analyze_motion = analyzeMotion,
            generate_embeddings = generateEmbeddings,
            generate_captions = generateCaptions
        }).ConfigureAwait(false);

    public async Task<List<SceneInfo>?> GetScenesAsync(int clipId)
        => await GetAsync<List<SceneInfo>>($"/video/scenes/{clipId}").ConfigureAwait(false);

    public async Task<MotionData?> GetMotionAsync(int clipId)
        => await GetAsync<MotionData>($"/video/motion/{clipId}").ConfigureAwait(false);

    // T6 (Timeline-Multi-Lane): Thumb-Strip + Mini-Wave fuer Per-Clip-Renderings.
    // Backend: backend/routers/video_router.py
    //   GET /video/thumbstrip/{clip_id}?n=8   -> Base64 JPEGs
    //   GET /video/clipwave/{clip_id}?n=256   -> Downsampled Mono-Peaks (0..1)
    public async Task<ThumbstripResponse?> GetThumbStripAsync(int clipId, int n = 8)
        => await GetAsync<ThumbstripResponse>($"/video/thumbstrip/{clipId}?n={n}").ConfigureAwait(false);

    public async Task<ClipwaveResponse?> GetClipWaveAsync(int clipId, int n = 256)
        => await GetAsync<ClipwaveResponse>($"/video/clipwave/{clipId}?n={n}").ConfigureAwait(false);

    // --- Pacing ---

    public async Task<CutListResponse?> GenerateCutListAsync(PacingConfig config)
        => await PostAsync<CutListResponse>("/pacing/generate", config).ConfigureAwait(false);

    public async Task<TimelineResponse?> GetTimelineAsync()
        => await GetAsync<TimelineResponse>("/pacing/timeline").ConfigureAwait(false);

    public async Task<StatusResponse?> UpdateTimelineAsync(List<TimelineEntryModel> entries)
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
                e.CutId
            )).ToList()
        };
        return await PostAsync<StatusResponse>("/pacing/timeline", payload).ConfigureAwait(false);
    }

    public async Task<PacingPreviewResponse?> GenerateTimelinePreviewAsync(double startSec, double duration, CancellationToken ct = default)
        => await PostAsync<PacingPreviewResponse>("/pacing/preview", new
        {
            start_sec = startSec,
            duration,
        }).ConfigureAwait(false);

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
            using var response = await _http.PostAsJsonAsync("/shutdown", (object?)null, JsonOptions, cts.Token).ConfigureAwait(false);
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

    public Task<BrainFeedbackResponse?> BrainFeedbackAsync(int cutId, string rating)
        => PostAsync<BrainFeedbackResponse>("/brain/feedback", new
        {
            cut_id = cutId,
            rating,
        });

    public Task<BrainLearningSessionResponse?> BrainLearningSessionAsync()
        => PostAsync<BrainLearningSessionResponse>("/brain/learning_session", null);

    public Task<BrainStatsResponse?> BrainStatsAsync()
        => GetAsync<BrainStatsResponse>("/brain/stats");

    public Task<BrainResetResponse?> BrainResetRequestAsync()
        => PostAsync<BrainResetResponse>("/brain/reset", null);

    public Task<BrainResetResponse?> BrainResetConfirmAsync(string confirmationToken)
        => PostAsync<BrainResetResponse>("/brain/reset", new { confirmation_token = confirmationToken });

    // R-Brain-09: Erklaerung fuer Confidence-Balken in der Timeline.
    // narrative=true (Default): Backend versucht LLM-Erklaerung via Ollama;
    // bei Fehler bleibt response.Narrative=null und der Tooltip faellt auf die
    // strukturierte Anzeige zurueck (kein Breaking-Change).
    public Task<BrainExplainResponse?> BrainExplainAsync(int cutId, int topN = 3, bool narrative = true, CancellationToken ct = default)
        => GetAsync<BrainExplainResponse>(
            $"/brain/explain/{cutId}?top_n={topN}&narrative={(narrative ? "true" : "false")}",
            ct);

    #region VRAM Telemetry
    // GET /health/vram[?model_id=...] — Histogramm-basierte Performance-Telemetrie pro model_id.
    // Bei modelId=null: Multi-Model-Snapshot (Telemetry.Summary + Telemetry.Models).
    // Bei modelId gesetzt: Single-Entry-Shape (Telemetry.ModelId/Count/DurationMs/...).
    public Task<VramHealthResponse?> GetVramTelemetryAsync(string? modelId = null, CancellationToken ct = default)
    {
        var url = string.IsNullOrWhiteSpace(modelId)
            ? "/health/vram"
            : $"/health/vram?model_id={Uri.EscapeDataString(modelId)}";
        // T5c (S-H1b Audit V2): API surface still typed as multi-model VramHealthResponse.
        // Single-model variant (Telemetry direkt = Entry) wird vom VM aktuell nicht genutzt.
        return GetAsync<VramHealthResponse>(url, ct);
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
        => GetAsync<ModelListResponse>("/models/list", ct);

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

    public async Task<bool> ActivateModelAsync(string name, CancellationToken ct = default)
    {
        try
        {
            var result = await PostAsync<object>("/models/activate", new { name }).ConfigureAwait(false);
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
            var result = await PostAsync<object>("/models/mode", new { mode }).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "UpdateKiModeAsync {Mode} fehlgeschlagen", mode);
            return false;
        }
    }

    public async Task<ModelTestResponse?> TestModelAsync(string name, CancellationToken ct = default)
    {
        try
        {
            return await PostAsync<ModelTestResponse>("/models/test", new { name }).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "TestModelAsync {Name} fehlgeschlagen", name);
            return new ModelTestResponse(false, 0.0, "", ex.Message);
        }
    }

    /// <summary>
    /// LM Studio Refactor 2026-05-17: Modell-Loeschung wird vom Backend
    /// nicht mehr unterstuetzt — LM Studio managed Modelle ueber die Desktop-App.
    /// Der Endpoint liefert HTTP 501. Wir werfen <see cref="NotSupportedException"/>
    /// mit einer User-tauglichen Message damit das UI das anzeigen kann.
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
            using var response = await _http.DeleteAsync(url, token).ConfigureAwait(false);

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

    /// <summary>Setup-Helfer: liefert offenen Response-Stream oder null bei Fehler/Cancel.
    /// LM Studio Refactor 2026-05-17: Wenn Backend mit HTTP 501 antwortet,
    /// werfen wir <see cref="NotSupportedException"/> mit User-tauglicher Message.</summary>
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

    private async Task<T?> DeleteAsync<T>(string url) where T : class
    {
        try
        {
            using var response = await _http.DeleteAsync(url, _shutdownCts.Token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> DeleteWithBodyAsync<T>(string url, object body) where T : class
    {
        try
        {
            // HttpClient.DeleteAsync supports no body; need explicit HttpRequestMessage
            using var request = new HttpRequestMessage(HttpMethod.Delete, url)
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, _shutdownCts.Token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} (with body) fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> PostAsync<T>(string url, object? body) where T : class
    {
        try
        {
            using var response = await _http.PostAsJsonAsync(url, body, JsonOptions, _shutdownCts.Token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex))
        {
            return null;
        }
        catch (Exception ex)
        {
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
            return null;
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
public record GpuStatus(string Name, double VramTotalMb, double VramUsedMb, double TemperatureC, string DriverVersion);
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
    // L-N4: Stem-Separation Outputs — Dict {vocals|instrumental|drums|bass|other -> path}.
    // Gesetzt nach POST /audio/stems/separate. UI rendert STEMS-Badge und
    // "Stems-Ordner oeffnen"-Button wenn nicht null und nicht-leer.
    Dictionary<string, string>? StemsPaths = null);
public record StructureSegment(double StartTime, double EndTime, string Label, double Confidence = 0.0, double EnergyScore = 0.0);
public record SubtrackSegment(double StartTime, double EndTime, double Confidence = 0.0, double? SubBpm = null, string? SubKey = null);
public record SpectralData(int ClipId, List<double> Times, Dictionary<string, List<float>> Bands, List<double> Centroids, Dictionary<string, double[]>? FrequencyRanges = null);
public record AudioAnalysisResult(
    int ClipId,
    double DurationSeconds,
    double Bpm,
    int BeatCount,
    List<BeatData> Beats,
    string? Key = null,
    List<float>? EnergyCurve = null,
    List<StructureSegment>? StructureSegments = null,
    SpectralData? SpectralData = null,
    List<SubtrackSegment>? SubtrackSegments = null,
    List<double>? TempoCurve = null,
    List<double>? OnsetTimes = null,
    List<double>? KickTimes = null,
    List<double>? SnareTimes = null,
    List<double>? HihatTimes = null);
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
    string? TagSource = null);
public record DeleteResponse(int DeletedCount, List<int> NotFoundIds);
public record VideoAnalysisResult(
    int ClipId,
    int SceneCount,
    double AvgMotion,
    List<string> DominantColors,
    List<string> Tags,
    bool HasEmbedding,
    int EmbeddingDim = 1152,
    List<SceneInfo>? Scenes = null,
    MotionData? Motion = null,
    int EmbeddingSamples = 0,
    string? AudioKey = null,
    string? TagSource = null,
    List<string>? MoodTags = null,
    double AvgBrightness = 0.5,
    double AvgSaturation = 0.5,
    double AvgColorTemp = 0.0);
public record CutListResponse(List<CutListEntry> Cuts, double TotalDuration, int CutCount, double AverageCutDuration);
public record CutListEntry(string ClipId, double StartTime, double EndTime, Dictionary<string, object>? Metadata);
public record TimelineResponse(List<TimelineEntry> Entries, double TotalDuration, string? AudioPath);
public record TimelineEntry(string ClipId, string ClipName, string FilePath, double StartTime, double EndTime, double ClipStart, string TriggerType, double TriggerStrength, string? SegmentType = null, double BrainConfidence = 0.0, int? CutId = null);
public record PacingConfig(int AudioClipId, List<int> VideoClipIds, double ExpectedBpm, bool UseMotionMatching, bool UseSemanticMatching, bool UseStructureAwareness, double? DurationLimit, double MinCutInterval = 0.5, TriggerSettings? TriggerSettings = null, bool UseBrain = false, double BrainMinConfidence = 0.0, bool UseKeyMatching = false, bool UseStemPacing = false, string? CanvasPath = null);
public record TriggerSettings(double BeatWeight = 1.0, double OnsetWeight = 0.5, double KickWeight = 1.2, double SnareWeight = 1.0, double HihatWeight = 0.3, double EnergyWeight = 0.8, double EnergyThreshold = 0.6, double MinClipLength = 1.0, double MaxClipLength = 8.0, double OnsetSensitivity = 0.5, double ClipLengthVariation = 0.0, double MaxCutInterval = 10.0, string BeatTriggerMode = "all");

public record BrainSuggestion(int? CutId, string ClipId, double StartTime, double EndTime, double FinalScore, Dictionary<string, double> BrainScores);
public record BrainSuggestResponse(List<BrainSuggestion> Suggestions);
public record PacingPreviewResponse(string PreviewPath, double Duration, string Resolution);
public record BrainFeedbackResponse(string Status, int UpdatedBuckets, int TotalClicks);
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
public record SceneInfo(double StartTime, double EndTime, string SceneType, double Confidence)
{
    public int SceneIndex { get; set; }
}
// L-VIDEO-2 / X1: PeakMotion am Ende mit Default 0.0 fuer backward compat —
// Backend liefert es jetzt im MotionData-Response, frueher wurde es im
// Pydantic-Schema silent gedropped.
public record MotionData(int ClipId, double AvgMotion, List<float> MotionCurve, List<Dictionary<string, object>> PeakFrames, string MotionCategory, double PeakMotion = 0.0);
public record RenderRequest(string OutputPath, string AudioPath, string Quality, int ResolutionWidth, int ResolutionHeight, double Fps, double BitrateMbps = 12.0, bool IncludeAudio = true, string? Encoder = null);
public record RenderProgress(string TaskId, string Status, double Percent, int CurrentFrame, int TotalFrames, double Fps, double ElapsedSeconds, double EtaSeconds, string? OutputPath, string? Error);
