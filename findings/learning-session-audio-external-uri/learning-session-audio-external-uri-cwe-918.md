# Learning-session audio preview accepts an external URI

## Executive Summary

**Severity: Low. Confidence: High. CWE-918.**

PB Studio trusts the `audio_path` string stored in a project's `timeline.json`,
returns it through the local pacing API, converts it to an unrestricted absolute
URI, and binds that URI to a WPF `MediaElement`. A person who can supply or alter
a project under the configured project directory can therefore cause the desktop
application to hand an attacker-selected URI to the Windows media stack when a
user opens that project's Brain learning-session dialog and interacts with its
audio preview. For supported remote-media protocols, this creates a blind,
user-assisted external request from the user's machine.

The practical impact is constrained. The attacker needs a project-import or
project-file modification path plus a user who opens the learning session.
PB Studio does not return the fetched response body to the attacker, and the
actual protocols, redirects, authentication behavior, and request timing depend
on the Windows media components installed on the target. The clearest impact is
an outbound request that reveals network reachability and source-address
information. Requests to loopback or intranet media endpoints may also be
possible, but response exfiltration is not established.

I reviewed the current T305-T328 repair working tree on branch
`00013-system-wide-bug-hunting-audit`, based on revision `b76937ddf341`, by
static source inspection only. I did not build PB Studio, open the GUI, load
media, execute the supplied artifact, or make any local or remote network
request. No fixed revision is known. Git history shows that the unrestricted
learning-session URI sink was present by `4e88bfc9` on 2026-05-06 and the
timeline-to-dialog path was complete by `29af6aa7` on 2026-05-08; exact affected
release numbers were not established.

## Background

PB Studio is a local WPF desktop application backed by a FastAPI process bound
to loopback. A project directory contains `timeline.json`, including timeline
entries and the audio source used for the current edit. Normal operation expects
`audio_path` to name a local audio file imported into the current project.

Opening a project is deliberately limited to the configured project directory:

```python
# backend/routers/project_router.py, open_project
project_path = Path(request.path).resolve()
allowed_base = Path(config.project_dir).resolve()
if not project_path.is_relative_to(allowed_base):
    raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
```

That check protects the location of the project directory. It does not validate
paths or URIs embedded inside `timeline.json`. This distinction matters: an
attacker does not need to escape the project root if an allowed project contains
a hostile `audio_path`.

The UI obtains timeline state through `GET /pacing/timeline` on the loopback API.
`BrainViewModel` then passes the returned audio string into the transient
`LearningSessionViewModel`. The dialog binds that view model's `Uri` directly to
`MediaElement.Source`. The backend and the UI therefore cross two trust
boundaries:

```text
project file
  -> backend process state
  -> loopback JSON response
  -> WPF string
  -> absolute URI
  -> Windows media subsystem
```

The expected invariant is stronger than "absolute URI": learning-session audio
must be a canonical local file already registered as audio media for the active
project. Remote schemes and UNC paths are not required for this feature.

## Vulnerability Details

We first reach the vulnerable state while opening a project. The loader parses
`timeline.json`, validates only the timeline entry list, and stores any non-empty
string from `audio_path`:

```python
# backend/routers/project_router.py, _load_timeline_into_state
payload = json.loads(timeline_path.read_text(encoding="utf-8"))
timeline = payload.get("timeline", [])
audio_path = payload.get("audio_path")

timeline = _normalize_timeline_entries(timeline)
warnings, errors = validate_timeline(timeline)

state.set_timeline(timeline)
state.current_audio_path = audio_path if isinstance(audio_path, str) and audio_path else None
```

No scheme check, local-file check, canonicalization, existence check, or
comparison with the current project's audio catalog occurs. A value such as
`https://example.invalid/pb-learning-session-probe.wav` therefore survives
unchanged.

The local API then serializes the value into `TimelineResponse.audio_path`:

```python
# backend/routers/pacing_router.py, get_timeline
return TimelineResponse(
    entries=entries,
    total_duration=total,
    audio_path=state.current_audio_path,
)
```

This endpoint is locally bound in the normal desktop configuration, so it is not
itself the remote attacker entry point. Its security significance is that it
preserves the untrusted project-file value across the Python-to-C# protocol with
no type stronger than nullable string.

When the user opens the Brain learning-session dialog, `BrainViewModel` obtains
that same field from cached timeline state or refreshes it from the API:

```csharp
// PBStudio.UI/ViewModels/BrainViewModel.cs, ResolveSessionPathsAsync
string? audioPath = _timelineState?.CurrentTimeline?.AudioPath;
if (string.IsNullOrEmpty(audioPath))
{
    var refreshed = _timelineState != null
        ? await _timelineState.RefreshAsync()
        : await _api.GetTimelineAsync();
    audioPath = refreshed?.AudioPath;
}
```

We can now carry the attacker string into `LearningSessionViewModel`. The code
requires it to be absolute but does not require it to be a local filesystem URI:

```csharp
// PBStudio.UI/ViewModels/LearningSessionViewModel.cs, ApplyCurrent
CurrentAudioUri = !string.IsNullOrEmpty(_projectAudioPath)
    ? new Uri(_projectAudioPath, UriKind.Absolute)
    : null;
```

Finally, XAML gives that URI to the media subsystem:

```xml
<!-- PBStudio.UI/Views/LearningSessionDialog.xaml -->
<MediaElement x:Name="AudioPlayer"
              Source="{Binding CurrentAudioUri, Mode=OneWay}"
              LoadedBehavior="Manual"
              UnloadedBehavior="Stop"
              Volume="0.7"
              Visibility="Collapsed"/>
```

`LoadedBehavior="Manual"` is an important interaction constraint. The dialog's
code-behind invokes `AudioPlayer.Play()` only after the user chooses Play, and
invokes it again on Restart. I did not dynamically establish whether a given
Windows media stack performs URI resolution or an initial connection as soon as
`Source` is assigned, so the report does not claim a request at dialog-open
time. The reliable security boundary is that Play or Restart directs the media
element to consume the attacker-controlled URI.

Malformed absolute URI strings can also make `new Uri(...)` throw during
`LoadAsync`, which is a separate availability issue. The CWE-918 finding concerns
well-formed remote absolute URIs that reach the media sink.

## Exploitability Analysis

The strongest realistic route is a shared or otherwise attacker-modifiable PB
Studio project:

1. The attacker places a syntactically valid `timeline.json` in a project beneath
   the victim's configured project directory, or modifies an existing shared
   project's file.
2. `audio_path` contains a well-formed remote media URI.
3. The victim opens that project, navigates to Brain, opens the learning session,
   and selects Play or Restart.
4. If the scheme and media format are supported by the target Windows media
   stack, the UI process initiates a request from the victim's network context.

For an Internet URI controlled by the attacker, we would expect the request
metadata visible at that endpoint to provide a low-grade callback primitive:
source IP, time, and whatever headers the media subsystem supplies. A long-lived
or redirecting media response could add nuisance behavior, but this review did
not establish a stable denial of service.

A loopback or intranet URI is the more interesting variant. The victim machine
may reach services unavailable to the attacker. However, `MediaElement` is a
media consumer, not a general response oracle: there is no source-backed path
that returns arbitrary response bytes, status codes, or parsed secrets to the
project author. This makes the primitive blind. A service whose state changes on
an unauthenticated GET may still be affected, while APIs requiring custom
headers, non-GET methods, or readable response data are poor targets.

Protocol handling is delegated to WPF and the installed Windows media
infrastructure. `http` and `https` are the principal remote cases to validate
later. Redirect following, proxy use, credential forwarding, MIME sniffing, and
supported media containers may vary by operating-system configuration. Although
an absolute `file:` URI is accepted by the current conversion, a local drive
path is the intended feature. UNC paths and remote file shares should be rejected
as well; I did not test whether the target stack attempts authentication to such
shares, so this report makes no credential-leak claim.

Severity remains Low because exploitation is user-assisted, the backend API is
normally loopback-only, the response is not exposed, and media protocol support
limits targets. Confidence is High for the missing invariant and source-level
flow: every transformation from project JSON to `MediaElement.Source` is
explicit in the reviewed code.

## Proof of Concept

The accompanying `poc/crafted-timeline-fragment.json` is intentionally inert. It
contains a reserved `.invalid` host and demonstrates the exact field shape
accepted by the loader without identifying a live service. It is supplied for
review and for conversion into an authorized, isolated regression fixture after
T332 begins.

The safe-first review procedure is:

```text
1. Inspect poc/crafted-timeline-fragment.json as text.
2. Confirm that audio_path is a remote absolute URI.
3. Compare the field with the source chain documented above.
4. Do not open it in PB Studio or replace the reserved host outside an approved lab.
```

No representative network output is included because I did not execute the
artifact. A later controlled validation should use a disposable project and a
loopback-only HTTP listener, then record separately whether assigning `Source`,
pressing Play, or pressing Restart produces the first request. Expected behavior
before a fix is a listener hit on at least the explicit playback action when the
media stack accepts the fixture. Expected behavior after a fix is rejection or
normalization before the URI reaches `MediaElement`, with zero listener hits.

There is no cleanup step for the distributed artifact because it creates no
files, processes, or requests by itself. Delete the copied disposable project
after an authorized future validation.

## Remediation

Restore one invariant at the earliest trust boundary: `audio_path` loaded from a
project file must resolve to a canonical local, non-UNC file that is already
registered in the active project's audio catalog. Invalid values should clear
the preview path and produce a warning; they should never remain in
`state.current_audio_path`.

A backend helper can enforce catalog membership while preserving projects that
legitimately reference local imported media outside the project directory:

```python
from pathlib import Path

def _validated_project_audio_path(value: object, state: AppState) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    candidate = Path(value)
    if not candidate.is_absolute() or str(candidate).startswith(("\\\\", "//")):
        return None

    try:
        resolved = candidate.resolve(strict=True)
        allowed = {
            Path(clip["path"]).resolve(strict=True)
            for clip in state.get_audio_clips_snapshot().values()
            if isinstance(clip.get("path"), str)
        }
    except (OSError, RuntimeError):
        return None

    return str(resolved) if resolved in allowed else None
```

`_load_timeline_into_state` should assign only the helper's result. The UI should
also fail closed as defense in depth, because protocol responses may originate
from older or independently corrupted state:

```csharp
private static Uri? ToLocalMediaUri(string? value)
{
    if (string.IsNullOrWhiteSpace(value) ||
        !Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
        !uri.IsFile ||
        uri.IsUnc ||
        !Path.IsPathFullyQualified(uri.LocalPath))
        return null;

    var fullPath = Path.GetFullPath(uri.LocalPath);
    return File.Exists(fullPath) ? new Uri(fullPath, UriKind.Absolute) : null;
}
```

The backend check is authoritative because it binds the path to project state;
the UI check prevents remote schemes from reaching the sink even if another
producer violates that contract. Do not merely allowlist `file:`: a `file:` URI
can still designate a UNC resource.

Tests belong in the deferred T332+ phase and were not run during this review.
Add regression cases for `http`, `https`, `file://server/share`, raw UNC,
relative paths, nonexistent local files, a local file absent from the current
audio catalog, a cataloged local file, percent-encoded forms, mixed-case
schemes, and project switching. A WPF integration test should verify that no
remote URI is ever assigned to `AudioPlayer.Source`; a controlled loopback
listener test can separately verify zero requests on dialog-open, Play, and
Restart.

## Summary

An untrusted `timeline.json` audio string crosses the local API unchanged,
becomes an unrestricted absolute URI, and reaches the WPF media subsystem during
the Brain learning-session workflow. This yields a blind, user-assisted external
request primitive with limited but concrete network-observation impact.

The defect exists because project-directory containment was treated as if it
also validated embedded media references. It does not. Enforcing canonical
local-file and project-catalog membership in the backend, plus rejecting remote
and UNC URIs in the UI, closes the path without changing normal local preview
behavior. Future variant review should inspect every other consumer of
`TimelineResponse.AudioPath` and every WPF media/image source created from
project-controlled strings.
