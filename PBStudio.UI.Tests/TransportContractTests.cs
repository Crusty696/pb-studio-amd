using System.Text.Json;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using Generated = PBStudio.UI.Generated;

namespace PBStudio.UI.Tests;

[TestClass]
public sealed class TransportContractTests
{
    private static readonly JsonSerializerOptions SnakeCaseJson = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    [TestMethod]
    public void AudioAdapter_PreservesGeneratedPartialResultAndEvidence()
    {
        var evidence = JsonSerializer.Deserialize<JsonElement>(
            """{"chunk_0":{"status":"completed"}}""");
        var transport = new Generated.AudioAnalysisResult(
            analysis_status: "partial",
            beat_count: null,
            beats: [new Generated.BeatData("kick", 0.75, 1.25)],
            bpm: null,
            chunk_evidence: evidence,
            clip_id: 17,
            downbeat_provenance: null,
            downbeats: [0.5],
            duration_seconds: 42.0,
            energy_curve: [0.1, 0.9],
            hihat_times: null,
            key: "Am",
            kick_times: [1.25],
            onset_times: null,
            snare_times: null,
            spectral_data: null,
            stage_errors: new Dictionary<string, string> { ["spectral"] = "unavailable" },
            stage_status: new Dictionary<string, string> { ["beats"] = "completed" },
            structure_segments: null,
            subtrack_segments: null,
            tempo_curve: [120.0]);

        var result = AudioAnalysisResult.FromTransport(transport);

        Assert.AreEqual(17, result.ClipId);
        Assert.AreEqual(0.0, result.Bpm);
        Assert.AreEqual(1, result.BeatCount);
        Assert.AreEqual("kick", result.Beats.Single().BeatType);
        Assert.AreEqual("partial", result.AnalysisStatus);
        Assert.AreEqual("completed", result.StageStatus!["beats"]);
        Assert.AreEqual("unavailable", result.StageErrors!["spectral"]);
        Assert.AreEqual(
            "completed",
            result.ChunkEvidence!["chunk_0"].GetProperty("status").GetString());
    }

    [TestMethod]
    public void SpectralAdapter_PreservesEveryGeneratedField()
    {
        var transport = new Generated.SpectralData(
            band_means: new Dictionary<string, double> { ["mid"] = 0.4 },
            band_variances: new Dictionary<string, double> { ["mid"] = 0.05 },
            bands: new Dictionary<string, IList<double>> { ["mid"] = new List<double> { 0.2, 0.6 } },
            centroids: [1500.0, 1750.0],
            clip_id: 9,
            events: [new { type = "rise" }],
            frequency_ranges: new Dictionary<string, IList<double>> { ["mid"] = new List<double> { 250, 4000 } },
            times: [0.0, 0.5]);

        var result = SpectralDataModel.FromTransport(transport);

        Assert.AreEqual(9, result.ClipId);
        CollectionAssert.AreEqual(new[] { 0.0, 0.5 }, result.Times);
        CollectionAssert.AreEqual(new[] { 0.2, 0.6 }, result.Bands["mid"]);
        CollectionAssert.AreEqual(new[] { 1500.0, 1750.0 }, result.Centroids);
        CollectionAssert.AreEqual(new[] { 250.0, 4000.0 }, result.FrequencyRanges["mid"]);
        Assert.AreEqual(0.4, result.BandMeans["mid"]);
        Assert.AreEqual(0.05, result.BandVariances["mid"]);
        Assert.AreEqual(1, result.Events.Count);
    }

    [TestMethod]
    public void SingleVramAdapter_ProducesOneModelSnapshotWithoutShapeDrift()
    {
        var budget = new Generated.VramBudgetStats(
            available_mb: 12000,
            committed_mb: 256,
            loaded_models: 1,
            max_vram_mb: 16177,
            models: null,
            reserved_mb: 512,
            reserved_models: 1,
            usable_vram_mb: 15000);
        var entry = new Generated.VramTelemetryEntry(
            count: 7,
            duration_ms: new Generated.VramDurationStats(null, null, null, null),
            failure_count: 1,
            last_error: "oom",
            model_id: "siglip",
            success_count: 6,
            vram_peak_mb: new Generated.VramPeakStats(null, 2048, 1024));
        var single = new Generated.VramHealthSingleResponse(budget, "ok", entry);

        var snapshot = single.ToMultiModelSnapshot();

        Assert.AreSame(budget, snapshot.Budget);
        Assert.AreEqual("ok", snapshot.Status);
        Assert.AreSame(entry, snapshot.Telemetry.Models!["siglip"]);
        Assert.AreEqual(1, snapshot.Telemetry.Summary.Models_tracked);
        Assert.AreEqual(7, snapshot.Telemetry.Summary.Observations);
    }

    [TestMethod]
    public void ResultDtos_DeserializeNegativeBackendTruth()
    {
        var cleanup = JsonSerializer.Deserialize<GpuCleanupResponse>(
            """{"success":false,"freed_mb":0,"error":"model busy"}""",
            SnakeCaseJson);
        var save = JsonSerializer.Deserialize<StatusResponse>(
            """{"success":false,"message":"disk full"}""",
            SnakeCaseJson);

        Assert.IsNotNull(cleanup);
        Assert.IsFalse(cleanup.Success);
        Assert.AreEqual(0, cleanup.FreedMb);
        Assert.AreEqual("model busy", cleanup.Error);
        Assert.IsNotNull(save);
        Assert.IsFalse(save.Success);
        Assert.AreEqual("disk full", save.Message);
    }
}
