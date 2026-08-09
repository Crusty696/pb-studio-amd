using System.Reflection;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class ProjectSwitchUiPublicationTests
{
    [TestMethod]
    public async Task AudioAnalysis_ProjectTransitionRejectsLateError()
    {
        var analysisStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var analysis = new TaskCompletionSource<AudioAnalysisResult?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 1, 0, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 1, 0, false);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.AnalyzeAudioAsync), _ =>
            {
                analysisStarted.TrySetResult(true);
                return analysis.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
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
        var clip = new AudioClipModel { Id = 7, Name = "A clip" };
        viewModel.AudioClips.Add(clip);
        viewModel.SelectedClip = clip;

        var command = viewModel.AnalyzeSelectedCommand.ExecuteAsync(null);
        await analysisStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        nextProject = projectB;
        await SwitchProjectAsync(projects, projectB);
        viewModel.StatusText = "Projekt B aktiv";
        analysis.SetException(new InvalidOperationException("stale A error"));
        await command.WaitAsync(TimeSpan.FromSeconds(3));

        Assert.AreEqual("Projekt B aktiv", viewModel.StatusText);
        Assert.IsFalse(viewModel.IsAnalyzing);
    }

    [TestMethod]
    public async Task VideoSelection_ProjectClosingClearsBatchStateBeforeReusedId()
    {
        var analyzeCalls = 0;
        var deleteCalls = 0;
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 0, 1, false);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(projectA))
            .Handle(nameof(IApiClient.AnalyzeVideoAsync), _ =>
            {
                analyzeCalls++;
                return Task.FromResult<VideoAnalysisResult?>(null);
            })
            .Handle(nameof(IApiClient.DeleteVideoClipAsync), _ =>
            {
                deleteCalls++;
                return Task.FromResult<DeleteResponse?>(new DeleteResponse(1, []));
            })
            .Handle(nameof(IApiClient.DeleteVideoClipsBatchAsync), _ =>
            {
                deleteCalls++;
                return Task.FromResult<DeleteResponse?>(new DeleteResponse(1, []));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        var dialogs = new RecordingDialogService();
        using var viewModel = new VideoLibraryViewModel(
            api.Client,
            new VideoLibraryStateService(
                api.Client,
                NullLogger<VideoLibraryStateService>.Instance),
            projects,
            sse,
            dialogs);
        var clipA = new VideoClipModel
        {
            Id = 1,
            Name = "A video",
            Path = @"C:\Projects\A\video.mp4",
            IsMarked = true,
        };
        viewModel.VideoClips.Add(clipA);
        viewModel.SelectedClip = clipA;
        viewModel.UpdateSelectedClips(new List<VideoClipModel> { clipA });
        Assert.IsTrue(viewModel.AnalyzeMarkedCommand.CanExecute(null));
        Assert.IsTrue(viewModel.DeleteSelectedCommand.CanExecute(null));

        WeakReferenceMessenger.Default.Send(new ProjectClosingMessage());

        Assert.AreEqual(0, viewModel.VideoClips.Count);
        Assert.AreEqual(0, viewModel.SelectedClips.Count);
        Assert.IsNull(viewModel.SelectedClip);
        Assert.IsFalse(clipA.IsMarked);

        var clipB = new VideoClipModel
        {
            Id = 1,
            Name = "B video",
            Path = @"C:\Projects\B\video.mp4",
        };
        viewModel.VideoClips.Add(clipB);
        viewModel.UpdateSelectedClips(new List<VideoClipModel> { clipA });

        Assert.IsFalse(viewModel.AnalyzeMarkedCommand.CanExecute(null));
        Assert.IsFalse(viewModel.DeleteSelectedCommand.CanExecute(null));
        viewModel.UpdateSelectedClips(new List<VideoClipModel>());

        await viewModel.AnalyzeMarkedCommand.ExecuteAsync(null);
        await viewModel.DeleteSelectedCommand.ExecuteAsync(null);

        Assert.AreEqual(0, viewModel.SelectedClips.Count);
        Assert.IsFalse(clipB.IsMarked);
        Assert.AreEqual(0, analyzeCalls);
        Assert.AreEqual(0, deleteCalls);
        Assert.AreEqual(0, dialogs.ConfirmationCount);
    }

    [TestMethod]
    public async Task PacingGeneration_ProjectTransitionRejectsLateError()
    {
        var pacingStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var pacing = new TaskCompletionSource<CutListResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 1, 1, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 1, 1, false);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.GenerateCutListAsync), _ =>
            {
                pacingStarted.TrySetResult(true);
                return pacing.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        using var viewModel = new DirectorViewModel(
            api.Client,
            new AudioLibraryStateService(
                api.Client,
                NullLogger<AudioLibraryStateService>.Instance),
            new VideoLibraryStateService(
                api.Client,
                NullLogger<VideoLibraryStateService>.Instance),
            sse,
            projects);
        viewModel.SelectedAudioClip = new AudioClipModel { Id = 8, Name = "A audio" };
        viewModel.AvailableVideoClips.Add(new SelectableVideoClip
        {
            Id = 9,
            Name = "A video",
            IsSelected = true,
        });
        viewModel.UpdateSelectedCount();

        var command = viewModel.GenerateCutListCommand.ExecuteAsync(null);
        await pacingStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        nextProject = projectB;
        await SwitchProjectAsync(projects, projectB);
        viewModel.StatusText = "Projekt B aktiv";
        pacing.SetException(new InvalidOperationException("stale A error"));
        await command.WaitAsync(TimeSpan.FromSeconds(3));

        Assert.AreEqual("Projekt B aktiv", viewModel.StatusText);
        Assert.IsFalse(viewModel.IsGenerating);
    }

    [TestMethod]
    public async Task VideoAnalysis_ProjectTransitionRejectsLateError()
    {
        var analysisStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var analysis = new TaskCompletionSource<VideoAnalysisResult?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 0, 1, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 0, 1, false);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.AnalyzeVideoAsync), _ =>
            {
                analysisStarted.TrySetResult(true);
                return analysis.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
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
            Id = 10,
            Name = "A video",
            Path = @"C:\Projects\A\video.mp4",
        };
        viewModel.VideoClips.Add(clip);
        viewModel.SelectedClip = clip;

        var command = viewModel.AnalyzeSelectedCommand.ExecuteAsync(null);
        await analysisStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        nextProject = projectB;
        await SwitchProjectAsync(projects, projectB);
        viewModel.StatusText = "Projekt B aktiv";
        analysis.SetException(new InvalidOperationException("stale A error"));
        await command.WaitAsync(TimeSpan.FromSeconds(3));

        Assert.AreEqual("Projekt B aktiv", viewModel.StatusText);
        Assert.IsFalse(viewModel.IsAnalyzing);
    }

    [TestMethod]
    public async Task TimelineSync_ProjectTransitionRejectsLateError()
    {
        var syncStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var sync = new TaskCompletionSource<StatusResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 1, 1, true);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 1, 1, true);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.UpdateTimelineAsync), _ =>
            {
                syncStarted.TrySetResult(true);
                return sync.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        using var viewModel = new TimelineViewModel(
            new TimelineStateService(
                api.Client,
                NullLogger<TimelineStateService>.Instance,
                projects),
            new AudioLibraryStateService(
                api.Client,
                NullLogger<AudioLibraryStateService>.Instance),
            api.Client,
            projects);
        typeof(TimelineViewModel)
            .GetField("_timelineReadyForMutation", BindingFlags.Instance | BindingFlags.NonPublic)!
            .SetValue(viewModel, true);
        viewModel.TimelineEntries.Add(new TimelineEntryModel
        {
            ClipId = "clip_11",
            ClipName = "A video",
            FilePath = @"C:\Projects\A\video.mp4",
            StartTime = 0,
            EndTime = 1,
        });
        viewModel.MarkTimelineDirty();

        var command = viewModel.SyncTimelineCommand.ExecuteAsync(null);
        await syncStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        nextProject = projectB;
        await SwitchProjectAsync(projects, projectB);
        viewModel.StatusText = "Projekt B aktiv";
        sync.SetException(new InvalidOperationException("stale A error"));
        await command.WaitAsync(TimeSpan.FromSeconds(3));

        Assert.AreEqual("Projekt B aktiv", viewModel.StatusText);
    }

    [TestMethod]
    public async Task BrainFeedback_ProjectResetRejectsLateResponse()
    {
        var feedbackStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var feedback = new TaskCompletionSource<BrainFeedbackResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 1, 1, true);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 1, 1, true);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.BrainFeedbackAsync), _ =>
            {
                feedbackStarted.TrySetResult(true);
                return feedback.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        using var viewModel = new BrainViewModel(api.Client, projects)
        {
            SelectedCutId = 41,
        };

        var command = viewModel.RatePerfectCommand.ExecuteAsync(null);
        await feedbackStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        WeakReferenceMessenger.Default.UnregisterAll(viewModel);
        nextProject = projectB;
        await SwitchProjectAsync(projects, projectB);
        viewModel.Status = "Projekt B aktiv";
        feedback.SetResult(new BrainFeedbackResponse("ok", 4, 12));
        await command.WaitAsync(TimeSpan.FromSeconds(3));

        Assert.AreEqual("Projekt B aktiv", viewModel.Status);
        Assert.AreEqual(41, viewModel.SelectedCutId);
        Assert.AreEqual(0, viewModel.TotalClicks);
    }

    private static async Task SwitchProjectAsync(
        ProjectService projects,
        ProjectInfo projectB)
    {
        var recipient = new object();
        var lifecycle = new List<string>();
        WeakReferenceMessenger.Default.Register<ProjectClosingMessage>(
            recipient,
            (_, _) => lifecycle.Add("closing"));
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(
            recipient,
            (_, _) => lifecycle.Add("closed"));
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(
            recipient,
            (_, _) => lifecycle.Add("opened"));
        try
        {
            Assert.IsTrue(await projects.OpenProjectAsync(projectB.Path));
            CollectionAssert.AreEqual(
                new[] { "closing", "closed", "opened" },
                lifecycle);
            Assert.AreEqual(projectB.Path, projects.CurrentProject?.Path);
        }
        finally
        {
            WeakReferenceMessenger.Default.UnregisterAll(recipient);
        }
    }

    private sealed class RecordingDialogService : IDialogService
    {
        public int ConfirmationCount { get; private set; }

        public string? OpenFile(string title, string filter, string? initialDirectory = null) => null;
        public List<string> OpenFiles(string title, string filter, string? initialDirectory = null) => [];
        public string? OpenFolder(string title, string? initialDirectory = null) => null;
        public string? SaveFile(
            string title,
            string filter,
            string defaultFileName,
            string? initialDirectory = null) => null;

        public bool ConfirmDestructiveAction(string title, string message)
        {
            ConfirmationCount++;
            return true;
        }
    }
}
