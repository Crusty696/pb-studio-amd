using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class TimelineViewModelTests
{
    [TestMethod]
    public void KeyboardSelectionAndScrub_UseTimelineOrderAndClampBounds()
    {
        using var fixture = TimelineFixture.Create();
        var late = Entry("late", 4, 6);
        var early = Entry("early", 0, 2);
        fixture.ViewModel.TimelineEntries.Add(late);
        fixture.ViewModel.TimelineEntries.Add(early);
        fixture.ViewModel.TotalDuration = 6;

        Assert.IsTrue(fixture.ViewModel.SelectFirstCut());
        Assert.AreSame(early, fixture.ViewModel.SelectedEntry);
        Assert.AreEqual(0.0, fixture.ViewModel.SelectedTimelinePosition);
        Assert.IsTrue(fixture.ViewModel.SelectLastCut());
        Assert.AreSame(late, fixture.ViewModel.SelectedEntry);
        Assert.IsTrue(fixture.ViewModel.ScrubTimelineBy(10));
        Assert.AreEqual(6.0, fixture.ViewModel.SelectedTimelinePosition);
        Assert.IsFalse(fixture.ViewModel.ScrubTimelineBy(1));
    }

    [TestMethod]
    public void KeyboardNudge_ClampsAtAdjacentCutsAndPreservesDuration()
    {
        using var fixture = TimelineFixture.Create();
        var first = Entry("first", 0, 1);
        var selected = Entry("selected", 2, 3);
        var last = Entry("last", 4, 5);
        fixture.ViewModel.TimelineEntries.Add(first);
        fixture.ViewModel.TimelineEntries.Add(selected);
        fixture.ViewModel.TimelineEntries.Add(last);
        fixture.ViewModel.TotalDuration = 5;
        fixture.ViewModel.SelectedEntry = selected;

        Assert.IsTrue(fixture.ViewModel.NudgeSelectedCutBy(-0.5));
        Assert.AreEqual(1.5, selected.StartTime);
        Assert.AreEqual(2.5, selected.EndTime);
        Assert.AreEqual(1.0, selected.Duration);
        Assert.IsTrue(fixture.ViewModel.NudgeSelectedCutBy(10));
        Assert.AreEqual(3.0, selected.StartTime);
        Assert.AreEqual(4.0, selected.EndTime);
        Assert.IsFalse(fixture.ViewModel.NudgeSelectedCutBy(0.5));
    }

    [TestMethod]
    public void KeyboardTrim_RespectsSourcePreviousNextAndMinimumDuration()
    {
        using var fixture = TimelineFixture.Create();
        var previous = Entry("previous", 0, 1);
        var selected = Entry("selected", 2, 4, clipStart: 1);
        var next = Entry("next", 5, 7);
        fixture.ViewModel.TimelineEntries.Add(previous);
        fixture.ViewModel.TimelineEntries.Add(selected);
        fixture.ViewModel.TimelineEntries.Add(next);
        fixture.ViewModel.TotalDuration = 7;
        fixture.ViewModel.SelectedEntry = selected;

        Assert.IsTrue(fixture.ViewModel.TrimSelectedCutStartBy(-5));
        Assert.AreEqual(1.0, selected.StartTime);
        Assert.AreEqual(0.0, selected.ClipStart);
        Assert.IsFalse(fixture.ViewModel.TrimSelectedCutStartBy(-0.1));
        Assert.IsTrue(fixture.ViewModel.TrimSelectedCutEndBy(5));
        Assert.AreEqual(5.0, selected.EndTime);
        Assert.IsFalse(fixture.ViewModel.TrimSelectedCutEndBy(0.1));
    }

    [TestMethod]
    public void UnsafeKeyboardRemoval_DoesNotMutateTimeline()
    {
        using var fixture = TimelineFixture.Create();
        var selected = Entry("selected", 0, 2);
        fixture.ViewModel.TimelineEntries.Add(selected);
        fixture.ViewModel.SelectedEntry = selected;

        fixture.ViewModel.RejectUnsafeTimelineRemoval();

        Assert.AreEqual(1, fixture.ViewModel.TimelineEntries.Count);
        Assert.AreSame(selected, fixture.ViewModel.TimelineEntries.Single());
        StringAssert.Contains(fixture.ViewModel.StatusText, "nicht entfernt");
    }

    [TestMethod]
    public void SortEntriesByTime_PreservesSelectedEntryIdentity()
    {
        using var fixture = TimelineFixture.Create();
        var late = Entry("late", 5, 6);
        var early = Entry("early", 1, 2);
        fixture.ViewModel.TimelineEntries.Add(late);
        fixture.ViewModel.TimelineEntries.Add(early);
        fixture.ViewModel.SelectedEntry = late;

        fixture.ViewModel.SortEntriesByTime();

        Assert.AreSame(early, fixture.ViewModel.TimelineEntries[0]);
        Assert.AreSame(late, fixture.ViewModel.TimelineEntries[1]);
        Assert.AreSame(late, fixture.ViewModel.SelectedEntry);
        Assert.AreEqual("Cut 2 / 2", fixture.ViewModel.SelectionIndexText);
    }

    private static TimelineEntryModel Entry(
        string name,
        double start,
        double end,
        double clipStart = 0) =>
        new()
        {
            ClipId = name,
            ClipName = name,
            FilePath = "",
            StartTime = start,
            EndTime = end,
            ClipStart = clipStart,
            IsAssetsLoaded = true,
        };

    private sealed class TimelineFixture : IDisposable
    {
        private TimelineFixture(
            TimelineViewModel viewModel,
            ProjectService projects)
        {
            ViewModel = viewModel;
            Projects = projects;
        }

        public TimelineViewModel ViewModel { get; }
        private ProjectService Projects { get; }

        public static TimelineFixture Create()
        {
            var api = ApiClientHarness.Create().Client;
            var projects = new ProjectService(
                api,
                NullLogger<ProjectService>.Instance);
            var viewModel = new TimelineViewModel(
                new TimelineStateService(
                    api,
                    NullLogger<TimelineStateService>.Instance,
                    projects),
                new AudioLibraryStateService(
                    api,
                    NullLogger<AudioLibraryStateService>.Instance),
                api,
                projects);
            return new TimelineFixture(viewModel, projects);
        }

        public void Dispose()
        {
            ViewModel.Dispose();
            Projects.Dispose();
        }
    }
}
