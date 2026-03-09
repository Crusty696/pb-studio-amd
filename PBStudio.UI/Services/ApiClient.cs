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

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public ApiClient(HttpClient http, ILogger<ApiClient> logger)
    {
        _http = http;
        _logger = logger;
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
    {
        return await GetAsync<GpuStatus>("/gpu/status").ConfigureAwait(false);
    }

    public async Task CleanupGpuAsync()
        => await PostAsync<object>("/gpu/cleanup", null).ConfigureAwait(false);

    // --- Audio ---

    public async Task<AudioClipInfo?> ImportAudioAsync(string path)
    {
        return await PostAsync<AudioClipInfo>("/audio/import", new { path }).ConfigureAwait(false);
    }

    public async Task<List<AudioClipInfo>?> GetAudioClipsAsync(int page = 1, int limit = 200)
    {
        return await GetAsync<List<AudioClipInfo>>($"/audio/clips?page={page}&limit={limit}").ConfigureAwait(false);
    }

    public async Task<AudioAnalysisResult?> AnalyzeAudioAsync(int clipId)
    {
        return await PostAsync<AudioAnalysisResult>("/audio/analyze", new { clip_id = clipId }).ConfigureAwait(false);
    }

    public async Task<List<BeatData>?> GetBeatsAsync(int clipId)
    {
        return await GetAsync<List<BeatData>>($"/audio/beats/{clipId}").ConfigureAwait(false);
    }

    public async Task<StemResult?> SeparateStemsAsync(int clipId, string model = "UVR-MDX-NET-Inst_HQ_3.onnx")
    {
        return await PostAsync<StemResult>("/audio/stems/separate", new { clip_id = clipId, model }).ConfigureAwait(false);
    }

    // --- Audio (Erweitert) ---

    public async Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3)
    {
        return await GetAsync<WaveformData>($"/audio/waveform/{clipId}?bands={bands}").ConfigureAwait(false);
    }

    public async Task<List<Dictionary<string, object>>?> GetStructureAsync(int clipId)
    {
        return await GetAsync<List<Dictionary<string, object>>>($"/audio/structure/{clipId}").ConfigureAwait(false);
    }

    public async Task<Dictionary<string, object>?> GetSpectralAsync(int clipId)
    {
        return await GetAsync<Dictionary<string, object>>($"/audio/spectral/{clipId}").ConfigureAwait(false);
    }

    // --- Video ---

    public async Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths)
    {
        return await PostAsync<List<VideoClipInfo>>("/video/import", new { paths }).ConfigureAwait(false);
    }

    public async Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200)
    {
        return await GetAsync<List<VideoClipInfo>>($"/video/clips?page={page}&limit={limit}").ConfigureAwait(false);
    }

    public async Task<byte[]?> GetThumbnailAsync(int clipId)
    {
        try
        {
            return await _http.GetByteArrayAsync($"/video/thumbnails/{clipId}").ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Thumbnail-Abruf fehlgeschlagen: {ClipId}", clipId);
            return null;
        }
    }

    public async Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId)
    {
        return await PostAsync<VideoAnalysisResult>("/video/analyze", new { clip_id = clipId }).ConfigureAwait(false);
    }

    public async Task<List<SceneInfo>?> GetScenesAsync(int clipId)
    {
        return await GetAsync<List<SceneInfo>>($"/video/scenes/{clipId}").ConfigureAwait(false);
    }

    public async Task<MotionData?> GetMotionAsync(int clipId)
    {
        return await GetAsync<MotionData>($"/video/motion/{clipId}").ConfigureAwait(false);
    }

    // --- Pacing ---

    public async Task<CutListResponse?> GenerateCutListAsync(PacingConfig config)
    {
        return await PostAsync<CutListResponse>("/pacing/generate", config).ConfigureAwait(false);
    }

    public async Task<TimelineResponse?> GetTimelineAsync()
    {
        return await GetAsync<TimelineResponse>("/pacing/timeline").ConfigureAwait(false);
    }

    // --- Render ---

    public async Task<RenderProgress?> StartRenderAsync(RenderRequest request)
    {
        return await PostAsync<RenderProgress>("/render/start", request).ConfigureAwait(false);
    }

    public async Task<RenderProgress?> GetRenderStatusAsync(string taskId)
    {
        return await GetAsync<RenderProgress>($"/render/status/{taskId}").ConfigureAwait(false);
    }

    public async Task CancelRenderAsync(string taskId)
    {
        await PostAsync<object>($"/render/cancel/{taskId}", null).ConfigureAwait(false);
    }

    // --- Generische Helfer ---

    private async Task<T?> GetAsync<T>(string url) where T : class
    {
        try
        {
            var response = await _http.GetAsync(url).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);
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
            var response = await _http.PostAsJsonAsync(url, body, JsonOptions).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "POST {Url} fehlgeschlagen", url);
            return null;
        }
    }
}

// --- API Response Models ---

public record HealthStatus(string Status, double UptimeSeconds, bool GpuAvailable);
public record GpuStatus(string Name, double VramTotalMb, double VramUsedMb, double TemperatureC, string DriverVersion);
public record AudioClipInfo(int Id, string Name, string Path, double DurationSeconds, int SampleRate, int Channels, string Format);
public record AudioAnalysisResult(int ClipId, double DurationSeconds, double Bpm, int BeatCount, List<BeatData> Beats, string? Key = null, List<float> EnergyCurve = null!, List<Dictionary<string, object>>? StructureSegments = null, Dictionary<string, object>? SpectralData = null);
public record BeatData(double Time, double Strength, string BeatType);
public record StemResult(int ClipId, string? VocalsPath, string? InstrumentalPath, string? DrumsPath, string? BassPath, string? OtherPath, string ModelUsed);
public record VideoClipInfo(int Id, string Name, string Path, double DurationSeconds, int Width, int Height, double Fps, string Codec, bool ThumbnailAvailable, List<string> Tags);
public record VideoAnalysisResult(int ClipId, int SceneCount, double AvgMotion, List<string> DominantColors, List<string> Tags, bool HasEmbedding, int EmbeddingDim = 1152);
public record CutListResponse(List<CutListEntry> Cuts, double TotalDuration, int CutCount, double AverageCutDuration);
public record CutListEntry(string ClipId, double StartTime, double EndTime, Dictionary<string, object>? Metadata);
public record TimelineResponse(List<TimelineEntry> Entries, double TotalDuration, string? AudioPath);
public record TimelineEntry(string ClipId, string ClipName, string FilePath, double StartTime, double EndTime, double ClipStart, string TriggerType, double TriggerStrength, string? SegmentType = null);
public record PacingConfig(int AudioClipId, List<int> VideoClipIds, double ExpectedBpm, bool UseMotionMatching, bool UseStructureAwareness, double? DurationLimit, double MinCutInterval = 0.5, TriggerSettings? TriggerSettings = null);
public record TriggerSettings(double BeatWeight = 1.0, double OnsetWeight = 0.5, double KickWeight = 1.2, double SnareWeight = 1.0, double HihatWeight = 0.3, double EnergyWeight = 0.8, double EnergyThreshold = 0.6, double MinClipLength = 1.0, double MaxClipLength = 8.0, double OnsetSensitivity = 0.5);
public record WaveformData(int ClipId, int SampleRate, List<List<float>> Bands, double DurationSeconds);
public record SceneInfo(double StartTime, double EndTime, string SceneType, double Confidence);
public record MotionData(int ClipId, double AvgMotion, List<float> MotionCurve, List<Dictionary<string, object>> PeakFrames, string MotionCategory);
public record RenderRequest(string OutputPath, string AudioPath, string Quality, int ResolutionWidth, int ResolutionHeight, double Fps, double BitrateMbps = 12.0, bool IncludeAudio = true);
public record RenderProgress(string TaskId, string Status, double Percent, int CurrentFrame, int TotalFrames, double ElapsedSeconds, double EtaSeconds, string? OutputPath, string? Error);
