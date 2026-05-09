using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

/// <summary>
/// Abstraktion für die Kommunikation mit dem Python FastAPI Backend.
/// Ermöglicht Mocking in Tests und Austauschbarkeit der Implementierung.
/// </summary>
public interface IApiClient : IDisposable
{
    void BeginShutdown();
    Task<T?> GetAsync<T>(string url, CancellationToken ct = default) where T : class;

    // --- Health ---
    Task<HealthStatus?> GetHealthAsync();
    Task<GpuStatus?> GetGpuStatusAsync();
    Task CleanupGpuAsync();

    // --- Project ---
    Task<ProjectInfo?> CreateProjectAsync(string name, string path);
    Task<ProjectInfo?> OpenProjectAsync(string path);
    Task<StatusResponse?> SaveProjectAsync();
    Task<StatusResponse?> CloseProjectAsync();
    Task<ProjectInfo?> GetProjectInfoAsync();

    // --- Audio ---
    Task<AudioClipInfo?> ImportAudioAsync(string path);
    Task<List<AudioClipInfo>?> GetAudioClipsAsync(int page = 1, int limit = 200);
    Task<AudioAnalysisResult?> AnalyzeAudioAsync(int clipId);
    Task<List<BeatData>?> GetBeatsAsync(int clipId);
    Task<StemResult?> SeparateStemsAsync(int clipId, string model = "UVR-MDX-NET-Inst_HQ_3.onnx");
    Task<DeleteResponse?> DeleteAudioClipAsync(int clipId);
    Task<DeleteResponse?> DeleteAudioClipsBatchAsync(List<int> clipIds);

    // --- Audio (Erweitert) ---
    Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3);
    Task<List<StructureSegment>?> GetStructureAsync(int clipId);
    Task<SpectralData?> GetSpectralAsync(int clipId);

    // --- Video ---
    Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths);
    Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200, CancellationToken cancellationToken = default);
    Task<byte[]?> GetThumbnailAsync(int clipId, CancellationToken cancellationToken = default);
    Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId);
    Task<List<SceneInfo>?> GetScenesAsync(int clipId);
    Task<MotionData?> GetMotionAsync(int clipId);
    Task<DeleteResponse?> DeleteVideoClipAsync(int clipId);
    Task<DeleteResponse?> DeleteVideoClipsBatchAsync(List<int> clipIds);

    // --- Pacing ---
    Task<CutListResponse?> GenerateCutListAsync(PacingConfig config);
    Task<TimelineResponse?> GetTimelineAsync();
    Task<StatusResponse?> UpdateTimelineAsync(List<TimelineEntryModel> entries);
    Task<PacingPreviewResponse?> GenerateTimelinePreviewAsync(double startSec, double duration, CancellationToken ct = default);

    // --- Render ---
    Task<RenderProgress?> StartRenderAsync(RenderRequest request);
    Task<RenderProgress?> GetRenderStatusAsync(string taskId);
    Task CancelRenderAsync(string taskId);
    Task ShutdownAsync();

    // --- Brain ---
    Task<BrainSuggestResponse?> BrainSuggestAsync(int audioClipId, List<int> videoClipIds, int topN = 20);
    Task<BrainFeedbackResponse?> BrainFeedbackAsync(int cutId, string rating);
    Task<BrainLearningSessionResponse?> BrainLearningSessionAsync();
    Task<BrainStatsResponse?> BrainStatsAsync();
    Task<BrainResetResponse?> BrainResetRequestAsync();
    Task<BrainResetResponse?> BrainResetConfirmAsync(string confirmationToken);
    Task<BrainExplainResponse?> BrainExplainAsync(int cutId, int topN = 3, CancellationToken ct = default);

    #region VRAM Telemetry
    // GET /health/vram — Histogramm-basierte Performance-Telemetrie pro model_id.
    // Gibt bei modelId=null das Multi-Model-Snapshot zurück (Summary + Models),
    // bei gesetztem modelId die single-entry Shape.
    Task<VramTelemetryResponse?> GetVramTelemetryAsync(string? modelId = null, CancellationToken ct = default);
    #endregion
}
