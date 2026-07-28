"""Static contracts for W9 WPF lifecycle and reachability fixes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "PBStudio.UI"


def _read(relative_path: str) -> str:
    return (UI / relative_path).read_text(encoding="utf-8")


def test_runtime_environment_is_applied_before_backend_start():
    app = _read("App.xaml.cs")
    bridge = _read("Services/PythonBridgeService.cs")

    assert "services.AddSingleton<ISettingsService, SettingsService>();" in app
    assert app.index("settings.Load();") < app.index("bridge.StartAsync()")
    assert app.index("PythonBridgeService.ApplyRuntimeEnvironment(settings.Current);") < app.index(
        "bridge.StartAsync()"
    )
    for setting in ("ForcedVramMb", "VramCapMb", "FfmpegPath"):
        assert setting in bridge[
            bridge.index("public static void ApplyRuntimeEnvironment"):
            bridge.index("public static void SetForcedVramEnvVar")
        ]


def test_app_exit_preserves_externally_managed_backend():
    app = _read("App.xaml.cs")
    on_exit = app[app.index("protected override void OnExit") :]

    assert 'Environment.GetEnvironmentVariable("PBSTUDIO_BACKEND_MANAGED_EXTERNALLY")' in on_exit
    assert on_exit.index("SaveProjectAsync()") < on_exit.index("BeginShutdown()")
    assert on_exit.index("BeginShutdown()") < on_exit.index("if (!externalBackendManaged)")
    assert on_exit.count("if (!externalBackendManaged)") == 2
    assert on_exit.index("if (!externalBackendManaged)") < on_exit.index("ShutdownAsync()")
    assert on_exit.rindex("if (!externalBackendManaged)") < on_exit.index("StopAsync()")


def test_audio_stems_and_pacing_use_project_generation_and_cancellation():
    project = _read("Services/ProjectService.cs")
    api_contract = _read("Services/IApiClient.cs")
    audio = _read("ViewModels/AudioLibraryViewModel.cs")
    director = _read("ViewModels/DirectorViewModel.cs")

    assert "ProjectOperationContext" in project
    assert "CaptureOperationContext()" in project
    assert "BeginProjectTransition();" in project
    assert "previous.Cancel();" in project
    assert "ProjectTransitionStarted" in project

    for signature in (
        "AnalyzeAudioAsync(int clipId, CancellationToken cancellationToken = default)",
        "SeparateStemsAsync(int clipId, string model = \"htdemucs.yaml\", CancellationToken cancellationToken = default)",
        "GenerateCutListAsync(PacingConfig config, CancellationToken cancellationToken = default)",
    ):
        assert signature in api_contract

    assert audio.count("_projectService.CaptureOperationContext()") == 3
    assert audio.count("operation.CancellationToken") >= 3
    assert audio.count("_projectService.IsCurrent(operation)") >= 6
    assert "ProjectTransitionStarted += OnProjectTransitionStarted" in audio

    assert "_projectService.CaptureOperationContext()" in director
    assert "GenerateCutListAsync(config, operation.CancellationToken)" in director
    assert "_projectService.IsCurrent(operation)" in director
    assert "ProjectTransitionStarted += OnProjectTransitionStarted" in director


def test_embedding_status_flows_from_list_dto_to_view():
    api = _read("Services/ApiClient.cs")
    model = _read("Models/VideoClip.cs")
    view_model = _read("ViewModels/VideoLibraryViewModel.cs")
    view = _read("Views/VideoLibraryView.xaml")

    for field in ("HasVideoEmbedding", "EmbeddingDim", "EmbeddingSamples", "HasEmbedding"):
        assert field in api
    assert "[ObservableProperty] private bool _hasEmbedding;" in model
    assert "HasEmbedding = c.HasEmbedding || c.HasVideoEmbedding" in view_model
    assert 'Binding="{Binding SelectedClip.HasEmbedding}"' in view
    assert 'Binding="{Binding SelectedClip.HasCacheHash}" Value="False"' not in view


def test_timeline_asset_load_is_deduplicated_and_cancellable():
    api_contract = _read("Services/IApiClient.cs")
    timeline = _read("ViewModels/TimelineViewModel.cs")

    assert "Dictionary<TimelineEntryModel, Task> _assetLoads" in timeline
    assert "_assetLoads.TryGetValue(entry, out var existing)" in timeline
    assert "LoadClipAssetsAsync(entry, _assetLoadCts.Token)" in timeline
    assert timeline.count("_ = QueueClipAssetLoad(") == 2
    assert "GetThumbStripAsync(cid, n: 8, cancellationToken: ct)" in timeline
    assert "GetClipWaveAsync(cid, n: 256, cancellationToken: ct)" in timeline
    assert "CancelAssetLoads();" in timeline
    assert "CancellationToken cancellationToken = default" in api_contract


def test_brain_selection_and_navigation_controls_are_reachable():
    brain_vm = _read("ViewModels/BrainViewModel.cs")
    brain_view = _read("Views/BrainView.xaml")
    main = _read("MainWindow.xaml")
    timeline_view = _read("Views/TimelineView.xaml")

    assert "OnSelectedLearningSessionCutChanged" in brain_vm
    assert "SelectedCutId = value?.CutId ?? 0;" in brain_vm
    assert 'SelectedItem="{Binding SelectedLearningSessionCut, Mode=TwoWay}"' in brain_view

    assert '<views:MediaIngestView/>' in main
    assert '<views:AnchorView/>' in main
    assert 'Command="{Binding PreviousCutCommand}"' in timeline_view
    assert 'Command="{Binding NextCutCommand}"' in timeline_view
