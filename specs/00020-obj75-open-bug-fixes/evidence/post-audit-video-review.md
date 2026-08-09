# T049 Post-Audit Video/UI Review

**Status:** PASS

## Confirmed post-audit findings and remediation

1. VLM cold-start lock survived a failed receipt for the whole batch task and
   could self-block A→B→A. Lock ownership is now limited to one receipt attempt
   and released in `finally`.
2. Valid partial Caption tags and `tag_source` were discarded by the stage merge,
   leaving stale Force-Retry tags. Partial Caption payload is now merged and
   persisted with honest partial status.
3. `VideoLibraryViewModel.ClearClips()` retained `SelectedClips`, allowing reused
   IDs from project B to become batch targets. It now unmarks clips, clears batch
   selection and refreshes command state.

## Parent verification

```text
PYTHONPATH=src .venv\Scripts\python.exe -m pytest \
  Tests\test_lmstudio_vision_wrapper.py Tests\test_video_pipeline_truth.py \
  Tests\test_video_analysis_resume.py -q
```

Result: **48 passed**, 4 third-party deprecation warnings, 25.26 s.

```text
dotnet test PBStudio.UI.Tests\PBStudio.UI.Tests.csproj -c Release \
  --filter "FullyQualifiedName~Video" --nologo
```

Result: **3 passed**, 0 failed, 0 skipped; Release build succeeded.

## Completed VLM live receipt

- LM Studio reported four installed non-audio Vision candidates:
  `qwen2.5-vl-7b-instruct`, `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive`,
  `qwen3.5-9b` and `ministral-3-14b-reasoning-2512`.
- Only `qwen2.5-vl-7b-instruct` was loaded. A screenshot produced ten tags with
  a 3.625-s loading heartbeat and 4.593-s active phase.
- One frame from an existing catalog video also produced ten tags; loading
  heartbeat 1.313 s, active phase 2.172 s.
- The smoke model was unloaded and the specifically started LM Studio server
  was stopped. No model was downloaded or deleted.

## Completed A→B UI live receipt

- Release regression
  `VideoSelection_ProjectClosingClearsBatchStateBeforeReusedId`: **1/1 PASS**.
- `Tests/gui_project_switch_selection_smoke.py`: **PASS**.
- Projekt A: 3 Clips, davon 2 selektiert. Projekt B: 1 Clip mit
  wiederverwendeter `clip_id=1`.
- Nach dem Wechsel: `target_selected=0`; Analyze und Delete beide deaktiviert.
- `destructive_actions_invoked=false`; es wurde keine Löschaktion ausgelöst.
- Der erste Automationsversuch deckte fehlende `CanExecute`-Gates auf. Nach dem
  minimalen Produktfix und der Regression bestand der erneute Live-Smoke.
- App und Backend wurden sauber beendet; `BACKEND_FORCED=0`.

Damit ist T049 vollständig geschlossen.
