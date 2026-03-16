using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;

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

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public ApiClient(HttpClient http, ILogger<ApiClient> logger)
    {
        _http = http;
        _http.Timeout = TimeSpan.FromMinutes(10);
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
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, CreateRequestCancellationToken()).ConfigureAwait(false);
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

    public async Task<StemResult?> SeparateStemsAsync(int clipId, string model = "UVR-MDX-NET-Inst_HQ_3.onnx")
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

    public async Task<byte[]?> GetThumbnailAsync(int clipId, CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, $"/video/thumbnails/{clipId}");

        try
        {
            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseContentRead, CreateRequestCancellationToken(cancellationToken)).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
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

    public async Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId)
        => await PostAsync<VideoAnalysisResult>("/video/analyze", new { clip_id = clipId }).ConfigureAwait(false);

    public async Task<List<SceneInfo>?> GetScenesAsync(int clipId)
        => await GetAsync<List<SceneInfo>>($"/video/scenes/{clipId}").ConfigureAwait(false);

    public async Task<MotionData?> GetMotionAsync(int clipId)
        => await GetAsync<MotionData>($"/video/motion/{clipId}").ConfigureAwait(false);

    // --- Pacing ---

    public async Task<CutListResponse?> GenerateCutListAsync(PacingConfig config)
        => await PostAsync<CutListResponse>("/pacing/generate", config).ConfigureAwait(false);

    public async Task<TimelineResponse?> GetTimelineAsync()
        => await GetAsync<TimelineResponse>("/pacing/timeline").ConfigureAwait(false);

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

    // --- Generische Helfer ---

    private async Task<T?> GetAsync<T>(string url, CancellationToken cancellationToken = default) where T : class
    {
        try
        {
            using var response = await _http.GetAsync(url, CreateRequestCancellationToken(cancellationToken)).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, cancellationToken).ConfigureAwait(false);
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

    private async Task<T?> PostAsync<T>(string url, object? body) where T : class
    {
        try
        {
            using var response = await _http.PostAsJsonAsync(url, body, JsonOptions, CreateRequestCancellationToken()).ConfigureAwait(false);
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

    private CancellationToken CreateRequestCancellationToken(CancellationToken cancellationToken = default)
        => cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token).Token
            : _shutdownCts.Token;

    private bool IsExpectedCancellation(Exception ex, CancellationToken cancellationToken = default)
        => ex is OperationCanceledException
           || (_isShuttingDown && ex is ObjectDisposedException)
           || cancellationToken.IsCancellationRequested
           || _shutdownCts.IsCancellationRequested;
}

// --- API Response Models ---

public record HealthStatus(string Status, double UptimeSeconds, bool GpuAvailable);
public record GpuStatus(string Name, double VramTotalMb, double VramUsedMb, double TemperatureC, string DriverVersion);
public record StatusResponse(bool Success, string Message);
public record ProjectInfo(string Name, string Path, int AudioCount, int VideoCount, bool HasTimeline, string? CreatedAt = null, string? ModifiedAt = null);
public record AudioClipInfo(int Id, string Name, string Path, double DurationSeconds, int SampleRate, int Channels, string Format, double Bpm = 0.0, string? Key = null, int BeatCount = 0, bool IsAnalyzed = false);
public record StructureSegment(double StartTime, double EndTime, string Label, double Confidence = 0.0);
public record SpectralData(int ClipId, Dictionary<string, List<float>> Bands, Dictionary<string, List<double>>? FrequencyRanges = null);
public record AudioAnalysisResult(int ClipId, double DurationSeconds, double Bpm, int BeatCount, List<BeatData> Beats, string? Key = null, List<float>? EnergyCurve = null, List<StructureSegment>? StructureSegments = null, SpectralData? SpectralData = null);
public record BeatData(double Time, double Strength, string BeatType);
public record StemResult(int ClipId, string? VocalsPath, string? InstrumentalPath, string? DrumsPath, string? BassPath, string? OtherPath, string ModelUsed);
public record VideoClipInfo(int Id, string Name, string Path, double DurationSeconds, int Width, int Height, double Fps, string Codec, bool ThumbnailAvailable, List<string> Tags, bool IsAnalyzed = false);
public record VideoAnalysisResult(int ClipId, int SceneCount, double AvgMotion, List<string> DominantColors, List<string> Tags, bool HasEmbedding, int EmbeddingDim = 1152, List<SceneInfo>? Scenes = null, MotionData? Motion = null);
public record CutListResponse(List<CutListEntry> Cuts, double TotalDuration, int CutCount, double AverageCutDuration);
public record CutListEntry(string ClipId, double StartTime, double EndTime, Dictionary<string, object>? Metadata);
public record TimelineResponse(List<TimelineEntry> Entries, double TotalDuration, string? AudioPath);
public record TimelineEntry(string ClipId, string ClipName, string FilePath, double StartTime, double EndTime, double ClipStart, string TriggerType, double TriggerStrength, string? SegmentType = null);
public record PacingConfig(int AudioClipId, List<int> VideoClipIds, double ExpectedBpm, bool UseMotionMatching, bool UseStructureAwareness, double? DurationLimit, double MinCutInterval = 0.5, TriggerSettings? TriggerSettings = null);
public record TriggerSettings(double BeatWeight = 1.0, double OnsetWeight = 0.5, double KickWeight = 1.2, double SnareWeight = 1.0, double HihatWeight = 0.3, double EnergyWeight = 0.8, double EnergyThreshold = 0.6, double MinClipLength = 1.0, double MaxClipLength = 8.0, double OnsetSensitivity = 0.5);
public record WaveformData(int ClipId, int SampleRate, List<List<float>> Bands, double DurationSeconds);
public record SceneInfo(double StartTime, double EndTime, string SceneType, double Confidence);
public record MotionData(int ClipId, double AvgMotion, List<float> MotionCurve, List<Dictionary<string, object>> PeakFrames, string MotionCategory);
public record RenderRequest(string OutputPath, string AudioPath, string Quality, int ResolutionWidth, int ResolutionHeight, double Fps, double BitrateMbps = 12.0, bool IncludeAudio = true, string? Encoder = null);
public record RenderProgress(string TaskId, string Status, double Percent, int CurrentFrame, int TotalFrames, double Fps, double ElapsedSeconds, double EtaSeconds, string? OutputPath, string? Error);
