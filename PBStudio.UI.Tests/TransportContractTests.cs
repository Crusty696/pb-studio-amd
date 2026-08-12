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
    public void AudioDtos_DeserializeEveryReceiptAndAttemptFieldIncludingNullableV0()
    {
        const string receipts = """
            {
              "beats": {
                "receipt_version": 1,
                "stage_id": "beats",
                "requested": true,
                "status": "failed",
                "input_fingerprint": "input-sha",
                "config_fingerprint": "config-sha",
                "artifact_ref": "ai_data_json.beats_json",
                "artifact_sha256": "artifact-sha",
                "artifact_valid": false,
                "started_at_utc": "2026-08-12T10:00:00Z",
                "finished_at_utc": "2026-08-12T10:00:01Z",
                "error_code": "beat_failed",
                "error_message": "Beat provider failed",
                "provider": "DmlExecutionProvider",
                "model_id": "beatnet",
                "attempts": [{
                  "provider": "DmlExecutionProvider",
                  "model_id": "beatnet",
                  "task": "beat_detection",
                  "mode": "balance",
                  "required_capabilities": ["beats"],
                  "verified_capabilities": ["beats"],
                  "source": "manifest",
                  "reason": "selected",
                  "selected_at": "2026-08-12T10:00:00Z"
                }],
                "correlation_id": "corr-17"
              },
              "key": {
                "receipt_version": 0,
                "stage_id": "key",
                "requested": true,
                "status": "interrupted",
                "input_fingerprint": null,
                "config_fingerprint": null,
                "artifact_ref": null,
                "artifact_sha256": null,
                "artifact_valid": null,
                "started_at_utc": null,
                "finished_at_utc": null,
                "error_code": null,
                "error_message": "legacy interruption",
                "provider": null,
                "model_id": null,
                "attempts": [],
                "correlation_id": null
              }
            }
            """;
        var analysisJson = $$"""
            {"clip_id":17,"duration_seconds":42,"bpm":0,"beat_count":0,"beats":[],"analysis_status":"failed","stage_status":{"beats":"failed","key":"interrupted"},"stage_errors":{"beats":"Beat provider failed","key":"legacy interruption"},"stage_receipts":{{receipts}}}
            """;
        var clipJson = $$"""
            {"id":17,"name":"mix","path":"C:\\media\\mix.wav","duration_seconds":42,"sample_rate":44100,"channels":2,"format":"wav","analysis_status":"failed","stage_status":{"beats":"failed","key":"interrupted"},"stage_errors":{"beats":"Beat provider failed","key":"legacy interruption"},"stage_receipts":{{receipts}}}
            """;

        var result = JsonSerializer.Deserialize<AudioAnalysisResult>(analysisJson, SnakeCaseJson);
        var clip = JsonSerializer.Deserialize<AudioClipInfo>(clipJson, SnakeCaseJson);

        Assert.IsNotNull(result);
        Assert.IsNotNull(clip);
        var receipt = result.StageReceipts!["beats"];
        Assert.AreEqual(1, receipt.ReceiptVersion);
        Assert.AreEqual("beats", receipt.StageId);
        Assert.IsTrue(receipt.Requested);
        Assert.AreEqual("failed", receipt.Status);
        Assert.AreEqual("input-sha", receipt.InputFingerprint);
        Assert.AreEqual("config-sha", receipt.ConfigFingerprint);
        Assert.AreEqual("ai_data_json.beats_json", receipt.ArtifactRef);
        Assert.AreEqual("artifact-sha", receipt.ArtifactSha256);
        Assert.IsFalse(receipt.ArtifactValid);
        Assert.AreEqual("2026-08-12T10:00:00Z", receipt.StartedAtUtc);
        Assert.AreEqual("2026-08-12T10:00:01Z", receipt.FinishedAtUtc);
        Assert.AreEqual("beat_failed", receipt.ErrorCode);
        Assert.AreEqual("Beat provider failed", receipt.ErrorMessage);
        Assert.AreEqual("DmlExecutionProvider", receipt.Provider);
        Assert.AreEqual("beatnet", receipt.ModelId);
        Assert.AreEqual("corr-17", receipt.CorrelationId);
        var attempt = receipt.Attempts!.Single();
        Assert.AreEqual("DmlExecutionProvider", attempt.Provider);
        Assert.AreEqual("beatnet", attempt.ModelId);
        Assert.AreEqual("beat_detection", attempt.Task);
        Assert.AreEqual("balance", attempt.Mode);
        CollectionAssert.AreEqual(new[] { "beats" }, attempt.RequiredCapabilities!);
        CollectionAssert.AreEqual(new[] { "beats" }, attempt.VerifiedCapabilities!);
        Assert.AreEqual("manifest", attempt.Source);
        Assert.AreEqual("selected", attempt.Reason);
        Assert.AreEqual("2026-08-12T10:00:00Z", attempt.SelectedAt);
        var legacy = clip.StageReceipts!["key"];
        Assert.AreEqual(0, legacy.ReceiptVersion);
        Assert.IsNull(legacy.ArtifactValid);
        Assert.IsNull(legacy.Provider);
        Assert.AreEqual("legacy interruption", legacy.ErrorMessage);
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

    [TestMethod]
    public void VideoClipInfo_PreservesPartialStageTruth()
    {
        var transport = JsonSerializer.Deserialize<VideoClipInfo>(
            """{"id":7,"name":"clip","path":"C:\\\\media\\\\clip.mp4","duration_seconds":4,"width":1920,"height":1080,"fps":30,"codec":"h264","thumbnail_available":true,"tags":[],"analysis_status":"partial","stage_status":{"scenes":"completed","embedding":"failed"},"stage_errors":{"embedding":"interrupted"}}""",
            SnakeCaseJson);

        Assert.IsNotNull(transport);
        Assert.AreEqual("partial", transport.AnalysisStatus);
        Assert.AreEqual("completed", transport.StageStatus!["scenes"]);
        Assert.AreEqual("interrupted", transport.StageErrors!["embedding"]);

        var model = new VideoClipModel
        {
            AnalysisStatus = transport.AnalysisStatus,
            StageStatus = transport.StageStatus,
            StageErrors = transport.StageErrors,
        };
        Assert.AreEqual("TEILANALYSE", model.AnalysisStatusText);
        StringAssert.Contains(model.AnalysisDetail, "embedding: interrupted");
    }
}
