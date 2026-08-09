using System.Reflection;
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
}
