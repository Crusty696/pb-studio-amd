# T356 — Configuration, OpenAPI, client, and nullability sync

Status: CONFIRMED

## Synchronized artifacts

- `config.json` and ConfigManager defaults include additive
  `ai.task_provider_overrides`.
- Backend models API schemas include provider inventory, model truth,
  discovery, activation provider/task, test provider, and receipt metadata.
- `PBStudio.UI/openapi.snapshot.json` was regenerated from `app.openapi()`.
- `PBStudio.UI/Generated/ApiTypes.g.cs` was regenerated directly with the
  pinned NSwag 14.2.0 tool; no WPF build was run.
- Handwritten C# DTOs and API methods mirror the additive fields.
- `SceneInfo.confidence` is nullable in Pydantic, OpenAPI, generated C#, and
  handwritten C#.

## Artifact hashes

- OpenAPI SHA-256:
  `CCC7CBD1055A11FF609354624037A8B535CE31B978C3A818E28BAFA71CB3845D`
- Generated C# SHA-256:
  `2F10529309DCDBD551EDEFD3596AA6ECFB78C889C1D48A6FE1F70E63BC0CB155`
- Generated client timestamp is not older than the snapshot.

## Static verification

- OpenAPI JSON parsed successfully.
- ModelListEntry exposes all central inventory fields.
- SceneInfo OpenAPI property is `type=number`, `nullable=true`, and is not
  required.
- Python 3.11 compile sweep for affected modules passed.
- Model Manager XAML parsed as XML.
- `git diff --check` passed.

## Gate

CONFIRMED: active configuration, Python DTOs, OpenAPI, generated client,
handwritten DTOs, and nullability contracts are synchronized.
