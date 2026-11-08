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
}
