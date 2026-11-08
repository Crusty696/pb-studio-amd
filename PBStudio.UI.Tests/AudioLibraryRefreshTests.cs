using System.Collections.Specialized;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class AudioLibraryRefreshTests
{
    [TestMethod]
    public void UnchangedRefreshPreservesMultipleSelectionWithoutCollectionChanges()
        => StaTest.Run(() =>
        {
            using var fixture = new LibraryFixture();
            fixture.Refresh();
            var original = fixture.ViewModel.AudioClips.ToArray();
            fixture.List.SelectedItems.Add(original[0]);
            fixture.List.SelectedItems.Add(original[1]);
            var changes = 0;
            fixture.ViewModel.AudioClips.CollectionChanged += (_, _) => changes++;

            fixture.Refresh();

            CollectionAssert.AreEqual(original, fixture.ViewModel.AudioClips.ToArray());
            CollectionAssert.AreEquivalent(new[] { 1, 2 }, fixture.SelectedIds());
            CollectionAssert.AreEquivalent(new[] { 1, 2 },
                fixture.ViewModel.SelectedClips.Select(c => c.Id).ToArray());
            Assert.AreEqual(0, changes, "An unchanged snapshot must not rebuild the bound collection.");
        });

    [TestMethod]
    public void RefreshUpdatesExistingModelAndSelectedDetails()
        => StaTest.Run(() =>
        {
            using var fixture = new LibraryFixture();
            fixture.Refresh();
            var selected = fixture.ViewModel.AudioClips[0];
            fixture.List.SelectedItems.Add(selected);
            fixture.Response = [Clip(1) with
            {
                Name = "Updated", DurationSeconds = 95, Bpm = 142, Key = "Am",
                BeatCount = 123, IsAnalyzed = true, AnalysisStatus = "partial",
                AudioHash = "hash", StemsPaths = new() { ["drums"] = @"C:\Test\drums.wav" },
                StageErrors = new() { ["key"] = "incomplete" },
            }, Clip(2), Clip(3)];
            fixture.State.Clear();

            fixture.Refresh();

            Assert.AreSame(selected, fixture.ViewModel.AudioClips[0]);
            Assert.AreEqual("Updated", selected.Name);
            Assert.AreEqual(142d, fixture.ViewModel.Bpm);
            Assert.AreEqual("Am", fixture.ViewModel.Key);
            Assert.AreEqual(123, fixture.ViewModel.BeatCount);
            Assert.AreEqual(95d, fixture.ViewModel.DurationSeconds);
            Assert.AreEqual("partial", selected.AnalysisStatus);
            Assert.AreEqual("incomplete", selected.StageErrors!["key"]);
            Assert.IsTrue(selected.HasCacheHash);
            Assert.IsTrue(selected.HasStems);
        });

    [TestMethod]
    public void RefreshRemovesMissingClipsAndReordersWithoutLosingSurvivingSelection()
        => StaTest.Run(() =>
        {
            using var fixture = new LibraryFixture();
            fixture.Refresh();
            var first = fixture.ViewModel.AudioClips[0];
            var third = fixture.ViewModel.AudioClips[2];
            foreach (var clip in fixture.ViewModel.AudioClips)
                fixture.List.SelectedItems.Add(clip);
            var resets = 0;
            fixture.ViewModel.AudioClips.CollectionChanged += (_, e) =>
            {
                if (e.Action == NotifyCollectionChangedAction.Reset) resets++;
            };
            fixture.Response = [Clip(3), Clip(4), Clip(1)];
            fixture.State.Clear();

            fixture.Refresh();

            CollectionAssert.AreEqual(new[] { 3, 4, 1 },
                fixture.ViewModel.AudioClips.Select(c => c.Id).ToArray());
            Assert.AreSame(third, fixture.ViewModel.AudioClips[0]);
            Assert.AreSame(first, fixture.ViewModel.AudioClips[2]);
            CollectionAssert.AreEquivalent(new[] { 1, 3 }, fixture.SelectedIds());
            CollectionAssert.AreEquivalent(new[] { 1, 3 },
                fixture.ViewModel.SelectedClips.Select(c => c.Id).ToArray());
            Assert.AreEqual(0, resets);
        });

    [TestMethod]
    public void ProjectTransitionDoesNotReuseModelOrSelectionForSameClipId()
        => StaTest.Run(() =>
        {
            using var fixture = new LibraryFixture();
            fixture.Refresh();
            var old = fixture.ViewModel.AudioClips[0];
            fixture.List.SelectedItems.Add(old);
            fixture.Project = new ProjectInfo("B", @"C:\Projects\B", 1, 0, false);
            fixture.Response = [Clip(1) with { Name = "B clip", Path = @"C:\Projects\B\clip.wav" }];
            // Keep the real transition event, avoid unrelated messenger-driven auto-loads.
            WeakReferenceMessenger.Default.UnregisterAll(fixture.ViewModel);
            Pump(fixture.Projects.OpenProjectAsync(fixture.Project.Path));

            fixture.Refresh();

            Assert.AreNotSame(old, fixture.ViewModel.AudioClips.Single());
            Assert.AreEqual("B clip", fixture.ViewModel.AudioClips.Single().Name);
            Assert.AreEqual(0, fixture.List.SelectedItems.Count);
            Assert.AreEqual(0, fixture.ViewModel.SelectedClips.Count);
            Assert.IsNull(fixture.ViewModel.SelectedClip);
        });

    [TestMethod]
    public void QueuedRefreshCannotPublishAfterProjectTransition()
        => StaTest.Run(() =>
        {
            using var fixture = new LibraryFixture();
            // The synchronous API response has completed; InvokeAsync has queued
            // publication, but this STA has not pumped the dispatcher yet.
            var pendingRefresh = fixture.ViewModel.LoadAudioClipsCommand.ExecuteAsync(null);
            Assert.IsFalse(pendingRefresh.IsCompleted);
            Assert.AreEqual(3, fixture.State.CurrentAudioClips.Count);
            Assert.AreEqual(0, fixture.ViewModel.AudioClips.Count);

            WeakReferenceMessenger.Default.UnregisterAll(fixture.ViewModel);
            fixture.Project = new ProjectInfo("B", @"C:\Projects\B", 1, 0, false);
            var transition = fixture.Projects.OpenProjectAsync(fixture.Project.Path);
            Assert.IsTrue(transition.IsCompletedSuccessfully,
                "The transition must complete before pumping the old publication.");
            Assert.IsTrue(transition.GetAwaiter().GetResult());
            var current = new AudioClipModel { Id = 1, Name = "B clip" };
            fixture.ViewModel.AudioClips.Add(current);
            fixture.ViewModel.StatusText = "Projekt B aktiv";

            Pump(pendingRefresh);

            Assert.AreSame(current, fixture.ViewModel.AudioClips.Single());
            Assert.AreEqual("B clip", current.Name);
            Assert.AreEqual("Projekt B aktiv", fixture.ViewModel.StatusText);
        });

    private static AudioClipInfo Clip(int id) => new(
        id, $"Clip {id}", $@"C:\Projects\A\{id}.wav", 60, 44100, 2, "wav");

    private static void Pump(Task task)
    {
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromMilliseconds(5),
        };
        var deadline = DateTime.UtcNow.AddSeconds(5);
        timer.Tick += (_, _) =>
        {
            if (task.IsCompleted || DateTime.UtcNow >= deadline) frame.Continue = false;
        };
        timer.Start();
        try { Dispatcher.PushFrame(frame); }
        finally { timer.Stop(); }
        Assert.IsTrue(task.IsCompleted, "UI command did not finish.");
        task.GetAwaiter().GetResult();
    }

    private sealed class LibraryFixture : IDisposable
    {
        public List<AudioClipInfo> Response = [Clip(1), Clip(2), Clip(3)];
        public ProjectInfo Project = new("A", @"C:\Projects\A", 3, 0, false);
        public ProjectService Projects { get; }
        public AudioLibraryStateService State { get; }
        public AudioLibraryViewModel ViewModel { get; }
        public ListBox List { get; }
        private readonly SSEClient _sse;

        public LibraryFixture()
        {
            SynchronizationContext.SetSynchronizationContext(
                new DispatcherSynchronizationContext(Dispatcher.CurrentDispatcher));
            var api = ApiClientHarness.Create()
                .Handle(nameof(IApiClient.OpenProjectAsync), _ => Task.FromResult<ProjectInfo?>(Project))
                .Handle(nameof(IApiClient.GetAudioClipsAsync), _ => Task.FromResult<List<AudioClipInfo>?>(Response));
            Projects = new ProjectService(api.Client, NullLogger<ProjectService>.Instance);
            Pump(Projects.OpenProjectAsync(Project.Path));
            State = new AudioLibraryStateService(api.Client, NullLogger<AudioLibraryStateService>.Instance);
            _sse = new SSEClient(NullLogger<SSEClient>.Instance, new TerminalLogBuffer());
            ViewModel = new AudioLibraryViewModel(api.Client, State, _sse, new DialogServiceStub(), Projects);
            List = new ListBox { DataContext = ViewModel, SelectionMode = SelectionMode.Extended };
            List.SetBinding(ItemsControl.ItemsSourceProperty, new Binding(nameof(ViewModel.AudioClips)));
            List.SetBinding(System.Windows.Controls.Primitives.Selector.SelectedItemProperty,
                new Binding(nameof(ViewModel.SelectedClip)) { Mode = BindingMode.TwoWay });
            List.SelectionChanged += (_, _) => ViewModel.UpdateSelectedClips(List.SelectedItems);
        }

        public int[] SelectedIds() => List.SelectedItems.Cast<AudioClipModel>().Select(c => c.Id).ToArray();
        public void Refresh() => Pump(ViewModel.LoadAudioClipsCommand.ExecuteAsync(null));
        public void Dispose()
        {
            ViewModel.Dispose();
            _sse.Dispose();
            Projects.Dispose();
            SynchronizationContext.SetSynchronizationContext(null);
        }
    }
}
