# T355 — SceneInfo nullability and batch truth

Status: CONFIRMED

## Implementation

- Handwritten `PBStudio.UI.Services.SceneInfo.Confidence` changed from
  `double` to `double?`.
- Backend Pydantic contract remains `Optional[float] = None`.
- Generated C# contract remains `double?`.
- No synthetic confidence default was introduced.
- Marked/all video batches increment success only after a non-null analysis
  response is received.
- Null responses and service/deserialization exceptions increment failure,
  remain visible in the final status, and do not mark a clip analyzed.
- Already analyzed clips are reported separately as skipped.
- Per-clip failures no longer abort the remaining batch or produce a false
  all-success message.

## Static verification

- Nullability references align across backend, generated C#, and handwritten C#.
- Modified C# files have balanced braces.
- Runtime deserialization and GUI checks remain deferred until T361/T365.

## Gate

CONFIRMED: `confidence=null` is representable end to end, and batch completion
no longer counts invalid client results as successful.
