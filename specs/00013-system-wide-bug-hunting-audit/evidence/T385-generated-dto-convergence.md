# T385 Generated DTO Convergence

Date: 2026-07-31
Result: PASS

## Change

- Audio analysis and spectral transport deserialize through NSwag-generated
  types and explicit UI adapters.
- Single-model and multi-model VRAM responses use separate generated shapes;
  the compatibility method performs an explicit single-to-multi UI mapping.
- Spectral adapter preserves bands, centroids, frequency ranges, means,
  variances and events.

## Verification

- Drift searches for direct manual spectral/audio transport use: PASS.
- `git diff --check`: PASS.
- WPF Release build: PASS, 0 warnings, 0 errors.
- `ApiClient.cs`: `a8108869190a7ac341895821f129041f6482ba550b1eae183c70d1a37c51a177`.
- `SpectralDataModel.cs`: `6f6b22c7e241e19a37a26efa035acb1ff18101a0afd68fd74ffee8a544299078`.
- `VramTelemetry.cs`: `43c5ffe1a629cdbe11138bdf41e3397a9cd3763cd60434256250440a7acebf37`.
