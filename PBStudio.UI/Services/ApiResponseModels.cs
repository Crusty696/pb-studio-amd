using System.Text.Json;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

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
    Dictionary<string, JsonElement>? DownbeatProvenance = null,
    // Herkunft und Plausibilitaet des Beat-Rasters (Audit 2026-08-30, C-3).
    // Bis dahin trug ausschliesslich der Downbeat-Pfad eine Provenance,
    // waehrend BPM und Beats - die Werte, die die Schnittzeitpunkte setzen -
    // ohne jede Herkunftsangabe ausgeliefert wurden.
    Dictionary<string, JsonElement>? BeatGridProvenance = null,
    // Das Beatgrid als Regel: Anker plus Tempo, aus denen jede Beat-Position
    // folgt - getrennt von der Zeitmarkenliste in Beats, die aus
    // librosa.beat_track stammt und den Anschlaegen folgt statt eine Regel
    // zu sein.
    Dictionary<string, JsonElement>? BeatGrid = null,
    Dictionary<string, JsonElement>? FeatureProvenance = null)
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
            ToJsonDictionary(value.Downbeat_provenance),
            ToJsonDictionary(value.Beat_grid_provenance),
            ToJsonDictionary(value.Beat_grid),
            ToJsonDictionary(value.Feature_provenance));
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
public record PacingConfig(int AudioClipId, List<int> VideoClipIds, double ExpectedBpm, bool UseMotionMatching, bool UseSemanticMatching, bool UseStructureAwareness, double? DurationLimit, double MinCutInterval = 0.5, TriggerSettings? TriggerSettings = null, bool UseBrain = false, double BrainMinConfidence = 0.0, bool UseKeyMatching = false, bool UseStemPacing = false, string? CanvasPath = null, string? RequestId = null);
public record TriggerSettings(double BeatWeight = 1.0, double OnsetWeight = 0.5, double KickWeight = 1.2, double SnareWeight = 1.0, double HihatWeight = 0.3, double EnergyWeight = 0.8, double EnergyThreshold = 0.6, double MinClipLength = 1.0, double MaxClipLength = 8.0, double OnsetSensitivity = 0.5, double ClipLengthVariation = 0.0, double MaxCutInterval = 10.0, string BeatTriggerMode = "all");

public record BrainSuggestion(int? CutId, string ClipId, double StartTime, double EndTime, double FinalScore, Dictionary<string, double> BrainScores);
public record BrainSuggestResponse(List<BrainSuggestion> Suggestions);
public record PacingPreviewResponse(
    string PreviewPath,
    double Duration,
    string Resolution,
    bool AudioIncluded = false);
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
    List<string>? ColdStartAxesList = null,
    string? WeightSemanticsVersion = null,
    int ArchivedObservations = 0,
    string? MigrationReason = null);
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
    string? ValidationStatus = null,
    double ProgressPercent = 0.0,
    string? ValidationPhase = null,
    double? ValidationProgress = null);
