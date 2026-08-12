using System.Reflection;
using System.Net;
using System.Net.Http;
using System.Text;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class AnalysisResumeContractTests
{
    [TestMethod]
    public async Task AnalyzeAudio_HttpTransportDeserializesOwnedReceiptDto()
    {
        const string json = """
            {
              "clip_id": 17,
              "duration_seconds": 42,
              "bpm": 128,
              "beat_count": 0,
              "beats": [],
              "analysis_status": "failed",
              "stage_status": {"beats": "failed"},
              "stage_errors": {"beats": "provider failed"},
              "stage_receipts": {
                "beats": {
                  "receipt_version": 1,
                  "stage_id": "beats",
                  "requested": true,
                  "status": "failed",
                  "artifact_valid": false,
                  "error_message": "provider failed",
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
                  }]
                }
              }
            }
            """;
        using var http = new HttpClient(new AudioResponseHandler(json))
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
        };
        using var api = new ApiClient(http, NullLogger<ApiClient>.Instance);

        var result = await api.AnalyzeAudioAsync(17);

        Assert.IsNotNull(result);
        Assert.AreEqual("failed", result.AnalysisStatus);
        var receipt = result.StageReceipts!["beats"];
        Assert.AreEqual("provider failed", receipt.ErrorMessage);
        Assert.AreEqual("DmlExecutionProvider", receipt.Attempts!.Single().Provider);
    }

    [TestMethod]
    public void AudioStageTruth_RendersRequestedRowsAndUsesExactRetryEligibility()
    {
        static StageReceipt Receipt(
            string stageId,
            string status,
            bool requested = true,
            string? error = null) => new(
                ReceiptVersion: 1,
                StageId: stageId,
                Requested: requested,
                Status: status,
                ErrorMessage: error);

        var completed = new AudioClipModel
        {
            IsAnalyzed = true,
            AnalysisStatus = "completed",
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["beats"] = Receipt("beats", "completed"),
                ["structure"] = Receipt("structure", "completed"),
                ["spectral"] = Receipt("spectral", "completed"),
                ["key"] = Receipt("key", "completed"),
            },
        };
        var partial = new AudioClipModel
        {
            IsAnalyzed = true,
            AnalysisStatus = "partial",
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["beats"] = Receipt("beats", "completed"),
                ["structure"] = Receipt("structure", "partial", error: "usable degradation"),
                ["spectral"] = Receipt("spectral", "completed"),
                ["key"] = Receipt("key", "completed"),
            },
        };
        var newlyRequested = new AudioClipModel
        {
            AnalysisStatus = "partial",
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["beats"] = Receipt("beats", "completed"),
                ["structure"] = Receipt("structure", "skipped", requested: false),
            },
        };
        var failed = new AudioClipModel
        {
            IsAnalyzed = true,
            AnalysisStatus = "failed",
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["beats"] = Receipt("beats", "failed", error: "provider failed"),
            },
        };
        var interrupted = new AudioClipModel
        {
            IsAnalyzed = true,
            AnalysisStatus = "partial",
            StageErrors = new Dictionary<string, string>
            {
                ["key"] = "project switched",
            },
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["key"] = Receipt("key", "interrupted"),
            },
        };
        var unavailable = new AudioClipModel
        {
            IsAnalyzed = true,
            AnalysisStatus = "failed",
            StageReceipts = new Dictionary<string, StageReceipt>
            {
                ["spectral"] = Receipt("spectral", "unavailable", error: "capability missing"),
            },
        };
        var pristine = new AudioClipModel();

        Assert.IsFalse(completed.CanRetryAnalysis);
        Assert.IsFalse(partial.CanRetryAnalysis);
        Assert.IsTrue(newlyRequested.CanRetryAnalysis);
        Assert.IsTrue(failed.CanRetryAnalysis);
        Assert.IsTrue(interrupted.CanRetryAnalysis);
        Assert.IsTrue(unavailable.CanRetryAnalysis);
        Assert.IsFalse(pristine.CanRetryAnalysis);
        Assert.AreEqual(0, pristine.StageItems.Count);
        Assert.AreEqual(4, completed.StageItems.Count);
        Assert.AreEqual(1, newlyRequested.StageItems.Count, "requested=false stage must stay hidden");
        Assert.AreEqual("completed", completed.StageItems[0].Status);
        Assert.AreEqual("provider failed", failed.StageItems.Single().Reason);
        Assert.AreEqual("project switched", interrupted.StageItems.Single().Reason);
        Assert.IsFalse(partial.IsAnalyzed);
        Assert.IsFalse(failed.IsAnalyzed);
        Assert.IsFalse(interrupted.IsAnalyzed);
        Assert.IsFalse(unavailable.IsAnalyzed);

        unavailable.AnalysisStatus = "completed";
        unavailable.IsAnalyzed = true;
        unavailable.AnalysisStatus = "unavailable";
        Assert.IsFalse(unavailable.IsAnalyzed);
    }

    [TestMethod]
    public async Task AudioTerminalSse_WhenIdle_ReloadsPersistedReceiptTruth()
    {
        var project = new ProjectInfo(
            "Receipt Refresh",
            @"C:\Projects\ReceiptRefresh",
            1,
            0,
            false);
        var listCalls = 0;
        var persisted = new AudioClipInfo(
            74,
            "mix",
            @"C:\Projects\ReceiptRefresh\mix.wav",
            60.0,
            44100,
            2,
            "wav",
            AnalysisStatus: "partial",
            StageStatus: new Dictionary<string, string>
            {
                ["structure"] = "interrupted",
            },
            StageErrors: new Dictionary<string, string>
            {
                ["structure"] = "backend restart",
            },
            StageReceipts: new Dictionary<string, StageReceipt>
            {
                ["structure"] = new StageReceipt(
                    ReceiptVersion: 1,
                    StageId: "structure",
                    Requested: true,
                    Status: "interrupted",
                    ErrorMessage: "backend restart"),
            });
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.GetAudioClipsAsync), _ =>
            {
                Interlocked.Increment(ref listCalls);
                return Task.FromResult<List<AudioClipInfo>?>([persisted]);
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        using var viewModel = new AudioLibraryViewModel(
            api.Client,
            new AudioLibraryStateService(
                api.Client,
                NullLogger<AudioLibraryStateService>.Instance),
            sse,
            new DialogServiceStub(),
            projects);
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        viewModel.AudioClips.Add(new AudioClipModel
        {
            Id = 74,
            Name = "stale",
            AnalysisStatus = "running",
        });
        Assert.IsFalse(viewModel.IsAnalyzing);

        var streamKindType = typeof(SSEClient).GetNestedType(
            "StreamKind",
            BindingFlags.NonPublic)!;
        var progressKind = Enum.Parse(streamKindType, "Progress");
        var processEvent = typeof(SSEClient).GetMethod(
            "ProcessEvent",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        processEvent.Invoke(
            sse,
            [
                progressKind,
                "analysis_progress",
                """{"task_id":"74","clip_id":74,"status":"partial","percent":100}""",
            ]);

        await TestWait.UntilAsync(() =>
            Volatile.Read(ref listCalls) > 0
            && viewModel.AudioClips.Count == 1
            && viewModel.AudioClips[0].StageReceipts?.ContainsKey("structure") == true);
        Assert.AreEqual("partial", viewModel.AudioClips[0].AnalysisStatus);
        Assert.AreEqual("backend restart", viewModel.AudioClips[0].StageItems.Single().Reason);
    }

    [TestMethod]
    public async Task VideoBatch_CompletedClipStillReachesPlannerAndSortPreservesIdentity()
    {
        var project = new ProjectInfo(
            "Video Resume",
            @"C:\Projects\VideoResume",
            0,
            2,
            false);
        var analyzedIds = new List<int>();
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.AnalyzeVideoAsync), arguments =>
            {
                var clipId = Assert.IsInstanceOfType<int>(arguments![0]);
                analyzedIds.Add(clipId);
                return Task.FromResult<VideoAnalysisResult?>(new VideoAnalysisResult(
                    clipId,
                    1,
                    0.0,
                    [],
                    [],
                    false,
                    Status: "completed",
                    StageStatus: new Dictionary<string, string>
                    {
                        ["scenes"] = "completed",
                    }));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        using var viewModel = new VideoLibraryViewModel(
            api.Client,
            new VideoLibraryStateService(
                api.Client,
                NullLogger<VideoLibraryStateService>.Instance),
            projects,
            sse,
            new DialogServiceStub());
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        var completed = new VideoClipModel
        {
            Id = 9,
            Name = "Zulu",
            Path = @"C:\Projects\VideoResume\zulu.mp4",
            IsAnalyzed = true,
            AnalysisStatus = "completed",
        };
        var pending = new VideoClipModel
        {
            Id = 10,
            Name = "Alpha",
            Path = @"C:\Projects\VideoResume\alpha.mp4",
            AnalysisStatus = "partial",
        };
        viewModel.VideoClips.Add(completed);
        viewModel.VideoClips.Add(pending);
        viewModel.SelectedClip = completed;
        viewModel.SelectedSortOption = "Name A-Z";

        var sorted = viewModel.VideoClipsView.Cast<VideoClipModel>().ToList();
        Assert.AreSame(pending, sorted[0]);
        Assert.AreSame(completed, sorted[1]);
        Assert.AreSame(completed, viewModel.SelectedClip);
        Assert.AreSame(completed, viewModel.VideoClips[0]);

        await viewModel.AnalyzeAllCommand.ExecuteAsync(null);

        CollectionAssert.AreEqual(new[] { 9, 10 }, analyzedIds);
        Assert.AreEqual(100.0, viewModel.AnalyzeAllProgress);
        StringAssert.Contains(viewModel.StatusText, "2 verarbeitet");
    }

    [TestMethod]
    public async Task AudioBatch_RestartSkipsCompletedAndContinuesAfterFailure()
    {
        var project = new ProjectInfo(
            "Resume",
            @"C:\Projects\Resume",
            3,
            0,
            false);
        var analyzedIds = new List<int>();
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.AnalyzeAudioAsync), arguments =>
            {
                var clipId = Assert.IsInstanceOfType<int>(arguments![0]);
                analyzedIds.Add(clipId);
                if (clipId == 2)
                {
                    return Task.FromException<AudioAnalysisResult?>(
                        new InvalidOperationException("unterbrochene Stufe"));
                }

                return Task.FromResult<AudioAnalysisResult?>(new AudioAnalysisResult(
                    clipId,
                    30.0,
                    128.0,
                    1,
                    [new BeatData(0.5, 0.8, "beat")],
                    AnalysisStatus: "completed",
                    StageStatus: new Dictionary<string, string>
                    {
                        ["beats"] = "completed",
                        ["structure"] = "completed",
                    }));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        using var viewModel = new AudioLibraryViewModel(
            api.Client,
            new AudioLibraryStateService(
                api.Client,
                NullLogger<AudioLibraryStateService>.Instance),
            sse,
            new DialogServiceStub(),
            projects);
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        viewModel.AudioClips.Add(new AudioClipModel
        {
            Id = 1,
            Name = "bereits fertig",
            IsAnalyzed = true,
            AnalysisStatus = "completed",
        });
        viewModel.AudioClips.Add(new AudioClipModel
        {
            Id = 2,
            Name = "unterbrochen",
            IsAnalyzed = false,
            AnalysisStatus = "partial",
            StageErrors = new Dictionary<string, string>
            {
                ["structure"] = "interrupted",
            },
        });
        var pending = new AudioClipModel
        {
            Id = 3,
            Name = "noch offen",
            IsAnalyzed = false,
            AnalysisStatus = "unavailable",
        };
        viewModel.AudioClips.Add(pending);

        await viewModel.AnalyzeAllCommand.ExecuteAsync(null);

        CollectionAssert.AreEqual(new[] { 2, 3 }, analyzedIds);
        Assert.IsTrue(pending.IsAnalyzed);
        Assert.AreEqual("completed", pending.AnalysisStatus);
        Assert.AreEqual(100.0, viewModel.AnalysisProgress);
        StringAssert.Contains(viewModel.StatusText, "1 fehlgeschlagen");
        StringAssert.Contains(viewModel.StatusText, "unterbrochene Stufe");
    }

    [TestMethod]
    public void SseInterrupted_IsTerminalAndCannotBeThrottled()
    {
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        var statuses = new List<string>();
        sse.ProgressReceived += (_, args) => statuses.Add(args.Status);

        var streamKindType = typeof(SSEClient).GetNestedType(
            "StreamKind",
            BindingFlags.NonPublic)!;
        var progressKind = Enum.Parse(streamKindType, "Progress");
        var processEvent = typeof(SSEClient).GetMethod(
            "ProcessEvent",
            BindingFlags.Instance | BindingFlags.NonPublic)!;

        processEvent.Invoke(
            sse,
            [
                progressKind,
                "analysis_progress",
                """{"task_id":"74","status":"running","percent":0}""",
            ]);
        processEvent.Invoke(
            sse,
            [
                progressKind,
                "analysis_progress",
                """{"task_id":"74","status":"interrupted","percent":0}""",
            ]);

        Assert.AreEqual(
            2,
            statuses.Count,
            $"Terminaler Abbruch vom 100-ms-Filter verworfen; empfangen: {string.Join(", ", statuses)}");
        CollectionAssert.AreEqual(new[] { "running", "interrupted" }, statuses);
    }

    [TestMethod]
    public void SseEventId_IsCommittedOnlyAfterSuccessfulDispatch()
    {
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        var streamKindType = typeof(SSEClient).GetNestedType(
            "StreamKind",
            BindingFlags.NonPublic)!;
        var progressKind = Enum.Parse(streamKindType, "Progress");
        var dispatch = typeof(SSEClient).GetMethod(
            "TryDispatchBufferedEvent",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        var getLastEventId = typeof(SSEClient).GetMethod(
            "GetLastEventId",
            BindingFlags.Instance | BindingFlags.NonPublic)!;

        var malformedProcessed = Assert.IsInstanceOfType<bool>(dispatch.Invoke(
            sse,
            [progressKind, "analysis_progress", new StringBuilder("{"), 74L]));
        Assert.IsFalse(malformedProcessed);
        Assert.AreEqual(0L, getLastEventId.Invoke(sse, [progressKind]));

        EventHandler<ProgressEventArgs> throwingHandler = (_, _) =>
            throw new InvalidOperationException("dispatch failed");
        sse.ProgressReceived += throwingHandler;
        var failedDispatchProcessed = Assert.IsInstanceOfType<bool>(dispatch.Invoke(
            sse,
            [
                progressKind,
                "analysis_progress",
                new StringBuilder("""{"status":"interrupted","percent":0}"""),
                74L,
            ]));
        sse.ProgressReceived -= throwingHandler;
        Assert.IsFalse(failedDispatchProcessed);
        Assert.AreEqual(0L, getLastEventId.Invoke(sse, [progressKind]));

        var successfulDispatch = Assert.IsInstanceOfType<bool>(dispatch.Invoke(
            sse,
            [
                progressKind,
                "analysis_progress",
                new StringBuilder("""{"status":"interrupted","percent":0}"""),
                74L,
            ]));
        Assert.IsTrue(successfulDispatch);
        Assert.AreEqual(74L, getLastEventId.Invoke(sse, [progressKind]));
    }

    [TestMethod]
    public void SseDispose_DoesNotThrowForCancelledReconnectTask()
    {
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        var listenTasksField = typeof(SSEClient).GetField(
            "_listenTasks",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        var listenTasks = Assert.IsInstanceOfType<List<Task>>(
            listenTasksField.GetValue(sse));
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        listenTasks.Add(Task.FromCanceled(cancellation.Token));

        sse.Dispose();
    }

    private sealed class AudioResponseHandler(string json) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json"),
            });
    }
}
