# PB Studio – PyQt Removal Classification

_Last updated: 2026-03-11_

## Summary
The removed `src/pb_studio/ui/...` area should **not** be treated as a blind parity loss.
A meaningful part has already been **replaced** by the WPF hybrid UI, but several higher-value interactive pieces are **not actually present yet** and should be treated as deliberate **rebuild** items rather than silently assumed done.

## Classification legend
- **Replace** = current WPF flow already covers the job well enough
- **Rebuild** = capability is still product-relevant, but current WPF only has partial/basic/no equivalent
- **Restore** = legacy implementation should come back substantially as-is
- **Keep** = concept remains valid without needing the old concrete widget

## Area decisions

| Legacy PyQt area | Decision | Why | Current replacement / gap |
|---|---|---|---|
| `src/pb_studio/ui/styles.qss` | Replace | PyQt-specific styling shell is obsolete after WPF migration | WPF theme/resources now own presentation |
| `src/pb_studio/ui/widgets/common/progress_card.py` | Replace | Generic progress-card concept exists in WPF via native progress/status surfaces | Audio/Video/Timeline/Production status bars |
| `src/pb_studio/ui/widgets/common/result_card.py` | Replace | Metric-card semantics already reappear in WPF layouts | Audio/Video/Settings metric sections |
| `src/pb_studio/ui/widgets/analysis/audio_analysis_step.py` | Replace | Audio analysis action/result flow exists in WPF audio library | `AudioLibraryView` + `AudioLibraryViewModel` |
| `src/pb_studio/ui/widgets/analysis/video_analysis_step.py` | Replace | Video analysis trigger exists in WPF video library | `VideoLibraryView` + `VideoLibraryViewModel` |
| `src/pb_studio/ui/widgets/generation/pacing_config_widget.py` | Replace | Pacing controls migrated into WPF Director settings | `DirectorView` |
| `src/pb_studio/ui/widgets/generation/generation_container.py` | Replace | Generation responsibilities split across Director + Timeline + Production, which is the right target architecture | `DirectorView`, `TimelineView`, `ProductionView` |
| `src/pb_studio/ui/widgets/generation_widget.py` | Replace | Old monolithic generation screen is superseded by the split WPF workflow | Director/Timeline/Production triad |
| `src/pb_studio/ui/widgets/common/file_drop_mixin.py` | Rebuild | Drag-drop ingest UX is still useful, but current WPF ingest is button-only | `MediaIngestView` lacks drag-drop path |
| `src/pb_studio/ui/widgets/analysis/analysis_queue_widget.py` | Rebuild | Mixed queued background analysis is a real workflow accelerator and not present in WPF | No queue-oriented WPF analysis surface yet |
| `src/pb_studio/ui/widgets/analysis/ai_analysis_step.py` | Rebuild | AI/semantic analysis is product-relevant, but WPF has no dedicated review surface for it | Backend capability partial, UI absent |
| `src/pb_studio/ui/widgets/audio/audio_info_panel.py` | Rebuild | WPF shows headline metrics, but not a richer compact metadata/details panel | Audio library has BPM/key/beat count only |
| `src/pb_studio/ui/widgets/audio/beat_marker_widget.py` | Rebuild | Beat overlay remains valuable for sync inspection and manual QA | No interactive beat overlay in WPF |
| `src/pb_studio/ui/widgets/waveform_widget.py` | Rebuild | Current Anchor view still uses a waveform placeholder, not a real waveform | `AnchorView` placeholder only |
| `src/pb_studio/ui/widgets/common/timeline_widget.py` | Rebuild | Current WPF timeline is a table/list, not a true editable/seekable timeline component | `TimelineView` is informational, not interactive timeline UX |
| `src/pb_studio/ui/widgets/generation/render_progress_widget.py` | Rebuild | Current render progress is basic and the render log is still placeholder-level | `ProductionView` has progress bar + placeholder log only |
| `src/pb_studio/ui/widgets/player_widget.py` | Rebuild | Media preview/playback remains important for validation and editing confidence | No native playback widget in current WPF views |
| `src/pb_studio/ui/widgets/video/motion_visualization_widget.py` | Rebuild | Motion analysis exists backend-side, but there is no visual motion graph in WPF | Analysis data available, UI absent |
| `src/pb_studio/ui/widgets/video/scene_list_widget.py` | Rebuild | Scene detection is live-tested, but users cannot inspect scenes in a dedicated WPF surface | Scene UI absent |
| `src/pb_studio/ui/widgets/video/video_info_panel.py` | Rebuild | Video grid shows only summary metadata; a richer details panel is still missing | Duration/resolution summary only |
| `src/pb_studio/ui/__init__.py` and `widgets/**/__init__.py` | Replace | Package shell files are implementation scaffolding, not product features | No direct WPF equivalent needed |

## Net judgment

### Already safely replaced
- Theme shell / generic cards / basic analysis triggers / pacing configuration / monolithic generation shell

### Still missing in a product-meaningful way
- Real waveform + beat overlay
- Real interactive timeline control
- Media preview/player
- Scene inspection UI
- Motion visualization UI
- Richer audio/video metadata panels
- Queued/batch analysis UX
- Drag-drop ingest UX
- Richer render progress/log UI

## What should NOT be restored as PyQt
- The old PyQt styling system
- The old monolithic generation shell
- The old standalone audio/video analysis step widgets as architecture anchors

Those should remain replaced by WPF-native flow rather than resurrected.

## Recommended next build order
1. Real waveform + beat overlay in WPF (`AnchorView` / shared control)
2. Scene + motion inspection surfaces for video analysis
3. Real render progress/log surface (and cancel-path verification)
4. Drag-drop ingest + optional queued analysis workflow
5. Native preview/player if required for parity and review speed

## Conclusion
The current migration is directionally correct.
The main risk is **false confidence** from assuming table/list-based WPF placeholders equal full parity.
They do not. The missing pieces are now explicit rebuild targets rather than invisible debt.
