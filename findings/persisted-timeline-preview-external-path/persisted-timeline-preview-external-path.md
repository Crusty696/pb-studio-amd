# Persisted Timeline Paths Can Trigger External Preview Requests

## Executive Summary

**Severity:** Low
**Confidence:** High
**Classification:** CWE-918 (Server-Side Request Forgery)

PB Studio trusts the `file_path` stored in a project's `timeline.json`. When a
project is opened, the backend copies that value into runtime state and returns
it through `GET /pacing/timeline`. The WPF timeline then selects the first entry,
checks the supplied path with `File.Exists`, and passes it to
`MediaElement.Source` as an absolute URI. A UNC path can therefore make the
victim workstation contact an attacker-selected network host under the
victim's Windows security context.

The practical impact is constrained. An attacker must first place or modify a
project beneath PB Studio's configured project directory and induce the user to
open it. The path must also pass `File.Exists` before the media player loads it.
Even so, that existence check is itself sufficient to initiate UNC name
resolution and SMB access. Depending on Windows policy and network placement,
this can disclose authentication material or provide a network reachability
oracle. I rate the finding Low because project delivery and user interaction
are prerequisites, while the resulting outbound request is real and occurs
without an explicit network-access decision.

I statically reviewed HEAD `b76937ddf341fb395f81e6936612329eca85c601`
and the uncommitted T305-T328 repair diff on 2026-07-29. I did not build PB
Studio, open a project, execute the supplied artifact, or generate network
traffic because functional and security test execution is deferred until T332.
No fixed revision was available during review, and I cannot make a precise
introduction-version claim from the reviewed material.

## Background

PB Studio projects are directories below `config.project_dir`. The open-project
endpoint correctly constrains the selected project directory:

```python
# backend/routers/project_router.py:226-230
project_path = Path(request.path).resolve()
allowed_base = Path(config.project_dir).resolve()
if not project_path.is_relative_to(allowed_base):
    raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
```

That check protects the project-directory boundary, but a project contains
persisted timeline data with nested media paths. Those paths cross a different
boundary: data inside an allowed project can name a resource outside that
project, including a UNC host.

When the timeline view refreshes, the backend response is converted into
`TimelineEntryModel` objects. The first entry is selected automatically:

```csharp
// PBStudio.UI/ViewModels/TimelineViewModel.cs:437-465
TimelineEntries.Clear();
foreach (var entry in timeline.Entries)
{
    TimelineEntries.Add(new TimelineEntryModel
    {
        ClipId = entry.ClipId,
        ClipName = entry.ClipName,
        FilePath = entry.FilePath,
        // ...
    });
}

SelectedEntry = TimelineEntries.FirstOrDefault();
```

The normal invariant should be that a persisted preview path identifies a
locally approved media asset, preferably a canonical file inside the project's
media directory. Opening a project must not silently authorize a new network
destination. The reviewed implementation enforces the first invariant only for
the project directory itself, not for paths embedded in the timeline.

## Vulnerability Details

We first reach the persisted-data boundary in
`_load_timeline_into_state`. The loader parses `timeline.json`, normalizes the
entries, performs temporal timeline validation, and installs the result in
global application state:

```python
# backend/routers/project_router.py:140-155
payload = json.loads(timeline_path.read_text(encoding="utf-8"))
timeline = payload.get("timeline", [])
audio_path = payload.get("audio_path")
if not isinstance(timeline, list):
    raise ValueError("timeline ist keine Liste")

timeline = _normalize_timeline_entries(timeline)
warnings, errors = validate_timeline(timeline)
# ...
state.set_timeline(timeline)
state.current_audio_path = audio_path if isinstance(audio_path, str) and audio_path else None
```

`_normalize_timeline_entries` copies a flat `file_path` into the entry's
metadata when needed. `validate_timeline` checks timeline shape and timing; the
reviewed load path does not require the media path to be local, canonical,
registered, or inside the project directory. From here we can carry a concrete
value such as:

```text
\\pb-studio-preview.invalid\share\clip.mp4
```

The next transition is `GET /pacing/timeline`. It extracts `file_path` from the
stored metadata and serializes it without applying a path policy:

```python
# backend/routers/pacing_router.py:227-256
for cut in state.get_timeline_snapshot():
    meta = cut.get("metadata", {})
    entries.append(TimelineEntrySchema(
        clip_id=cut.get("clip_id", ""),
        clip_name=meta.get("clip_name", "Unknown"),
        file_path=meta.get("file_path", ""),
        # ...
    ))

return TimelineResponse(
    entries=entries,
    total_duration=total,
    audio_path=state.current_audio_path,
)
```

The WPF view model then exposes `File.Exists` as its preview authorization
check:

```csharp
// PBStudio.UI/ViewModels/TimelineViewModel.cs:162-170
public string SelectedFilePath => SelectedEntry?.FilePath ?? "–";
public bool CanPreviewSelectedClip =>
    SelectedEntry != null && File.Exists(SelectedEntry.FilePath);
```

This is the missed invariant. `File.Exists` answers whether a path is
accessible; it does not establish that the path belongs to the current project
or that accessing it is safe. On Windows, checking a UNC path can perform name
resolution and SMB negotiation.

Finally, if the path is accessible, the code-behind constructs an absolute URI
and assigns it to the media element:

```csharp
// PBStudio.UI/Views/TimelineView.xaml.cs:579-608
var entry = _viewModel?.SelectedEntry;
if (entry == null || !_viewModel!.CanPreviewSelectedClip)
{
    ResetPreview("Kein Preview geladen");
    return;
}

var sourcePath = entry.FilePath;
// ...
PreviewPlayer.Source = new Uri(sourcePath, UriKind.Absolute);
```

The complete path is therefore:

```text
crafted project/timeline.json
  -> _load_timeline_into_state
  -> AppState timeline metadata
  -> GET /pacing/timeline
  -> TimelineEntryModel.FilePath
  -> File.Exists(UNC path)
  -> MediaElement.Source
```

The T305-T328 diff expands timeline metadata round-tripping but does not add a
network path or project-root check at either trust transition. I found no
evidence that these repairs introduced the original `file_path` flow; the
security regression is that the repaired contract continues to preserve and
consume an unvalidated persisted path.

## Exploitability Analysis

The strongest realistic route is a project bundle supplied by an attacker. The
attacker places a syntactically valid `timeline.json` in the project and sets
the first entry's `file_path` to an attacker-controlled UNC share. When the
victim opens the project and reaches the Timeline view, PB Studio selects that
entry. We then reach `File.Exists` before any preview button is pressed.

If the host is resolvable and SMB is permitted, the Windows client may attempt
authentication using the victim process's network context. This can expose a
challenge-response exchange to an attacker-operated server. Whether that
exchange is relayable or crackable depends on domain policy, SMB signing,
credential protections, egress filtering, and the victim's account. The
primitive alone does not establish credential compromise.

If the remote path returns a file, `MediaElement.Source` provides a second
request surface and asks the Windows media stack to parse attacker-controlled
content. That is not evidence of code execution, and I did not inspect codecs
for downstream vulnerabilities. It does, however, increase the data handled
after the initial path check.

Meaningful constraints are:

- The project directory itself must pass the existing `project_dir` check.
- A remote attacker needs a delivery mechanism or a local actor capable of
  modifying the project.
- The WPF client, not the FastAPI process, performs the UNC request described
  here; CWE-918 is used because a trusted application is induced to request an
  attacker-selected resource under its own authority.
- Direct `http://` paths appear less promising because `File.Exists` normally
  rejects them before `MediaElement.Source` is assigned.
- Network controls can block UNC resolution or SMB egress.
- The supplied artifact uses the reserved `.invalid` namespace and was not
  executed, so it demonstrates data flow only.

Local absolute paths are another variant. They may disclose file existence
through visible preview state, but the reviewed UI does not return file bytes to
the project author. That route is weaker than UNC authentication and is not the
basis for the severity.

## Proof of Concept

The `poc/` directory contains an inert project timeline fragment:

```text
poc/
  README.md
  crafted-timeline.json
```

The JSON places a reserved `.invalid` UNC hostname in the first timeline
entry's `file_path`. It is deliberately data-only: there is no launcher,
listener, DNS setup, SMB server, or automatic project modification.

Because T329 permits static review only, I did not run the artifact. The safe
inspection command from this report directory is:

```powershell
Get-Content -Raw .\poc\crafted-timeline.json
```

Expected static output includes:

```text
"file_path": "\\\\pb-studio-preview.invalid\\share\\clip.mp4"
```

Do not import or open the fixture in PB Studio on a networked workstation.
Execution could cause DNS and SMB traffic and may expose Windows authentication
material. There is no runtime output to report because no trigger was executed.
After a fix, the later T332 security test should feed the same value through a
mocked path policy and assert rejection before any filesystem or media API is
called. Cleanup consists only of deleting the copied test project; the
distributed fixture itself changes no application state.

## Remediation

Restore this invariant: **a persisted project may reference only an explicitly
approved local media file, and project loading must never cause network access
while deciding whether that reference is valid.**

Enforce the invariant in the backend before installing a timeline in
`AppState`, and apply the same policy to `POST /pacing/timeline`. Reject UNC,
device-namespace, URI-scheme, relative, traversal, and junction/symlink escape
variants before checking existence. A minimal project-contained policy could
take this shape:

```python
from pathlib import Path

def _validated_video_path(raw: object, project_path: Path) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError("missing timeline media path")

    # Reject network and Windows device namespaces before filesystem access.
    if raw.startswith(("\\\\", "//")):
        raise ValueError("network media paths are not allowed")

    candidate = Path(raw)
    if not candidate.is_absolute():
        raise ValueError("timeline media path must be absolute")

    media_root = (project_path / "video").resolve()
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(media_root) or not resolved.is_file():
        raise ValueError("timeline media path is outside project video storage")

    return str(resolved)
```

If external local media is an intentional product feature, replace the strict
project-directory rule with a stored approval record created only by an
interactive import action. Do not infer approval from `File.Exists` or from a
path stored in project-controlled JSON/SQLite.

The WPF layer should also fail closed as defense in depth. It should consume an
already-approved local path or opaque media identifier, reject `Uri.IsUnc`, and
avoid calling `File.Exists` on untrusted text. An opaque clip ID resolved by the
backend is preferable to returning an arbitrary path.

After T332 begins, add regression coverage for:

1. UNC paths, including mixed separators and `\\?\UNC\...`.
2. `file:`, `http:`, and other URI schemes.
3. Relative paths and `..` traversal.
4. symlink or junction escape from the project video directory.
5. a valid local clip inside the approved media root.
6. both project-load and `POST /pacing/timeline` entry points.
7. a UI contract asserting that rejected entries never reach `File.Exists` or
   `MediaElement.Source`.
8. metadata round-tripping that cannot override a validated canonical path.

Tests should mock filesystem/network boundaries so no DNS, SMB, GUI, or media
playback occurs.

## Summary

A project-scoped path check protects where PB Studio opens a project, but not
what resources that project can name. A persisted timeline path flows unchanged
through backend state and the timeline API into WPF, where selecting the first
entry can issue UNC filesystem access and, if accessible, media loading. This
creates a low-severity, high-confidence CWE-918 request-forgery primitive with
possible Windows authentication exposure.

The fix is to treat persisted media paths as untrusted references, validate
them against an approved local-media policy before runtime state is updated,
and keep the UI away from raw path authorization. Future variant analysis
should cover persisted `audio_path`, render inputs, thumbnail/waveform loaders,
and any project metadata that reaches filesystem or URI APIs.
