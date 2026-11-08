using System.Windows;
using System.Windows.Threading;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class VideoLibraryBatchPartialResultTests
{
    [TestMethod]
    public void BatchFailureStillLoadsSuccessfulSceneStage()
    {
        StaTest.Run(() => RunOnStaDispatcherAsync().GetAwaiter().GetResult());
    }

    private static async Task RunOnStaDispatcherAsync()
    {
        var dispatcher = Dispatcher.CurrentDispatcher;
        SynchronizationContext.SetSynchronizationContext(
            new DispatcherSynchronizationContext(dispatcher));

        var request = 0;
        var sceneReads = 0;
        var project = new ProjectInfo(
            "Batch partial scene",
            @"C:\Projects\BatchPartialScene",
            0,
            1,
            false);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.AnalyzeVideoAsync), _ =>
            {
                request++;
                if (request == 3)
                    throw new InvalidOperationException("verlorene Szenen-Antwort");

                var scenes = new List<SceneInfo>
                {
                    new(0.0, 2.0, "action", 0.9),
                };
                return Task.FromResult<VideoAnalysisResult?>(request switch
                {
                    1 => new VideoAnalysisResult(
                        31,
                        1,
                        0.0,
                        [],
                        [],
                        false,
                        Scenes: scenes,
                        Status: "completed",
                        StageStatus: new Dictionary<string, string>
                        {
                            ["scenes"] = "completed",
                        }),
                    2 => new VideoAnalysisResult(
                        31,
                        1,
                        0.0,
                        [],
                        [],
                        false,
                        Scenes: scenes,
                        Status: "partial",
                        StageStatus: new Dictionary<string, string>
                        {
                            ["scenes"] = "completed",
                            ["motion"] = "failed",
                        },
                        StageErrors: new Dictionary<string, string>
                        {
                            ["motion"] = "RAFT unavailable",
                        }),
                    _ => new VideoAnalysisResult(
                        31,
                        1,
                        0.0,
                        [],
                        [],
                        false,
                        Scenes: scenes,
                        Status: "completed",
                        StageStatus: new Dictionary<string, string>
                        {
                            ["scenes"] = "completed",
                            ["motion"] = "completed",
                        }),
                });
            })
            .Handle(nameof(IApiClient.GetAsync), arguments =>
            {
                var url = Assert.IsInstanceOfType<string>(arguments![0]);
                Assert.AreEqual("/video/scenes/31", url);
                sceneReads++;
                return Task.FromResult<List<SceneInfo>?>(
                    [new SceneInfo(0.0, 2.0, "action", 0.9)]);
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
        var clip = new VideoClipModel
        {
            Id = 31,
            Name = "Partial clip",
            Path = @"C:\Projects\BatchPartialScene\clip.mp4",
        };
        viewModel.VideoClips.Add(clip);
        viewModel.SelectedClip = clip;
        viewModel.StepAnalyzeMotion = true;
        viewModel.StepGenerateEmbeddings = false;
        viewModel.StepGenerateCaptions = false;

        await ExecuteBatchAndPumpAsync(viewModel, dispatcher);

        Assert.AreEqual(2, request);
        Assert.AreEqual(1, sceneReads);
        Assert.AreEqual(1, viewModel.SelectedClipScenes.Count);
        Assert.AreEqual("action", viewModel.SelectedClipScenes[0].SceneType);
        StringAssert.Contains(viewModel.StatusText, "1 fehlgeschlagen");

        await ExecuteBatchAndPumpAsync(viewModel, dispatcher);

        Assert.AreEqual(4, request);
        Assert.AreEqual(2, sceneReads);
        StringAssert.Contains(viewModel.StatusText, "1 erfolgreich");
        StringAssert.Contains(viewModel.StatusText, "0 fehlgeschlagen");
        SynchronizationContext.SetSynchronizationContext(null);
    }

    private static async Task ExecuteBatchAndPumpAsync(
        VideoLibraryViewModel viewModel,
        Dispatcher dispatcher)
    {
        var analysis = viewModel.AnalyzeAllCommand.ExecuteAsync(null);
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer(
            TimeSpan.FromMilliseconds(5),
            DispatcherPriority.Background,
            (_, _) =>
            {
                if (analysis.IsCompleted)
                    frame.Continue = false;
            },
            dispatcher);
        timer.Start();
        Dispatcher.PushFrame(frame);
        timer.Stop();
        await analysis;
    }
}
