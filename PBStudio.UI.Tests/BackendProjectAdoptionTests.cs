using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.Tests;

// 2026-10-01: a project opened via API/chat tool left the WPF on its old state
// (AUDIO tab empty although the backend had the mix loaded).
[TestClass]
[DoNotParallelize]
public sealed class BackendProjectAdoptionTests
{
    private sealed class Recipient { }

    [TestMethod]
    public async Task BackendOpenedProjectIsAdoptedOnceAndClosedAgain()
    {
        var project = new ProjectInfo("t013", @"C:\Projects\t013", 1, 56, true);
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.GetProjectInfoAsync), _ => Task.FromResult<ProjectInfo?>(project));
        using var projects = new ProjectService(api.Client, NullLogger<ProjectService>.Instance);
        var recipient = new Recipient();
        var opened = 0;
        var closed = 0;
        WeakReferenceMessenger.Default.Register<Recipient, ProjectOpenedMessage>(recipient, (_, _) => opened++);
        WeakReferenceMessenger.Default.Register<Recipient, ProjectClosedMessage>(recipient, (_, _) => closed++);
        try
        {
            await projects.AdoptBackendProjectAsync("opened", project.Path);
            await projects.AdoptBackendProjectAsync("opened", project.Path);

            Assert.AreEqual(project.Path, projects.CurrentProject?.Path);
            Assert.AreEqual(1, opened, "same path must not re-publish");

            await projects.AdoptBackendProjectAsync("closed", "");

            Assert.IsNull(projects.CurrentProject);
            Assert.AreEqual(1, closed);
        }
        finally
        {
            WeakReferenceMessenger.Default.UnregisterAll(recipient);
        }
    }

    [TestMethod]
    public async Task MismatchedBackendInfoIsNotAdopted()
    {
        var other = new ProjectInfo("x", @"C:\Projects\x", 0, 0, false);
        var api = ApiClientHarness.Create()
            .Handle(nameof(IApiClient.GetProjectInfoAsync), _ => Task.FromResult<ProjectInfo?>(other));
        using var projects = new ProjectService(api.Client, NullLogger<ProjectService>.Instance);

        await projects.AdoptBackendProjectAsync("opened", @"C:\Projects\t013");

        Assert.IsNull(projects.CurrentProject);
    }
}
