using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class ViewModelAndProjectServiceTests
{
    [TestMethod]
    public async Task ChatClear_BackendFalsePreservesLocalMessages()
    {
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.ClearChatHistoryAsync),
                _ => Task.FromResult(false));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        using var viewModel = new ChatViewModel(api.Client, projects);
        var originalWelcome = viewModel.Messages.Single();

        await viewModel.ClearAsync();

        Assert.AreEqual(1, viewModel.Messages.Count);
        Assert.AreSame(originalWelcome, viewModel.Messages.Single());
        StringAssert.Contains(viewModel.StatusText, "konnte nicht");
    }

    [TestMethod]
    public async Task ChatClear_BackendTrueReplacesHistoryWithFreshWelcome()
    {
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.ClearChatHistoryAsync),
                _ => Task.FromResult(true));
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        using var viewModel = new ChatViewModel(api.Client, projects);
        var originalWelcome = viewModel.Messages.Single();

        await viewModel.ClearAsync();

        Assert.AreEqual(1, viewModel.Messages.Count);
        Assert.AreNotSame(originalWelcome, viewModel.Messages.Single());
        Assert.AreEqual("History geleert.", viewModel.StatusText);
    }

    [TestMethod]
    public void SettingsLoadFailure_IsImmediatelyVisibleToViewModel()
    {
        var settings = new SettingsServiceStub
        {
            LoadResult = new SettingsLoadResult(
                false,
                false,
                SettingsPersistenceFailure.MalformedJson,
                "Settings beschädigt."),
        };
        using var viewModel = new SettingsViewModel(
            ApiClientHarness.Create().Client,
            new DialogServiceStub(),
            settings);

        Assert.AreEqual("Settings beschädigt.", viewModel.SettingsPersistenceError);
    }

    [TestMethod]
    public async Task SettingsSaveFailure_NeverReportsSuccess()
    {
        var projectRoot = RepositoryLayout.FindProjectRoot();
        using var backendEnvironment = new EnvironmentVariableScope(
            "PBSTUDIO_BACKEND_DIR",
            System.IO.Path.Combine(projectRoot, "backend"));
        var settings = new SettingsServiceStub
        {
            SaveResult = new SettingsSaveResult(
                false,
                SettingsPersistenceFailure.WriteFailed,
                "Atomarer Write fehlgeschlagen."),
        };
        using var viewModel = new SettingsViewModel(
            ApiClientHarness.Create().Client,
            new DialogServiceStub(),
            settings);

        await viewModel.SaveSettingsCommand.ExecuteAsync(null);

        Assert.AreEqual("Atomarer Write fehlgeschlagen.", viewModel.SettingsPersistenceError);
        Assert.IsFalse(
            viewModel.StatusText.Contains(
                "Einstellungen gespeichert",
                StringComparison.Ordinal));
    }

    [TestMethod]
    public async Task GpuCleanup_BackendFailureNeverReportsCompletion()
    {
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.CleanupGpuAsync),
                _ => Task.FromResult<GpuCleanupResponse?>(
                    new GpuCleanupResponse(false, 0, "Modelle aktiv")));
        using var viewModel = new SettingsViewModel(
            api.Client,
            new DialogServiceStub(),
            new SettingsServiceStub());

        await viewModel.CleanupGpuCommand.ExecuteAsync(null);

        StringAssert.Contains(viewModel.StatusText, "fehlgeschlagen");
        StringAssert.Contains(viewModel.StatusText, "Modelle aktiv");
        Assert.IsFalse(
            viewModel.StatusText.Contains(
                "abgeschlossen",
                StringComparison.Ordinal));
    }

    [TestMethod]
    public async Task Recommendation_LateOlderModeCannotReplaceCurrentMode()
    {
        var calls = new List<(string Mode, TaskCompletionSource<ModelRecommendationResponse?> Completion)>();
        var callGate = new object();
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.GetModelRecommendationAsync), args =>
            {
                var completion = new TaskCompletionSource<ModelRecommendationResponse?>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
                lock (callGate)
                    calls.Add(((string)args![1]!, completion));
                return completion.Task;
            });
        using var viewModel = new SettingsViewModel(
            api.Client,
            new DialogServiceStub(),
            new SettingsServiceStub());

        viewModel.KiModeIndex = 0;
        await TestWait.UntilAsync(() =>
        {
            lock (callGate)
                return calls.Count == 1;
        });
        viewModel.KiModeIndex = 2;
        await TestWait.UntilAsync(() =>
        {
            lock (callGate)
                return calls.Count == 2;
        });

        (string Mode, TaskCompletionSource<ModelRecommendationResponse?> Completion) speed;
        (string Mode, TaskCompletionSource<ModelRecommendationResponse?> Completion) quality;
        lock (callGate)
        {
            speed = calls.Single(call => call.Mode == "speed");
            quality = calls.Single(call => call.Mode == "quality");
        }
        quality.Completion.SetResult(Recommendation("quality", "quality-model"));
        await TestWait.UntilAsync(
            () => viewModel.KiModeAutoSelectionText.Contains(
                "quality-model",
                StringComparison.Ordinal));
        speed.Completion.SetResult(Recommendation("speed", "stale-speed-model"));
        await Task.Delay(50);

        StringAssert.Contains(viewModel.KiModeAutoSelectionText, "quality-model");
        Assert.IsFalse(
            viewModel.KiModeAutoSelectionText.Contains(
                "stale-speed-model",
                StringComparison.Ordinal));
    }

    [TestMethod]
    public async Task Recommendation_ProjectSwitchRejectsOldProjectResult()
    {
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 0, 0, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 0, 0, false);
        var nextProject = projectA;
        var completions = new List<TaskCompletionSource<ModelRecommendationResponse?>>();
        var callGate = new object();
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject))
            .Handle(nameof(IApiClient.GetModelRecommendationAsync), _ =>
            {
                var completion = new TaskCompletionSource<ModelRecommendationResponse?>(
                    TaskCreationOptions.RunContinuationsAsynchronously);
                lock (callGate)
                    completions.Add(completion);
                return completion.Task;
            });
        using var projects = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await projects.OpenProjectAsync(projectA.Path));
        using var viewModel = new SettingsViewModel(
            api.Client,
            new DialogServiceStub(),
            new SettingsServiceStub(),
            projects);

        viewModel.KiModeIndex = 0;
        await TestWait.UntilAsync(() =>
        {
            lock (callGate)
                return completions.Count == 1;
        });
        nextProject = projectB;
        Assert.IsTrue(await projects.OpenProjectAsync(projectB.Path));
        await TestWait.UntilAsync(() =>
        {
            lock (callGate)
                return completions.Count >= 3;
        });

        TaskCompletionSource<ModelRecommendationResponse?> current;
        TaskCompletionSource<ModelRecommendationResponse?>[] stale;
        lock (callGate)
        {
            current = completions[^1];
            stale = completions.Take(completions.Count - 1).ToArray();
        }
        current.SetResult(Recommendation("speed", "project-b-model"));
        await TestWait.UntilAsync(
            () => viewModel.KiModeAutoSelectionText.Contains(
                "project-b-model",
                StringComparison.Ordinal));
        foreach (var completion in stale)
            completion.SetResult(Recommendation("speed", "stale-project-a-model"));
        await Task.Delay(50);

        StringAssert.Contains(viewModel.KiModeAutoSelectionText, "project-b-model");
        Assert.IsFalse(
            viewModel.KiModeAutoSelectionText.Contains(
                "stale-project-a-model",
                StringComparison.Ordinal));
    }

    [TestMethod]
    public async Task ProjectSaveAndClose_NegativeResultsPreserveProject()
    {
        var project = new ProjectInfo(
            "A",
            @"C:\Projects\A",
            1,
            2,
            true);
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(project))
            .Handle(
                nameof(IApiClient.SaveProjectAsync),
                _ => Task.FromResult<StatusResponse?>(
                    new StatusResponse(false, "disk full")))
            .Handle(
                nameof(IApiClient.CloseProjectAsync),
                _ => Task.FromResult<StatusResponse?>(
                    new StatusResponse(false, "busy")));
        using var service = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await service.OpenProjectAsync(project.Path));

        var saved = await service.SaveProjectAsync();
        var closed = await service.CloseProjectAsync();

        Assert.IsFalse(saved);
        Assert.IsFalse(closed);
        Assert.AreSame(project, service.CurrentProject);
        Assert.IsTrue(service.HasProject);
    }

    [TestMethod]
    public async Task ProjectSwitch_InvalidatesCapturedOperationContext()
    {
        var projectA = new ProjectInfo("A", @"C:\Projects\A", 0, 0, false);
        var projectB = new ProjectInfo("B", @"C:\Projects\B", 0, 0, false);
        var nextProject = projectA;
        var api = ApiClientHarness.Create()
            .Handle(
                nameof(IApiClient.OpenProjectAsync),
                _ => Task.FromResult<ProjectInfo?>(nextProject));
        using var service = new ProjectService(
            api.Client,
            NullLogger<ProjectService>.Instance);
        Assert.IsTrue(await service.OpenProjectAsync(projectA.Path));
        var contextA = service.CaptureOperationContext();

        nextProject = projectB;
        Assert.IsTrue(await service.OpenProjectAsync(projectB.Path));

        Assert.IsTrue(contextA.CancellationToken.IsCancellationRequested);
        Assert.IsFalse(service.IsCurrent(contextA));
        var contextB = service.CaptureOperationContext();
        Assert.IsTrue(service.IsCurrent(contextB));
        Assert.AreEqual(projectB.Path, contextB.ProjectPath);
        Assert.IsTrue(contextB.Generation > contextA.Generation);
    }

    private static ModelRecommendationResponse Recommendation(
        string mode,
        string model) =>
        new(
            "video_captioning",
            mode,
            model,
            "selected",
            [model],
            null,
            [model],
            "ollama",
            ["vision"],
            ["vision"],
            "automatic");
}
