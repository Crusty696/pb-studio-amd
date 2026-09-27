using System.Reflection;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class ProductionRenderRecoveryTests
{
    [TestMethod]
    public void ReplayGap_ReconcilesRenderStatusWithoutGlobalApplication()
    {
        StaTest.Run(() => RunOnStaDispatcherAsync().GetAwaiter().GetResult());
    }

    [TestMethod]
    public void ReplayGap_DropsStatusResponseForSupersededRenderTask()
    {
        StaTest.Run(() => RunSupersededTaskOnStaDispatcherAsync().GetAwaiter().GetResult());
    }

    private static async Task RunOnStaDispatcherAsync()
    {
        Assert.IsNull(Application.Current, "Test must exercise dispatcher fallback without global WPF Application.");
        var dispatcher = Dispatcher.CurrentDispatcher;
        SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));

        var statusCalls = 0;
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.GetRenderStatusAsync), arguments =>
            {
                Assert.AreEqual("render-gap-1", arguments![0]);
                statusCalls++;
                return Task.FromResult<RenderProgress?>(new RenderProgress(
                    "render-gap-1",
                    "completed",
                    100.0,
                    120,
                    120,
                    30.0,
                    4.0,
                    0.0,
                    @"C:\Projects\QA\final.mp4",
                    null,
                    Message: "Render nach SSE-Lücke vollständig"));
            });

        using var projects = new ProjectService(api.Client, NullLogger<ProjectService>.Instance);
        using var sse = new SSEClient(NullLogger<SSEClient>.Instance, new TerminalLogBuffer());
        using var viewModel = new ProductionViewModel(
            api.Client,
            sse,
            new TimelineStateService(api.Client, NullLogger<TimelineStateService>.Instance, projects),
            projects,
            new DialogServiceStub());

        InvokeRenderProgress(viewModel, new ProgressEventArgs
        {
            EventType = "render_progress",
            TaskId = "render-gap-1",
            Status = "running",
            ProgressPercent = 42.0,
            Message = "Rendering läuft",
        });
        await PumpUntilAsync(dispatcher, () => viewModel.RenderProgress == 42.0);

        var streamKind = typeof(SSEClient).GetNestedType("StreamKind", BindingFlags.NonPublic)!;
        var progressStream = Enum.Parse(streamKind, "Progress");
        var processEvent = typeof(SSEClient).GetMethod("TryProcessEvent", BindingFlags.Instance | BindingFlags.NonPublic)!;
        var accepted = (bool)processEvent.Invoke(
            sse,
            [progressStream, "replay_gap", "{\"first_missing_id\":7,\"last_missing_id\":9}"])!;
        Assert.IsTrue(accepted);

        await PumpUntilAsync(
            dispatcher,
            () => !viewModel.IsRendering && viewModel.StatusText == "Render nach SSE-Lücke vollständig");

        Assert.AreEqual(1, statusCalls);
        Assert.AreEqual(100.0, viewModel.RenderProgress);
        Assert.AreEqual(string.Empty, viewModel.EtaText);
        Assert.IsTrue(viewModel.RenderLogEntries.Any(line => line.Contains("final.mp4", StringComparison.Ordinal)));
        SynchronizationContext.SetSynchronizationContext(null);
    }

    private static async Task RunSupersededTaskOnStaDispatcherAsync()
    {
        Assert.IsNull(Application.Current, "Test must exercise dispatcher fallback without global WPF Application.");
        var dispatcher = Dispatcher.CurrentDispatcher;
        SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));

        var requestedTaskId = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
        var delayedStatus = new TaskCompletionSource<RenderProgress?>(TaskCreationOptions.RunContinuationsAsynchronously);
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.GetRenderStatusAsync), arguments =>
            {
                requestedTaskId.TrySetResult((string)arguments![0]!);
                return delayedStatus.Task;
            });

        using var projects = new ProjectService(api.Client, NullLogger<ProjectService>.Instance);
        using var sse = new SSEClient(NullLogger<SSEClient>.Instance, new TerminalLogBuffer());
        using var viewModel = new ProductionViewModel(
            api.Client,
            sse,
            new TimelineStateService(api.Client, NullLogger<TimelineStateService>.Instance, projects),
            projects,
            new DialogServiceStub());

        InvokeRenderProgress(viewModel, new ProgressEventArgs
        {
            EventType = "render_progress",
            TaskId = "render-old",
            Status = "running",
            ProgressPercent = 41.0,
            Message = "Alter Render läuft",
        });
        await PumpUntilAsync(dispatcher, () => viewModel.RenderProgress == 41.0);
        InvokeReplayGap(sse);
        Assert.AreEqual("render-old", await requestedTaskId.Task.WaitAsync(TimeSpan.FromSeconds(2)));

        typeof(ProductionViewModel)
            .GetField("_currentTaskId", BindingFlags.Instance | BindingFlags.NonPublic)!
            .SetValue(viewModel, "render-new");
        InvokeRenderProgress(viewModel, new ProgressEventArgs
        {
            EventType = "render_progress",
            TaskId = "render-new",
            Status = "running",
            ProgressPercent = 23.0,
            Message = "Neuer Render läuft",
        });
        await PumpUntilAsync(dispatcher, () => viewModel.RenderProgress == 23.0);

        delayedStatus.SetResult(new RenderProgress(
            "render-old",
            "completed",
            100.0,
            100,
            100,
            30.0,
            5.0,
            0.0,
            @"C:\Projects\QA\old.mp4",
            null,
            Message: "Veralteter Abschluss"));
        await PumpForAsync(dispatcher, TimeSpan.FromMilliseconds(100));

        Assert.IsTrue(viewModel.IsRendering);
        Assert.AreEqual(23.0, viewModel.RenderProgress);
        Assert.AreEqual("Neuer Render läuft", viewModel.StatusText);
        SynchronizationContext.SetSynchronizationContext(null);
    }

    private static void InvokeRenderProgress(ProductionViewModel viewModel, ProgressEventArgs args)
    {
        var handler = typeof(ProductionViewModel).GetMethod("OnRenderProgress", BindingFlags.Instance | BindingFlags.NonPublic)!;
        handler.Invoke(viewModel, [null, args]);
    }

    private static void InvokeReplayGap(SSEClient sse)
    {
        var streamKind = typeof(SSEClient).GetNestedType("StreamKind", BindingFlags.NonPublic)!;
        var progressStream = Enum.Parse(streamKind, "Progress");
        var processEvent = typeof(SSEClient).GetMethod("TryProcessEvent", BindingFlags.Instance | BindingFlags.NonPublic)!;
        var accepted = (bool)processEvent.Invoke(
            sse,
            [progressStream, "replay_gap", "{\"first_missing_id\":7,\"last_missing_id\":9}"])!;
        Assert.IsTrue(accepted);
    }

    private static async Task PumpUntilAsync(Dispatcher dispatcher, Func<bool> condition)
    {
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer(
            TimeSpan.FromMilliseconds(5),
            DispatcherPriority.Background,
            (_, _) =>
            {
                if (condition())
                    frame.Continue = false;
            },
            dispatcher);
        timer.Start();
        Dispatcher.PushFrame(frame);
        timer.Stop();
        Assert.IsTrue(condition(), "Dispatcher callback did not reach expected render state.");
        await Task.CompletedTask;
    }

    private static async Task PumpForAsync(Dispatcher dispatcher, TimeSpan duration)
    {
        var startedAt = DateTime.UtcNow;
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer(
            TimeSpan.FromMilliseconds(5),
            DispatcherPriority.Background,
            (_, _) =>
            {
                if (DateTime.UtcNow - startedAt >= duration)
                    frame.Continue = false;
            },
            dispatcher);
        timer.Start();
        Dispatcher.PushFrame(frame);
        timer.Stop();
        await Task.CompletedTask;
    }
}
