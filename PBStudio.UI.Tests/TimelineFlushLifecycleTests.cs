using System.Reflection;
using System.Windows.Threading;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class TimelineFlushLifecycleTests
{
    [TestMethod]
    public async Task TimelineFlush_ConvergesWhenEditArrivesDuringFirstWrite()
    {
        var project = Project("A");
        var writes = new List<double>();
        TimelineViewModel? viewModel = null;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.UpdateTimelineAsync), args =>
            {
                var entries = (List<TimelineEntryModel>)args![0]!;
                writes.Add(entries.Single().StartTime);
                if (writes.Count == 1)
                {
                    viewModel!.TimelineEntries.Single().StartTime = 2;
                    viewModel.MarkTimelineDirty();
                }
                return Task.FromResult<StatusResponse?>(new(true, "saved"));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var fixture = TimelineFixture.Create(api.Client, projects);
        viewModel = fixture.ViewModel;
        Ready(viewModel);
        viewModel.TimelineEntries.Add(Entry(0));
        viewModel.MarkTimelineDirty();

        var result = await viewModel.FlushPendingTimelineAsync();

        Assert.IsTrue(result.Success);
        CollectionAssert.AreEqual(new[] { 0.0, 2.0 }, writes);
        var noOp = await viewModel.FlushPendingTimelineAsync();
        Assert.IsTrue(noOp.Success);
        Assert.AreEqual(2, writes.Count);
    }

    [TestMethod]
    public async Task TimelineFlush_FailureKeepsDirtyStateForRetry()
    {
        var project = Project("A");
        var calls = 0;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.UpdateTimelineAsync), _ =>
            {
                calls++;
                return Task.FromResult<StatusResponse?>(
                    new(calls > 1, calls > 1 ? "saved" : "disk full"));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var fixture = TimelineFixture.Create(api.Client, projects);
        Ready(fixture.ViewModel);
        fixture.ViewModel.TimelineEntries.Add(Entry(0));
        fixture.ViewModel.MarkTimelineDirty();

        var failed = await fixture.ViewModel.FlushPendingTimelineAsync();
        var retried = await fixture.ViewModel.FlushPendingTimelineAsync();

        Assert.IsFalse(failed.Success);
        Assert.AreEqual("disk full", failed.ErrorMessage);
        Assert.IsTrue(retried.Success);
        Assert.AreEqual(2, calls);
    }

    [TestMethod]
    public async Task TimelineFlush_ReloadsBackendCanonicalTimelineAfterConvergence()
    {
        var project = Project("A");
        var canonical = new TimelineResponse(
            [new TimelineEntry(
                "clip_1",
                "clip",
                @"C:\Projects\A\clip.mp4",
                1.25,
                2.25,
                0,
                "beat",
                1)],
            3,
            null);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(
                nameof(IApiClient.UpdateTimelineAsync),
                _ => Task.FromResult<StatusResponse?>(new(true, "canonicalized")))
            .Handle(
                nameof(IApiClient.GetTimelineAsync),
                _ => Task.FromResult<TimelineResponse?>(canonical));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var fixture = TimelineFixture.Create(api.Client, projects);
        Ready(fixture.ViewModel);
        fixture.ViewModel.TimelineEntries.Add(Entry(1.237));
        fixture.ViewModel.MarkTimelineDirty();

        var result = await fixture.ViewModel.FlushPendingTimelineAsync();

        Assert.IsTrue(result.Success);
        Assert.AreEqual(1.25, fixture.ViewModel.TimelineEntries.Single().StartTime);
        Assert.AreEqual(2.25, fixture.ViewModel.TimelineEntries.Single().EndTime);
    }

    [TestMethod]
    public async Task TimelineFlush_CancellationKeepsDirtyStateForRetry()
    {
        var project = Project("A");
        var firstStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var calls = 0;
        var canonical = new TimelineResponse(
            [new TimelineEntry(
                "clip_1",
                "clip",
                @"C:\Projects\A\clip.mp4",
                0,
                1,
                0,
                "beat",
                1)],
            1,
            null);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.UpdateTimelineAsync), args =>
            {
                calls++;
                if (calls > 1)
                    return Task.FromResult<StatusResponse?>(new(true, "saved"));
                firstStarted.TrySetResult(true);
                return WaitForCancellationAsync((CancellationToken)args![1]!);
            })
            .Handle(
                nameof(IApiClient.GetTimelineAsync),
                _ => Task.FromResult<TimelineResponse?>(canonical));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        using var fixture = TimelineFixture.Create(api.Client, projects);
        Ready(fixture.ViewModel);
        fixture.ViewModel.TimelineEntries.Add(Entry(0));
        fixture.ViewModel.MarkTimelineDirty();
        using var cancellation = new CancellationTokenSource();

        var pending = fixture.ViewModel.FlushPendingTimelineAsync(cancellation.Token);
        await firstStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        cancellation.Cancel();
        var cancelled = await pending;
        var retried = await fixture.ViewModel.FlushPendingTimelineAsync();

        Assert.IsFalse(cancelled.Success);
        Assert.IsTrue(cancelled.Cancelled);
        Assert.IsTrue(retried.Success);
        Assert.AreEqual(2, calls);
    }

    [TestMethod]
    public async Task Coordinator_OlderLeaseCannotUnregisterNewTimeline()
    {
        using var coordinator = new TimelineFlushCoordinator();
        var dispatcher = Dispatcher.CurrentDispatcher;
        var oldCalls = 0;
        var newCalls = 0;
        var oldLease = coordinator.Register(dispatcher, _ =>
        {
            oldCalls++;
            return Task.FromResult(TimelineFlushResult.Succeeded);
        });
        using var newLease = coordinator.Register(dispatcher, _ =>
        {
            newCalls++;
            return Task.FromResult(TimelineFlushResult.Succeeded);
        });

        oldLease.Dispose();
        var result = await coordinator.FlushAsync();

        Assert.IsTrue(result.Success);
        Assert.AreEqual(0, oldCalls);
        Assert.AreEqual(1, newCalls);
    }

    [TestMethod]
    public async Task Coordinator_WorkerFlushRunsDelegateOnRegisteredStaDispatcher()
    {
        using var coordinator = new TimelineFlushCoordinator();
        var dispatcherReady = new TaskCompletionSource<Dispatcher>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var thread = new Thread(() =>
        {
            dispatcherReady.TrySetResult(Dispatcher.CurrentDispatcher);
            Dispatcher.Run();
        });
        thread.IsBackground = true;
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        var dispatcher = await dispatcherReady.Task.WaitAsync(TimeSpan.FromSeconds(3));
        var ranOnDispatcher = false;
        using var lease = coordinator.Register(dispatcher, _ =>
        {
            ranOnDispatcher = dispatcher.CheckAccess();
            return Task.FromResult(TimelineFlushResult.Succeeded);
        });

        var result = await Task.Run(() => coordinator.FlushAsync());

        dispatcher.BeginInvokeShutdown(DispatcherPriority.Send);
        Assert.IsTrue(thread.Join(TimeSpan.FromSeconds(3)));
        Assert.IsTrue(result.Success);
        Assert.IsTrue(ranOnDispatcher);
    }

    [TestMethod]
    public async Task ProjectLifecycle_FlushesBeforeEveryApiMutation()
    {
        var events = new List<string>();
        var nextProject = Project("A");
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.OpenProjectAsync), _ =>
            {
                events.Add("open");
                return Task.FromResult<ProjectInfo?>(nextProject);
            })
            .Handle(nameof(IApiClient.CreateProjectAsync), _ =>
            {
                events.Add("create");
                return Task.FromResult<ProjectInfo?>(nextProject);
            })
            .Handle(nameof(IApiClient.SaveProjectAsync), _ =>
            {
                events.Add("save");
                return Task.FromResult<StatusResponse?>(new(true, "saved"));
            })
            .Handle(nameof(IApiClient.CloseProjectAsync), _ =>
            {
                events.Add("close");
                return Task.FromResult<StatusResponse?>(new(true, "closed"));
            });
        var flush = new RecordingFlushCoordinator(() =>
        {
            events.Add("flush");
            return Task.FromResult(TimelineFlushResult.Succeeded);
        });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance,
            flush);
        Assert.IsTrue(await projects.OpenProjectAsync(nextProject.Path));

        events.Clear();
        Assert.IsTrue(await projects.SaveProjectAsync());
        CollectionAssert.AreEqual(new[] { "flush", "save" }, events);

        events.Clear();
        nextProject = Project("B");
        Assert.IsTrue(await projects.OpenProjectAsync(nextProject.Path));
        CollectionAssert.AreEqual(new[] { "flush", "open" }, events);

        events.Clear();
        nextProject = Project("C");
        Assert.IsTrue(await projects.CreateProjectAsync("C", nextProject.Path));
        CollectionAssert.AreEqual(new[] { "flush", "create" }, events);

        events.Clear();
        Assert.IsTrue(await projects.CloseProjectAsync());
        CollectionAssert.AreEqual(new[] { "flush", "close" }, events);
    }

    [TestMethod]
    public async Task ProjectLifecycle_FlushFailurePreservesProjectAndSkipsApi()
    {
        var project = Project("A");
        var saveCalls = 0;
        var openCalls = 0;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ =>
                {
                    openCalls++;
                    return Task.FromResult<ProjectInfo?>(project);
                })
            .Handle(
                nameof(IApiClient.SaveProjectAsync),
                _ =>
                {
                    saveCalls++;
                    return Task.FromResult<StatusResponse?>(new(true, "saved"));
                });
        var flushResult = TimelineFlushResult.Succeeded;
        var flush = new RecordingFlushCoordinator(
            () => Task.FromResult(flushResult));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance,
            flush);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        var stable = projects.CurrentProject;
        flushResult = TimelineFlushResult.Failed("disk full");

        Assert.IsFalse(await projects.SaveProjectAsync());
        Assert.IsFalse(await projects.OpenProjectAsync(@"C:\Projects\B"));
        var closeResult = await new MainWindowCloseGate(projects).TryAuthorizeAsync();

        Assert.AreSame(stable, projects.CurrentProject);
        Assert.AreEqual(0, saveCalls);
        Assert.AreEqual(1, openCalls);
        Assert.IsFalse(closeResult.Authorized);
        Assert.AreEqual("disk full", closeResult.ErrorMessage);
        Assert.AreEqual("disk full", projects.LastTimelineFlushResult.ErrorMessage);
    }

    [TestMethod]
    public async Task ProjectLifecycle_SaveAndOpenAreSerialized()
    {
        var projectA = Project("A");
        var projectB = Project("B");
        var nextProject = projectA;
        var saveStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var finishSave = new TaskCompletionSource<StatusResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var openCalls = 0;
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.OpenProjectAsync), _ =>
            {
                openCalls++;
                return Task.FromResult<ProjectInfo?>(nextProject);
            })
            .Handle(nameof(IApiClient.SaveProjectAsync), _ =>
            {
                saveStarted.TrySetResult(true);
                return finishSave.Task;
            });
        var flush = new RecordingFlushCoordinator(
            () => Task.FromResult(TimelineFlushResult.Succeeded));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance,
            flush);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        nextProject = projectB;

        var save = projects.SaveProjectAsync();
        await saveStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        var open = projects.OpenProjectAsync(projectB.Path);
        await Task.Delay(50);
        Assert.AreEqual(1, openCalls);

        finishSave.SetResult(new StatusResponse(true, "saved"));
        Assert.IsTrue(await save);
        Assert.IsTrue(await open);
        Assert.AreEqual(2, openCalls);
    }

    [TestMethod]
    public async Task MainWindowCloseGate_DeduplicatesAndRetriesSave()
    {
        var project = Project("A");
        var saveCalls = 0;
        var firstSaveStarted = new TaskCompletionSource<bool>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var firstSave = new TaskCompletionSource<StatusResponse?>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var allowSave = false;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(nameof(IApiClient.SaveProjectAsync), _ =>
            {
                saveCalls++;
                if (saveCalls == 1)
                {
                    firstSaveStarted.TrySetResult(true);
                    return firstSave.Task;
                }
                return Task.FromResult<StatusResponse?>(
                    new(allowSave, allowSave ? "saved" : "disk full"));
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(project.Path));
        var gate = new MainWindowCloseGate(projects);

        var first = gate.TryAuthorizeAsync();
        await firstSaveStarted.Task.WaitAsync(TimeSpan.FromSeconds(3));
        var duplicate = await gate.TryAuthorizeAsync();
        Assert.IsTrue(duplicate.InProgress);
        Assert.AreEqual(1, saveCalls);

        firstSave.SetResult(new StatusResponse(false, "disk full"));
        var failed = await first;
        Assert.IsFalse(failed.Authorized);
        Assert.IsFalse(gate.IsAuthorized);

        var failedRetry = await gate.TryAuthorizeAsync();
        Assert.IsFalse(failedRetry.Authorized);
        allowSave = true;
        var success = await gate.TryAuthorizeAsync();
        Assert.IsTrue(success.Authorized);
        Assert.IsTrue(gate.IsAuthorized);
        var alreadyAuthorized = await gate.TryAuthorizeAsync();
        Assert.IsTrue(alreadyAuthorized.Authorized);
        Assert.AreEqual(3, saveCalls);
    }

    private static ProjectInfo Project(string name) =>
        new(name, $@"C:\Projects\{name}", 1, 1, true);

    private static TimelineEntryModel Entry(double start) =>
        new()
        {
            ClipId = "clip_1",
            ClipName = "clip",
            FilePath = @"C:\Projects\A\clip.mp4",
            StartTime = start,
            EndTime = start + 1,
        };

    private static async Task<StatusResponse?> WaitForCancellationAsync(
        CancellationToken cancellationToken)
    {
        await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
        return null;
    }

    private static void Ready(TimelineViewModel viewModel) =>
        typeof(TimelineViewModel)
            .GetField(
                "_timelineReadyForMutation",
                BindingFlags.Instance | BindingFlags.NonPublic)!
            .SetValue(viewModel, true);

    private sealed class RecordingFlushCoordinator(
        Func<Task<TimelineFlushResult>> flush) : ITimelineFlushCoordinator
    {
        public IDisposable Register(
            Dispatcher dispatcher,
            Func<CancellationToken, Task<TimelineFlushResult>> flushAsync) =>
            new NoopRegistration();

        public Task<TimelineFlushResult> FlushAsync(
            CancellationToken cancellationToken = default) => flush();

        private sealed class NoopRegistration : IDisposable
        {
            public void Dispose() { }
        }
    }

    private sealed class TimelineFixture : IDisposable
    {
        private TimelineFixture(TimelineViewModel viewModel) =>
            ViewModel = viewModel;

        public TimelineViewModel ViewModel { get; }

        public static TimelineFixture Create(
            IApiClient api,
            ProjectService projects) =>
            new(new TimelineViewModel(
                new TimelineStateService(
                    api,
                    NullLogger<TimelineStateService>.Instance,
                    projects),
                new AudioLibraryStateService(
                    api,
                    NullLogger<AudioLibraryStateService>.Instance),
                api,
                projects));

        public void Dispose() => ViewModel.Dispose();
    }
}
