using System.IO;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class Obj73UiRegressionTests
{
    [TestMethod]
    public async Task AnchorLoad_ProjectSwitchRejectsPreviousGeneration()
    {
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 0, 0, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 0, 0, false);
        var nextProject = projectA;
        var loads = new List<TaskCompletionSource<AnchorListResponse?>>();
        var sync = new object();
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.GetProjectAnchorsAsync), _ =>
            {
                var completion = new TaskCompletionSource<AnchorListResponse?>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
                lock (sync)
                    loads.Add(completion);
                return completion.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        var audioState = new AudioLibraryStateService(
            api.Client,
            NullLogger<AudioLibraryStateService>.Instance);
        using var viewModel = new AnchorViewModel(api.Client, audioState, projects);

        await TestWait.UntilAsync(() =>
        {
            lock (sync)
                return loads.Count == 1;
        });
        nextProject = projectB;
        Assert.IsTrue(await projects.OpenProjectAsync(projectB.Path));

        TaskCompletionSource<AnchorListResponse?> stale;
        lock (sync)
            stale = loads[0];
        stale.SetResult(new AnchorListResponse(
            [new AnchorEntry(1.0, "stale-A")],
            1));

        await TestWait.UntilAsync(() =>
        {
            lock (sync)
                return loads.Count == 2;
        });
        Assert.AreEqual(0, viewModel.Anchors.Count);

        TaskCompletionSource<AnchorListResponse?> current;
        lock (sync)
            current = loads[1];
        current.SetResult(new AnchorListResponse(
            [new AnchorEntry(2.0, "current-B")],
            1));
        await TestWait.UntilAsync(() =>
            viewModel.Anchors.Count == 1
            && viewModel.Anchors[0].Label == "current-B");

        Assert.AreEqual("current-B", viewModel.Anchors.Single().Label);
    }

    [TestMethod]
    public async Task AnchorWrites_DisableEditingUntilOrderedWriteCompletes()
    {
        var project = new ProjectInfo("A", @"C:\Projects\A", 0, 0, false);
        var writes = new List<(
            IReadOnlyList<AnchorEntry> Payload,
            TaskCompletionSource<AnchorListResponse?> Completion)>();
        var sync = new object();
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(
                nameof(IApiClient.GetProjectAnchorsAsync),
                _ => Task.FromResult<AnchorListResponse?>(new AnchorListResponse([], 0)))
            .Handle(nameof(IApiClient.SetProjectAnchorsAsync), args =>
            {
                var completion = new TaskCompletionSource<AnchorListResponse?>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
                var payload = ((IEnumerable<AnchorEntry>)args![0]!).ToList();
                lock (sync)
                    writes.Add((payload, completion));
                return completion.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        var audioState = new AudioLibraryStateService(
            api.Client,
            NullLogger<AudioLibraryStateService>.Instance);
        using var viewModel = new AnchorViewModel(api.Client, audioState, projects);
        await TestWait.UntilAsync(() => viewModel.AddAnchorCommand.CanExecute(null));

        var add = viewModel.AddAnchorCommand.ExecuteAsync(null);
        await TestWait.UntilAsync(() =>
        {
            lock (sync)
                return writes.Count == 1;
        });
        Assert.IsFalse(viewModel.AddAnchorCommand.CanExecute(null));
        Assert.IsFalse(viewModel.RemoveAnchorCommand.CanExecute(null));

        TaskCompletionSource<AnchorListResponse?> first;
        lock (sync)
        {
            Assert.AreEqual(1, writes[0].Payload.Count);
            first = writes[0].Completion;
        }
        first.SetResult(new AnchorListResponse([new AnchorEntry(0, "Anchor 1")], 1));
        await add;
        await TestWait.UntilAsync(() => viewModel.RemoveAnchorCommand.CanExecute(null));

        var remove = viewModel.RemoveAnchorCommand.ExecuteAsync(null);
        await TestWait.UntilAsync(() =>
        {
            lock (sync)
                return writes.Count == 2;
        });
        TaskCompletionSource<AnchorListResponse?> second;
        lock (sync)
        {
            Assert.AreEqual(0, writes[1].Payload.Count);
            second = writes[1].Completion;
        }
        second.SetResult(new AnchorListResponse([], 0));
        await remove;

        Assert.AreEqual(0, viewModel.Anchors.Count);
    }

    [TestMethod]
    public async Task LearningSession_RatingGateAllowsOnlyOneFeedbackForCurrentCut()
    {
        var feedbackCalls = 0;
        var completion = new TaskCompletionSource<BrainFeedbackResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.BrainLearningSessionAsync),
                _ => Task.FromResult<BrainLearningSessionResponse?>(
                    new BrainLearningSessionResponse(
                    [
                        Suggestion(11, "clip-a", 4, 6),
                        Suggestion(12, "clip-b", 8, 10),
                    ])))
            .Handle(nameof(IApiClient.BrainFeedbackAsync), _ =>
            {
                Interlocked.Increment(ref feedbackCalls);
                return completion.Task;
            });
        using var viewModel = new LearningSessionViewModel(api.Client);
        await viewModel.LoadAsync();

        var first = viewModel.RatePerfectAsync();
        await TestWait.UntilAsync(() => Volatile.Read(ref feedbackCalls) == 1);
        await viewModel.RateFitsAsync();

        Assert.AreEqual(1, Volatile.Read(ref feedbackCalls));
        Assert.IsFalse(viewModel.RateNoMatchCommand.CanExecute(null));
        completion.SetResult(new BrainFeedbackResponse("ok", 1, 1));
        await first;

        Assert.AreEqual(1, viewModel.CurrentIndex);
        Assert.AreEqual(12, viewModel.CurrentCutId);
    }

    [TestMethod]
    public async Task Brain_RatingGateAllowsOnlyOneFeedbackForSelectedCut()
    {
        var feedbackCalls = 0;
        var completion = new TaskCompletionSource<BrainFeedbackResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.BrainFeedbackAsync), _ =>
            {
                Interlocked.Increment(ref feedbackCalls);
                return completion.Task;
            });
        using var viewModel = new BrainViewModel(api.Client)
        {
            SelectedCutId = 21,
        };

        var first = viewModel.RatePerfectAsync();
        await TestWait.UntilAsync(() => Volatile.Read(ref feedbackCalls) == 1);
        await viewModel.RateFitsAsync();

        Assert.AreEqual(1, Volatile.Read(ref feedbackCalls));
        Assert.IsFalse(viewModel.RateNoMatchCommand.CanExecute(null));
        completion.SetResult(new BrainFeedbackResponse("ok", 1, 1));
        await first;
    }

    [TestMethod]
    public async Task RatingGate_IsSharedAcrossLearningAndBrainForSameCut()
    {
        var feedbackCalls = 0;
        var completion = new TaskCompletionSource<BrainFeedbackResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.BrainLearningSessionAsync),
                _ => Task.FromResult<BrainLearningSessionResponse?>(
                    new BrainLearningSessionResponse(
                    [Suggestion(25, "shared-cut", 2, 4)])))
            .Handle(nameof(IApiClient.BrainFeedbackAsync), _ =>
            {
                Interlocked.Increment(ref feedbackCalls);
                return completion.Task;
            });
        using var learning = new LearningSessionViewModel(api.Client);
        using var brain = new BrainViewModel(api.Client) { SelectedCutId = 25 };
        await learning.LoadAsync();

        var first = learning.RatePerfectAsync();
        await TestWait.UntilAsync(() => Volatile.Read(ref feedbackCalls) == 1);
        await brain.RateFitsAsync();

        Assert.AreEqual(1, Volatile.Read(ref feedbackCalls));
        completion.SetResult(new BrainFeedbackResponse("ok", 1, 1));
        await first;
    }

    [TestMethod]
    public async Task LearningPlayback_PublishesCutBoundsAndCompletionState()
    {
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.BrainLearningSessionAsync),
                _ => Task.FromResult<BrainLearningSessionResponse?>(
                    new BrainLearningSessionResponse(
                    [Suggestion(31, "clip", 12.5, 18.25)])));
        using var viewModel = new LearningSessionViewModel(api.Client);
        (double Start, double End)? requested = null;
        viewModel.PlayRequested += (start, end) => requested = (start, end);
        await viewModel.LoadAsync();

        viewModel.PlayPause();

        Assert.AreEqual((12.5, 18.25), requested);
        Assert.IsTrue(viewModel.IsPlaying);
        viewModel.NotifyPlaybackCompleted();
        Assert.IsFalse(viewModel.IsPlaying);
    }

    [TestMethod]
    public void LearningDialog_SeeksBothPlayersAndEnforcesCutEnd()
    {
        var root = RepositoryLayout.FindProjectRoot();
        var codeBehind = File.ReadAllText(Path.Combine(
            root,
            "PBStudio.UI",
            "Views",
            "LearningSessionDialog.xaml.cs"));
        var xaml = File.ReadAllText(Path.Combine(
            root,
            "PBStudio.UI",
            "Views",
            "LearningSessionDialog.xaml"));

        StringAssert.Contains(codeBehind, "VideoPlayer.Position = start;");
        StringAssert.Contains(codeBehind, "AudioPlayer.Position = start;");
        StringAssert.Contains(codeBehind, "AudioPlayer.Position >= end");
        StringAssert.Contains(codeBehind, "VideoPlayer.Position >= end");
        StringAssert.Contains(codeBehind, "NotifyPlaybackCompleted()");
        StringAssert.Contains(xaml, "MediaOpened=\"OnMediaOpened\"");
        StringAssert.Contains(xaml, "MediaEnded=\"OnMediaEnded\"");
    }

    private static BrainSuggestion Suggestion(
        int cutId,
        string clipId,
        double start,
        double end) =>
        new(cutId, clipId, start, end, 0.5, []);
}
