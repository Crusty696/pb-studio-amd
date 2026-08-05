using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

/// <summary>
/// Abstraktion für die Kommunikation mit dem Python FastAPI Backend.
/// Ermöglicht Mocking in Tests und Austauschbarkeit der Implementierung.
/// </summary>
public interface IApiClient : IDisposable
{
    void BeginShutdown();

    /// <summary>
    /// Grund des zuletzt fehlgeschlagenen Requests aus dem <c>detail</c>-Feld des
    /// Backend-Body. Vor dem Fix (Audit 2026-08-05, C-1) wurde dieser Body verworfen —
    /// jedes 4xx blieb dadurch fuer User und Log grundlos. ViewModels sollen diesen
    /// Text anzeigen statt einer generischen Fehlermeldung.
    /// </summary>
    string? LastErrorDetail { get; }

    Task<T?> GetAsync<T>(string url, CancellationToken ct = default) where T : class;

    // --- Health ---
    Task<HealthStatus?> GetHealthAsync();
    Task<GpuStatus?> GetGpuStatusAsync();
    Task<GpuCleanupResponse?> CleanupGpuAsync(CancellationToken ct = default);

    // --- Project ---
    Task<ProjectInfo?> CreateProjectAsync(string name, string path);
    Task<ProjectInfo?> OpenProjectAsync(string path);
    Task<StatusResponse?> SaveProjectAsync();
    Task<StatusResponse?> CloseProjectAsync();
    Task<ProjectInfo?> GetProjectInfoAsync();

    // --- Audio ---
    Task<AudioClipInfo?> ImportAudioAsync(string path);
    Task<List<AudioClipInfo>?> GetAudioClipsAsync(int page = 1, int limit = 200);
    Task<AudioAnalysisResult?> AnalyzeAudioAsync(int clipId, CancellationToken cancellationToken = default);
    Task<List<BeatData>?> GetBeatsAsync(int clipId);
    Task<StemResult?> SeparateStemsAsync(int clipId, string model = "htdemucs.yaml", CancellationToken cancellationToken = default);

    Task<DeleteResponse?> DeleteAudioClipAsync(int clipId, CancellationToken cancellationToken = default);
    Task<DeleteResponse?> DeleteAudioClipsBatchAsync(List<int> clipIds, CancellationToken cancellationToken = default);

    // --- Audio (Erweitert) ---
    Task<WaveformData?> GetWaveformAsync(int clipId, int bands = 3);
    Task<List<StructureSegment>?> GetStructureAsync(int clipId);
    Task<PBStudio.UI.Generated.SpectralData?> GetSpectralAsync(int clipId);
    // AP3.5 (Audit 2026-06-10): war nur auf ApiClient public — zwang TimelineViewModel,
    // den konkreten ApiClient zu injizieren (zweite HttpClient-Instanz, BeginShutdown
    // erreichte sie nie). Additiv, einziger Implementierer ApiClient hat die Methode bereits.
    Task<List<double>?> GetOnsetsAsync(int clipId);

    // --- Video ---
    Task<List<VideoClipInfo>?> ImportVideosAsync(List<string> paths);
    Task<List<VideoClipInfo>?> GetVideoClipsAsync(int page = 1, int limit = 200, CancellationToken cancellationToken = default);
    Task<byte[]?> GetThumbnailAsync(int clipId, CancellationToken cancellationToken = default);
    Task<VideoAnalysisResult?> AnalyzeVideoAsync(int clipId, bool detectScenes = true, bool analyzeMotion = true, bool generateEmbeddings = true, bool generateCaptions = true, CancellationToken cancellationToken = default);
    Task<List<SceneInfo>?> GetScenesAsync(int clipId);
    Task<MotionData?> GetMotionAsync(int clipId);
    Task<ThumbstripResponse?> GetThumbStripAsync(int clipId, int n = 8, CancellationToken cancellationToken = default);
    Task<ClipwaveResponse?> GetClipWaveAsync(int clipId, int n = 256, CancellationToken cancellationToken = default);
    Task<DeleteResponse?> DeleteVideoClipAsync(int clipId, CancellationToken cancellationToken = default);
    Task<DeleteResponse?> DeleteVideoClipsBatchAsync(List<int> clipIds, CancellationToken cancellationToken = default);

    // --- Pacing ---
    Task<CutListResponse?> GenerateCutListAsync(PacingConfig config, CancellationToken cancellationToken = default);
    Task<TimelineResponse?> GetTimelineAsync(CancellationToken cancellationToken = default);
    Task<StatusResponse?> UpdateTimelineAsync(List<TimelineEntryModel> entries, CancellationToken cancellationToken = default);
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
    Task<BrainExplainResponse?> BrainExplainAsync(int cutId, int topN = 3, bool narrative = true, CancellationToken ct = default);

    #region VRAM Telemetry
    // GET /health/vram — Histogramm-basierte Performance-Telemetrie pro model_id.
    // Bestehender Multi-Modell-UI-Vertrag; Einzelmodell-Transport wird intern
    // korrekt deserialisiert und anschließend adaptiert.
    Task<VramHealthResponse?> GetVramTelemetryAsync(string? modelId = null, CancellationToken ct = default);
    Task<VramHealthResponse?> GetVramTelemetrySnapshotAsync(CancellationToken ct = default);
    Task<VramHealthSingleResponse?> GetVramModelTelemetryAsync(string modelId, CancellationToken ct = default);
    Task<VramLimitResponse?> UpdateVramLimitAsync(int limitMb, CancellationToken ct = default);
    #endregion


    #region Model Manager
    // ----------------------------------------------------------------------
    // Providerübergreifendes Modellinventar und -management.
    // Endpoints im Backend: backend/routers/models_router.py
    //   GET    /models/list            -> installierte Modelle
    //   GET    /models/available       -> live verifizierte Downloads + Discover
    //   POST   /models/pull            -> SSE-Stream "event: pull_progress\ndata: {...}\n\n"
    //   DELETE /models/{name:path}     -> Modell loeschen
    //   GET    /models/recommendations -> Auto-Selection-Empfehlung fuer Task+Mode
    // ----------------------------------------------------------------------

    /// <summary>Providergebundenes Live-Inventar. Liefert null bei Transport-Fehler.</summary>
    Task<ModelListResponse?> GetInstalledModelsAsync(CancellationToken ct = default);

    /// <summary>Verifizierte Downloadzustände und allgemeine Discover-Aktionen.</summary>
    Task<AvailableModelsResponse?> GetAvailableModelsAsync(CancellationToken ct = default);

    /// <summary>Streamt Pull-Progress fuer einen Modell-Download (SSE event=pull_progress).
    /// Letztes Event setzt <see cref="PullProgressEvent.IsTerminal"/>=true (status=success ODER Error).</summary>
    IAsyncEnumerable<PullProgressEvent> PullModelAsync(string name, CancellationToken ct = default);

    /// <summary>Loescht ein installiertes Ollama-Modell.</summary>
    Task<bool> DeleteModelAsync(string name, CancellationToken ct = default);

    /// <summary>Empfehlung welches Modell die Auto-Selection fuer Task+Mode waehlen wuerde.</summary>
    Task<ModelRecommendationResponse?> GetModelRecommendationAsync(string task = "video_captioning", string mode = "balance", CancellationToken ct = default);

    /// <summary>Aktiviert das Modell persistent im Backend fuer alle passenden Tasks.</summary>
    Task<bool> ActivateModelAsync(string name, string provider, CancellationToken ct = default);

    /// <summary>Aktualisiert den KI-Modus persistent im Backend.</summary>
    Task<bool> UpdateKiModeAsync(string mode, CancellationToken ct = default);

    /// <summary>Fuehrt einen Inferenz-Smoke-Test auf der AMD-GPU durch.</summary>
    Task<ModelTestResponse?> TestModelAsync(string name, string provider, CancellationToken ct = default);
    #endregion

    #region Chat
    // ----------------------------------------------------------------------
    // KI-Chat-Endpoints (Ollama Tool-Use, Phase 2026-05-16).
    // Backend: backend/routers/chat_router.py
    //   POST   /chat/message   -> SSE-Stream (event: model|text|tool_call|tool_result|error|done)
    //   GET    /chat/tools     -> Tool-Inventar
    //   DELETE /chat/history   -> Server-Side History leeren
    // ----------------------------------------------------------------------

    /// <summary>Streamt ChatStreamEvents fuer eine User-Message. Mode = speed|balance|quality.</summary>
    IAsyncEnumerable<ChatStreamEvent> SendChatMessageAsync(
        string message,
        IReadOnlyList<ChatMessage>? history = null,
        string mode = "balance",
        bool saveHistory = true,
        CancellationToken ct = default);

    /// <summary>Approves or rejects server-stored tool arguments by one-time ID.</summary>
    Task<bool> DecideChatToolConfirmationAsync(
        string confirmationId, bool approve, CancellationToken ct = default);

    /// <summary>Leert die Server-Side Chat-History.</summary>
    Task<bool> ClearChatHistoryAsync(CancellationToken ct = default);
    #endregion
}
