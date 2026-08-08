# Inert persisted-timeline path fixture

`crafted-timeline.json` is a data-only fixture for the static source finding.
Its first timeline entry contains this reserved test path:

```text
\\pb-studio-preview.invalid\share\clip.mp4
```

The `.invalid` top-level domain is reserved for testing. The fixture has no
launcher, listener, SMB service, or project-install script.

## Safe inspection

From the report directory:

```powershell
Get-Content -Raw .\poc\crafted-timeline.json
```

Do **not** copy this file into a PB Studio project or open it in the application
on a networked workstation. Even a path-existence check can cause DNS or SMB
traffic and may expose Windows authentication material.

No runtime result is claimed. The fixture was not executed under T329's
static-only constraint. Once T332 permits tests, use mocked filesystem and
media boundaries and assert that the value is rejected before any I/O.
