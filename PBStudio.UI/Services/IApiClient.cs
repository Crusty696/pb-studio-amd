namespace PBStudio.UI.Services;

/// <summary>
/// Abstraktion für die Kommunikation mit dem Python FastAPI Backend.
/// Ermöglicht Mocking in Tests und Austauschbarkeit der Implementierung.
/// </summary>
public interface IApiClient
{
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

    // --- Audio (Erweitert) ---
    Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3);
    Task<List<Dictionary<string, object>>?> GetStructureAsync(int clipId);
    Task<Dictionary<string, object>?> GetSpectralAsync(int clipId);

    // --- Video ---
    Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths);
    Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200);
    Task<byte[]?> GetThumbnailAsync(int clipId);
    Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId);
    Task<List<SceneInfo>?> GetScenesAsync(int clipId);
    Task<MotionData?> GetMotionAsync(int clipId);

    // --- Pacing ---
    Task<CutListResponse?> GenerateCutListAsync(PacingConfig config);
    Task<TimelineResponse?> GetTimelineAsync();

    // --- Render ---
    Task<RenderProgress?> StartRenderAsync(RenderRequest request);
    Task<RenderProgress?> GetRenderStatusAsync(string taskId);
    Task CancelRenderAsync(string taskId);
}
