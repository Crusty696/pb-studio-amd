# PB Studio Function Catalog

## Test Data

| Type | Approved input |
|---|---|
| Audio | `C:\Users\david\Videos\test_data\audio\test_30s.wav`, `test_60s.wav` |
| Video | `C:\Users\david\Videos\test_data\video\test_5s.mp4`, `test_8s.mp4`, `test_10s.mp4`, `test_12s.mp4`, `test_20s.mp4` |

## Area: Pacing / KI-Regie

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> absichtlich `⬜`, bis der Nutzer die automatisierte und Live-Verifikation
> ausdrücklich freigibt; kein Eintrag wird ohne Testbeleg als PASS markiert.

| ID | Function | UI entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-6.1 | Sources load/reload | Open KI-Regie / project-library refresh | `DirectorViewModel.LoadClipsAsync` → audio/video state services | Current-project audio/video lists load; user video selection survives refresh | ⬜ |
| F-6.2 | Audio source selection | Audio-Quelle combo box | `SelectedAudioClip` → `AudioClipId`; analyzed BPM → `ExpectedBpm` | Selected audio and tempo become request inputs | ⬜ |
| F-6.3 | Individual video selection | Video list checkbox | `SelectableVideoClip.IsSelected` → `VideoClipIds` | Only selected registered videos enter generation | ⬜ |
| F-6.4 | Select all videos | ALLE / Alt+A | `SelectAllVideoClipsCommand` | Every listed video becomes selected and count updates | ⬜ |
| F-6.5 | Deselect all videos | KEINE / Alt+N | `DeselectAllVideoClipsCommand` | Selection clears and Generate becomes unavailable | ⬜ |
| F-6.6 | Expected BPM override | Erwartete BPM | `expected_bpm` → active corrected beat grid | Material override changes rhythmic grid; near-detected value preserves measured beats | ⬜ |
| F-6.7 | Beat weight | Beat-Gewichtung | `trigger_settings.beat_weight` → beat-trigger strength/gating | Value changes beat-trigger contribution; zero disables it | ⬜ |
| F-6.8 | Onset weight | Onset-Gewichtung | `trigger_settings.onset_weight` → onset-trigger strength/gating | Value changes onset-trigger contribution; zero disables it | ⬜ |
| F-6.9 | Kick weight | Kick-Gewichtung | `trigger_settings.kick_weight` → drum/stem weighting | Value changes kick contribution when data exists | ⬜ |
| F-6.10 | Snare weight | Snare-Gewichtung | `trigger_settings.snare_weight` → drum/stem weighting | Value changes snare contribution when data exists | ⬜ |
| F-6.11 | Hi-hat weight | HiHat-Gewichtung | `trigger_settings.hihat_weight` → drum/stem weighting | Value changes hi-hat contribution when data exists | ⬜ |
| F-6.12 | Energy weight | Energie-Gewichtung | `trigger_settings.energy_weight` → cached-energy triggers | Value changes energy-trigger contribution; zero disables it | ⬜ |
| F-6.13 | Energy threshold | Energie-Schwelle | `trigger_settings.energy_threshold` → energy peak filter | Higher threshold admits fewer/weaker energy events | ⬜ |
| F-6.14 | Onset sensitivity | Onset-Empfindlichkeit | `trigger_settings.onset_sensitivity` → onset delta | Value changes onset trigger sensitivity monotonically | ⬜ |
| F-6.15 | Minimum clip length | Min. Clip-Länge | `trigger_settings.min_clip_length` → effective interval enforcement | No generated cut violates effective minimum except valid terminal handling | ⬜ |
| F-6.16 | Maximum clip length | Max. Clip-Länge | `trigger_settings.max_clip_length` → automatic split enforcement | Long intervals split without source overflow or sub-minimum fragments | ⬜ |
| F-6.17 | Clip-length variation | Clip-Längen-Variation | `trigger_settings.clip_length_variation` → seeded split jitter | Zero is uniform; non-zero varies lengths within safety bounds | ⬜ |
| F-6.18 | Maximum cut interval | Max. Schnittabstand | `trigger_settings.max_cut_interval` → effective maximum | No generated gap/cut duration exceeds effective maximum | ⬜ |
| F-6.19 | Minimum cut interval | Min. Schnittabstand | top-level `min_cut_interval` → effective minimum | Contradictory settings reject cleanly; generated spacing respects minimum | ⬜ |
| F-6.20 | Beat trigger mode: all | Beat-Trigger-Modus | `beat_trigger_mode=all` → `_build_beat_triggers` | All eligible measured beats may trigger | ⬜ |
| F-6.21 | Beat trigger mode: downbeat | Beat-Trigger-Modus | `downbeat_only` → derived/measured downbeats, safe all-beat fallback when absent | Uses labelled downbeats and never returns an accidental empty grid | ⬜ |
| F-6.22 | Beat trigger mode: strong | Beat-Trigger-Modus | `strong_only` → onset-strength filter | Only strong eligible beats trigger; safe behavior when strengths absent | ⬜ |
| F-6.23 | Duration limit | Dauer-Limit | `duration_limit` → service target duration/finalizer | Positive limit caps exact timeline duration; invalid values reject | ⬜ |
| F-6.24 | Storyboard canvas anchors | Storyboard Canvas path | `canvas_path` + UI anchors → `load_canvas_manual_anchors` / merge | Valid owned canvas assignments/anchors affect output; invalid input fails safely | ⬜ |
| F-6.25 | Motion matching | Motion Matching | `use_motion_matching` → video preflight/cache → selector motion score | Motion data changes ranking; missing data is rejected or shown truthfully | ⬜ |
| F-6.26 | Semantic matching | Semantisches Matching | `use_semantic_matching` → local ONNX/VectorStore selector | Semantic data changes ranking; unavailable capability returns structured degradation | ⬜ |
| F-6.27 | Structure awareness | Struktur-Erkennung | `use_structure_awareness` → cached sections/subtracks → engine weights/snapping | Valid structure data changes section-aware pacing | ⬜ |
| F-6.28 | Key matching | Tonart-Matching | `use_key_matching` → Camelot compatibility score | Scorable keys affect ranking; zero scorable clips disable mode visibly | ⬜ |
| F-6.29 | Stem pacing | Stem-basiertes Pacing | `use_stem_pacing` + validated `stems_paths` → stem generation branch | Approved stems drive triggers; missing/unsafe stems degrade safely without crash | ⬜ |
| F-6.30 | Brain reranking/confidence | Brain + Min-Confidence | `use_brain`, `brain_min_confidence` → reranker + post-processor | Brain affects eligible selection/persistence; failures are visible and base timeline survives | ⬜ |
| F-6.31 | Generate cut list | Button / Ctrl+G | `POST /pacing/generate` → service → active engine → state timeline | Returns non-empty finite ordered contiguous source-safe cuts for valid analyzed inputs | ⬜ |
| F-6.32 | Progress and correlation | Generation progress UI | `pacing_progress` SSE keyed by audio/task | Progress updates only active request and reaches completion without stale cross-project updates | ⬜ |
| F-6.33 | Generate error/retry lifecycle | Generate after validation/runtime failure | ViewModel status/finally + project operation | User sees compact cause; controls recover; retry can succeed; stale result is rejected | ⬜ |
| F-6.34 | Generated cut-list display | CUT-LISTE grid | response metadata → `TimelineEntryModel` | Count, duration, clip, time, duration, trigger match response | ⬜ |
| F-6.35 | Brain top-N suggestions | Vorschläge laden / F5 | `BrainSuggestAsync` → suggestion grid | Top-N current-timeline suggestions load in score order or explain absence | ⬜ |
| F-6.36 | Runtime degradation display | Status line | response `degradations` → `FormatDegradations` | Each affected mode and its own scored/total counts are visible | ⬜ |

## Area: Pacing Timeline Boundary

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-7.1 | Timeline reload | Timeline tab / `GET /pacing/timeline` | state snapshot → `TimelineResponse` | Latest current-project timeline and complete metadata reload | ⬜ |
| F-7.2 | Manual timeline update | Timeline edit sync / `POST /pacing/timeline` | path/source cap + timeline validation + project commit | Valid edits persist; gaps, overlaps, foreign media, and source overflow reject safely | ⬜ |
| F-7.3 | Preview generation | Timeline preview / `POST /pacing/preview` | validated timeline paths → preview renderer under GPU lock | Playable 640×360 preview for requested valid interval | ⬜ |
| F-7.4 | Timeline/render handoff | Timeline refresh + render consumer | canonical cuts/metadata/source bounds | Render boundary receives same contiguous source-safe segments | ⬜ |
| F-7.5 | Project isolation | Project switch/close during or after Pacing | project epoch/context + UI reset | No timeline, progress, or result leaks across projects | ⬜ |

## Explicit Legacy Exclusion

`advanced_pacing_engine.SyncMode`, `PacingConfig`, `plan_cuts`, and related historical planners have no productive `/pacing/generate` caller. They remain documented legacy per ADR and are not counted as current user functions.

## Area: KI / MODELLE

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> `⬜`, bis der Nutzer Tests, Provider-Probes und GUI-Verifikation freigibt.

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-8.1 | Initial inventory | MODELLE tab open | `IsActive` → `LoadAsync` → `GET /models/list?refresh=true` → `ModelInventoryService` | One fresh provider-separated snapshot; installed/loaded/usable remain distinct | ⬜ |
| F-8.2 | Manual refresh | Refresh / F5 | `RefreshCommand` → list then available from same generation | Cards and provider state refresh without stale request publication | ⬜ |
| F-8.3 | Provider status | Header badges/status | native LM Studio/Ollama probes → `ProviderStatusEntry` | Offline/degraded/ready/empty states and reason are truthful | ⬜ |
| F-8.4 | Installed cards | Installed list | inventory entry → `InstalledModelCardViewModel` | Provider, capabilities, loaded/on-demand state, size, context and active tasks match snapshot | ⬜ |
| F-8.5 | Available/discovery | Available list | verified Ollama manifest candidates + provider discovery links | Only live-verifiable downloads get a download action; discovery is labelled separately | ⬜ |
| F-8.6 | Activate model | Activate | owner-authorized `POST /models/activate` → capability/task overrides → durable config check | Exact provider/model activates only compatible tasks; stale/ambiguous identity rejects visibly | ⬜ |
| F-8.7 | Provider inference test | Inferenz-Test | owner-authorized `POST /models/test` → exact receipt → chat or image inference | Chat models receive text; vision models receive an image; receipt/error remains visible | ⬜ |
| F-8.8 | Ollama download | Download | owner-authorized `POST /models/pull` SSE → native `/api/pull` | Progress/error is visible; cancel stops consumption; success invalidates inventory | ⬜ |
| F-8.9 | Ollama delete | Delete + confirmation | owner-authorized `DELETE /models/{id}` → exact live identity → native `/api/delete` | Only confirmed exact Ollama model is deleted; provider failure is not reported as not-found | ⬜ |
| F-8.10 | LM Studio management handoff | Download/Delete on LM Studio card | UI handoff message → LM Studio Discover/My Models | Unsupported mutation is explained; PB Studio does not invent success | ⬜ |
| F-8.11 | Task recommendation | `GET /models/recommendations` | live snapshot → capability gate → `ModelSelectionReceipt` | One compatible provider/model or one truthful no-model reason | ⬜ |
| F-8.12 | Selection hierarchy | runtime task selection | hard task override → task preference → recommendation → bounded live fallback | Provider/model identity is exact; failed identities are excluded; max three candidates | ⬜ |
| F-8.13 | Vision model pin | Video captioning | process pin → exact receipt reused for every frame/clip | One successful VLM remains loaded; content-empty frame does not churn models | ⬜ |
| F-8.14 | Model-centric video batch | Analyze marked/all | WPF pass loop: scenes → all clips, RAFT → all, SigLIP → all, VLM → all | Specialized model changes occur between passes, not between every clip | ⬜ |
| F-8.15 | KI mode | global mode control / `POST /models/mode` | owner-authorized config persistence → mode-changed refresh | speed/balance/quality persists and affects subsequent unoverridden selection | ⬜ |

## Area: KI / CHAT

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> `⬜`, bis der Nutzer Tests, Live-Tool-Aufrufe und GUI-Verifikation freigibt.

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-9.1 | Project history load | CHAT tab/project open | `LoadHistoryAsync` → `GET /chat/history` → project-bound JSON store | Persisted current-project turns appear before send; stale project load is discarded | ⬜ |
| F-9.2 | Send | Send / Enter / Ctrl+Enter | `SendAsync` → `POST /chat/message` SSE → per-request `ChatAgent` | One user turn and one streaming assistant turn are created | ⬜ |
| F-9.3 | Multiline input | Shift+Enter | `InputBox_KeyDown` | Shift+Enter inserts newline; Enter sends only when command can execute | ⬜ |
| F-9.4 | Mode selection | speed/balance/quality combo | request mode → receipt selection | Mode affects compatible selection; successful model remains pinned across turns | ⬜ |
| F-9.5 | Model event/status | `model` + `llm_status` | receipt payload → message model/status text | Exact provider/model and selection reason are visible | ⬜ |
| F-9.6 | Text streaming | `text_delta` / `text` | SSE parser → ordered builder → assistant message | Deltas remain ordered; final text replaces cumulative copy without duplication | ⬜ |
| F-9.7 | Tool call correlation | `tool_call` / `tool_result` | stable tool-call ID through agent/router/client/UI | Repeated same-name calls receive their own result | ⬜ |
| F-9.8 | Destructive confirmation | confirmation event/dialog | one-time broker ID → approve/reject endpoint → consume | Exact server-stored tool/args execute once only after approval | ⬜ |
| F-9.9 | Tool errors | tool dispatch error/result | registry/handler → visible error event and result payload | Unknown, invalid, timeout and backend failures never masquerade as success | ⬜ |
| F-9.10 | Tool compatibility degradation | provider rejects tools | retry same model without tools + visible nonterminal notice | Chat may continue, but missing tool support is never silent | ⬜ |
| F-9.11 | Model/provider fallback | connection/provider failure | exclude failed identity → one refresh → bounded next receipt | Successful recovery is a notice, not a permanent red terminal error | ⬜ |
| F-9.12 | Stop | Stop / Escape | cancellation token → HTTP stream close → agent/resource cleanup | Active response stops; UI exits busy state and marks partial turn aborted | ⬜ |
| F-9.13 | Clear history | Clear / Ctrl+L | disabled during stream/load → `DELETE /chat/history` → UI clear after confirmation | No append-after-clear race; failure leaves visible history intact | ⬜ |
| F-9.14 | Project isolation | project transition | generation token + stream/history cancellation + backend project capability | No text, tool result or history crosses project boundary | ⬜ |
| F-9.15 | Stream termination | error/done/EOF | router terminal frames + UI terminal check/finally | Error/cancel/success always releases busy/status state; EOF without done is visible | ⬜ |
| F-9.16 | History bounds | send/persist | UI last 40 + server max 200 + token-aware trim | Context remains bounded while durable project history remains intact | ⬜ |
| F-9.17 | Tool inventory | `GET /chat/tools` | `build_default_registry` → schemas/category/destructive flags | Every registered productive tool exposes matching name, schema and safety class | ⬜ |

## Explicit KI Legacy Exclusion

`ModelManagerViewModel.StreamPullAsync` and `DownloadProgressViewModel` currently have no productive view/dialog caller; the active download path streams directly into the model-card status. They remain excluded until a real progress dialog is wired.

## Area: Brain / HIRN

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> `⬜`, bis der Nutzer Tests, Live-API-Aufrufe und GUI-Verifikation freigibt.

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-10.1 | Brain scoring | Pacing with Brain | canonical features → available bridge axes → posterior weights → finite mean | Only explicitly available axes enter score and denominator | ⬜ |
| F-10.2 | Trigger-axis evidence | generated cut trigger | trigger type → matching trigger axis status | Exactly the matching beat/onset/kick/snare/hihat/energy axis contributes | ⬜ |
| F-10.3 | Brain confidence threshold | Brain Min-Confidence | reranker final score → threshold/fallback | Threshold applies to Brain score; finished timeline intervals are never deleted | ⬜ |
| F-10.4 | Hierarchical posterior | axis/context lookup | Level 5→0 confident bucket → Laplace posterior or cold default | Exact selected bucket and cold-start state remain explainable | ⬜ |
| F-10.5 | Bayesian variance | learning-session sampler | Laplace Beta posterior → evidence-aware variance | One-sided early feedback does not produce false zero uncertainty | ⬜ |
| F-10.6 | Sparse credit | feedback click | persisted bridge/status → relevant axis/context assignments | Only available contributing evidence receives weighted credit | ⬜ |
| F-10.7 | Feedback idempotency | four rating buttons | stable operation ID → outbox/receipt → project event + global weights | Retry applies one logical click at most once | ⬜ |
| F-10.8 | Feedback project guard | rate during project transition | client project identity + server operation context/lease | Old-project rating cannot mutate same-numbered cut in new project | ⬜ |
| F-10.9 | Brain persistence | Pacing post-processor | atomic timeline/cut transaction → state DB | Transient unpersisted scores are rejected; base timeline survives with degradation | ⬜ |
| F-10.10 | Semantic input availability | Brain semantic axis | exact CLAP/SigLIP cache identities → dimension/norm/finite validation | Missing/partial inputs stay explicit and leave score denominator | ⬜ |
| F-10.11 | Projector readiness | semantic projection | learned artifact/event ledger → trained gate | Random fresh projection matrices never masquerade as semantic evidence | ⬜ |
| F-10.12 | Projector training | accepted feedback | unseen UUID inventory → copy-on-write fit → atomic V2 publish | No artifact generation is published when zero trainable pairs exist | ⬜ |
| F-10.13 | Brain suggestions | `POST /brain/suggest` / Director suggestions | current audio timeline → clip filter → stored scores → top-N | Current-project suggestions are score ordered and bounded | ⬜ |
| F-10.14 | Learning-session list | List / `POST /brain/learning_session` | current cuts → available-axis variance → stratified sampler | Up to 15 diverse uncertain cuts use only evidence they actually contain | ⬜ |
| F-10.15 | Learning walkthrough | Walkthrough dialog | project timeline paths + learning list → preview/navigation/rating | Project transition closes the session and suppresses stale results | ⬜ |
| F-10.16 | Brain statistics | Refresh / `GET /brain/stats` | global weight store → learned/cold/top buckets + migration metadata | Counts, variance, semantics version and archived history are visible | ⬜ |
| F-10.17 | Structured explanation | timeline confidence tooltip / explain API | stored bridges + current exact posterior diagnostics | Contributions, cold state and final score describe the same current calculation | ⬜ |
| F-10.18 | Narrative explanation | explain with narrative | pinned Brain model → provider call → structured offline fallback | Model remains stable; empty content does not churn models | ⬜ |
| F-10.19 | Global Beta reset request | reset request | owner capability → expiring owner-bound token | Request is non-destructive and clearly states global scope | ⬜ |
| F-10.20 | Global Beta reset confirm | reset confirm | single-use token → serialized global weight reset | Only Beta weights reset; projector/history retention is disclosed | ⬜ |
| F-10.21 | HIRN project lifecycle | project open/close/switch | generation invalidation → list/selection/reset-state clear → reload | No stale learning cut, feedback status or reset token crosses projects | ⬜ |
| F-10.22 | Error/retry lifecycle | any HIRN request failure | backend detail/null result → visible status → controls recover | Failure is visible and no busy/rating/reset gate remains stuck | ⬜ |

## Area: VIDEO / VISION

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> `⬜`, bis der Nutzer Tests, Live-Provider-Läufe und GUI-Verifikation freigibt.

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-11.1 | File import | Add videos / path import | canonical path → ffprobe → streaming hash → project media registration | Supported readable files register once; input duplicates are skipped visibly | ⬜ |
| F-11.2 | Folder import | Import folder | recursive extension filter → guarded project import | All supported files enter the initiating project; stale results are suppressed | ⬜ |
| F-11.3 | Clip list | Video Library load/refresh | paged `/video/clips` → persisted/cache analysis merge → WPF models | Current-project metadata and exact stage status are visible | ⬜ |
| F-11.4 | Thumbnail | clip card | project lease → FFmpeg frame → JPEG → guarded availability flag | Thumbnail belongs to the same clip/project and failure remains local | ⬜ |
| F-11.5 | Thumbstrip | timeline clip | project lease → duration-bounded frame sampling → JPEG data URLs | Frames cannot publish after project switch or beyond visible duration | ⬜ |
| F-11.6 | Clip waveform | timeline clip | project lease → audio peak extraction | Peaks belong to the requested current-project clip | ⬜ |
| F-11.7 | Single delete | Delete selected | confirmation → project-guarded DB/outbox/runtime delete | Exact current-project clip is removed or reported not found | ⬜ |
| F-11.8 | Batch delete | Delete marked/all | one project commit boundary → idempotent outbox deletion | No partial cross-project delete after a switch | ⬜ |
| F-11.9 | Scene detection | Scenes pass | PySceneDetect → duration clamp → persisted scene stage | At least one valid bounded scene or explicit failed state | ⬜ |
| F-11.10 | Scene retrieval | selected clip detail | completed-stage gate → `/video/scenes/{id}` | Missing/unrun scene analysis is not returned as successful empty data | ⬜ |
| F-11.11 | RAFT motion | Motion pass | bounded samples → cached DirectML RAFT → finite curve/peaks/category | One RAFT session serves the clip pass; unavailable and failed remain distinct | ⬜ |
| F-11.12 | Motion retrieval | detail/pacing preflight | completed-stage gate → `/video/motion/{id}` | Never fabricates static zero motion for an unrun/failed stage | ⬜ |
| F-11.13 | SigLIP embedding | Embedding pass | hash reuse or cached DirectML SigLIP → finite 1152-D normalized vector | One SigLIP session serves the clip pass; invalid vectors never persist | ⬜ |
| F-11.14 | Embedding persistence | analysis commit | pending vector → FAISS/media link + Brain cache → DB truth → old-vector dedupe | Canonical DB/cache/vector state commits or compensates coherently | ⬜ |
| F-11.15 | Color analysis | analysis stage | representative RGB frames → weighted dominant colors/features | Finite color/mood features persist without requiring caption success | ⬜ |
| F-11.16 | Vision tags | Vision-Tags pass | pinned local VLM → bounded failover → optional ONNX Moondream | Successful provider/model stays pinned; missing fallback is explicit | ⬜ |
| F-11.17 | Stage resume | repeated analysis | persisted stage validity → skip/retry/force decision → merge | Valid completed stages survive optional-stage failures and resume | ⬜ |
| F-11.18 | Analysis progress | progress panel/SSE | clip-scoped init/stage/frame/final terminal events | Only active clip/project updates progress; every exit is terminal | ⬜ |
| F-11.19 | Model-centric batch | Analyze marked/all | scenes all → RAFT all → SigLIP all → VLM all | Models stay resident across their pass and change only between stages/errors | ⬜ |
| F-11.20 | Cancel/project switch | active import/analysis/load | sequence + project context + linked cancellation → stale suppression | Old work cannot publish or mutate the new project UI/state | ⬜ |
| F-11.21 | Selection/state restore | refresh/sort/mark | stable clip IDs → selection/mark/thumbnail cache restore | User selection survives same-project refresh and clears on project close | ⬜ |
| F-11.22 | Explicit capability degradation | missing DirectML/provider asset | stage `unavailable` + reason, no CPU neural fallback | Other completed stages remain usable; no fabricated completion data | ⬜ |

## Area: AUDIO

> Stand 2026-09-19: Quellpfad-Audit und Fixphase abgeschlossen. Status bleibt
> `⬜`, bis der Nutzer Audio-Proben, Tests, Builds und GUI-Verifikation freigibt.

| ID | Function | UI/API entry | Runtime path | Expected result | Status |
|---|---|---|---|---|---|
| F-12.1 | File import | Dateien / Ctrl+I / Media Import | canonical path → ffprobe → streaming hash → project registration | Supported readable audio registers once with finite metadata in the initiating project | ⬜ |
| F-12.2 | Folder import | Ordner / Ctrl+Shift+I | recursive extension scan → normalized distinct paths → sequential guarded import | One bad file does not abort the batch; duplicates and stale project results do not duplicate UI rows | ⬜ |
| F-12.3 | Clip list | Audio Library open/refresh | paged `/audio/clips` under project lease → cache/DB status merge | Current-project metadata, stem paths and exact analysis state load without cross-project publication | ⬜ |
| F-12.4 | Selection lifecycle | clip list / all / none | stable clip ID → metrics/command state/selected collection | Metrics and command availability follow selection; transition clears every selected item | ⬜ |
| F-12.5 | Single delete | Delete selected | confirmation → project operation/commit → DB/runtime delete | Exact current-project clip is removed or reported not found | ⬜ |
| F-12.6 | Batch/delete all | marked/all delete | one guarded project boundary → per-ID persistent/runtime delete | No delete continues into a different project | ⬜ |
| F-12.7 | Waveform | `/audio/waveform/{id}` | project lease → validated file → cached three-band extraction | Real clip sample rate and non-empty bands return; missing/extraction failure is explicit | ⬜ |
| F-12.8 | Short-file beat/BPM | Analyze | BeatNet when available, documented librosa fallback → interval-median BPM | Positive finite beat grid/BPM or failed stage; bounded duration survives fallback | ⬜ |
| F-12.9 | Downbeats/provenance | Analyze | native BeatNet or aligned Beat This evidence → labelled beat subset | Measured/derived/unavailable provenance is explicit; no invented every-fourth claim | ⬜ |
| F-12.10 | Beat-grid estimate | analysis result/UI metric | onset-envelope grid + kick observation → provenance and secondary display | Independent grid remains labelled, finite and subordinate to production BPM | ⬜ |
| F-12.11 | Onset/drum triggers | analysis + `/audio/onsets/{id}` | onset/kick/snare/hi-hat extraction → beat-stage cache | Completed beat stage exposes bounded triggers; unrun/partial stage returns conflict | ⬜ |
| F-12.12 | Structure | analysis + `/audio/structure/{id}` | novelty/stream energy → labelled segments → completed-stage gate | Non-empty valid segments return only from a completed structure stage | ⬜ |
| F-12.13 | Spectral analysis | analysis + `/audio/spectral/{id}` | 44.1-kHz eight bands + low/mid/high aggregates/events → stage gate | Full-band data returns only when completed; missing data is not fabricated | ⬜ |
| F-12.14 | Key detection | Analyze | instrumental stem when valid, otherwise original mix → Krumhansl-Kessler | Valid named key persists or key stage fails explicitly | ⬜ |
| F-12.15 | Partial-stage truth | analyze/list/detail endpoints | per-stage status/error → merge/persist/API | Optional failures preserve completed stages without declaring full completion | ⬜ |
| F-12.16 | Long-file routing | files >600 s | duration probe → 30-s streaming windows / 5-s overlap | Full-load is blocked; bounded streaming covers the complete duration | ⬜ |
| F-12.17 | Long-file evidence/resume | streaming analysis retry | source/config identity → per-chunk checkpoint → durable merge | Compatible completed chunks resume; incompatible/stale checkpoints are rejected | ⬜ |
| F-12.18 | Long-file overlap | streaming accumulators | window floor + bounded seam dedup → beats/triggers/energy/features | Overlap is not double-counted and dense 16th-note triggers are not collapsed | ⬜ |
| F-12.19 | Stem separation | Stems trennen | project lease → GPU task → locked separator caller → validated marker | Exact model output is validated/persisted; partial outputs resume; no silent success | ⬜ |
| F-12.20 | Stem cache/folder | STEMS badge / folder | validated paths → persisted `stems_paths` → Explorer handoff | Badge/folder appear only for existing validated output paths | ⬜ |
| F-12.21 | Progress correlation | import/analyze/stem progress | active project + clip/task ID → WPF progress fields | Only the initiating current operation updates visible progress | ⬜ |
| F-12.22 | Project transition | open/close/switch during Audio work | backend context + WPF context/generation reset | Old list, selection, status and results cannot leak into the new project | ⬜ |
| F-12.23 | Error/retry lifecycle | import/analyze/stem failure | per-file continuation / stage errors / finally state | Failure is visible, controls recover and valid earlier work remains reusable | ⬜ |
| F-12.24 | Mutable response isolation | all Audio schemas | Pydantic `default_factory` collections | One response instance cannot share mutable lists/dicts with another | ⬜ |
