# T327 – Public Contracts and Visible Status

Status: CONFIRMED

## Root cause and data flow

- Audio analysis persisted partial/stage/chunk/downbeat evidence internally,
  but the response schemas and C# DTOs dropped it. The UI consequently marked
  partial analyses as complete and synthesized every fourth beat as a downbeat.
- Timeline metadata contained semantic, feature, trigger, and Brain-axis
  provenance, but the GET/update DTO cycle discarded it.
- Render jobs produced machine-readable run and validation evidence, but HTTP,
  SSE, and the Production view did not expose the complete terminal contract.
- Brain feedback rejection details returned as HTTP 409 were swallowed by the
  generic client path.
- Verified caller flows:
  `audio analysis/cache -> audio router -> AudioAnalysisResult/AudioClipInfo ->
  ApiClient -> AudioLibrary/beat markers`;
  `pacing metadata -> timeline router -> TimelineEntry -> Timeline view`;
  `RenderService -> render task/SSE -> RenderProgress -> Production view`;
  `brain feedback router -> ApiClient -> Brain view`.

## Contract implemented

- Audio DTOs expose analysis status, stage state/errors, chunk evidence,
  downbeats, and downbeat provenance. Partial results remain visibly partial;
  downbeat badges use only backend provenance.
- Timeline DTOs round-trip full metadata plus typed feature, semantic,
  trigger-provenance, and Brain-axis status fields.
- Render HTTP/SSE contracts expose queue job, run, result evidence, validation
  evidence, terminal progress flag, and validation status; the Production log
  renders those values as copyable text.
- Brain feedback preserves the concrete rejection/failure message and does not
  report rejected feedback as a successful update.
- Status, error, evidence, and path text introduced or affected by this task is
  rendered through read-only copyable WPF text controls.
- `PBStudio.UI/openapi.snapshot.json` and the hand-maintained C# records match
  the backend schemas.

## Side effects and boundaries

- Public DTOs are backward-compatible additions; existing method signatures
  and `IApiClient` operations are unchanged.
- Timeline manual updates preserve unknown metadata keys while canonical fields
  remain authoritative.
- No dependency, lockfile, database schema, or runtime binary changed.
- No functional, regression, hardware, GUI, build, or E2E test ran.

## Static evidence

- Python `py_compile`: PASS for all changed schemas and routers.
- XAML XML parse: PASS for Audio Library, Timeline, Production, and Brain views.
- OpenAPI JSON parse: PASS.
- Selected Pydantic/OpenAPI property parity: PASS for AudioAnalysisResult,
  AudioClipInfo, TimelineEntrySchema, RenderProgress, and
  BrainFeedbackResponse.
- Static caller/reference scan: PASS; every added backend field has a DTO/UI
  consumer, and no every-fourth-beat downbeat synthesis remains.
- `git diff --check`: PASS for the complete T327 file set.
