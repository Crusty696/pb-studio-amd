# T403 Complete Diff Review

Date: 2026-08-01
Result: PASS

## Independent review

- Three independent zone reviews covered WPF/project lifecycle, backend state
  and persistence, and release/security infrastructure.
- Initial result: FAIL with 19 findings (13 HIGH, 6 MEDIUM); no finding was
  waived or downgraded.
- A bounded Claude final-review attempt was stopped after its 60-second limit
  without output and was not retried (loop/token guard).

## Closed findings

- Project transitions, timeline refreshes, deletes, video analysis, thumbnails
  and Brain endpoints now carry project identity, generation/epoch and
  cancellation through their commit boundary.
- Project open/save compensate durable partial failure; render workers retain
  immutable queue ID/context and drain their physical thread on cancellation.
- SSE filters apply before bounded enqueue; NSwag generates under `obj`.
- PyTorch is exact `2.4.1+cpu`/`0.19.1+cpu`/`2.4.1+cpu`; generator, setup and
  CI reject CUDA/NVIDIA packages and incompatible imports.
- Secret rules cover classic/fine-grained GitHub tokens and encrypted private
  keys with a 7/7 negative fixture. Dependency review is bound to the final
  protected push SHA as well as the PR.
- FFmpeg GPL/static-build truth, Demucs CPU truth, mandatory setup gates and
  T388 hashes were reconciled.

## Static integration gate

- CPython 3.11.9 compile sweep (`backend`, `src`, `scripts`, `Tests`): PASS.
- JSON: 130 UTF-8 and 2 historical UTF-16 files PASS; preserved `.pytest_*`
  fault fixtures were intentionally excluded and not modified.
- YAML 2, XML/XAML/MSBuild 20, PowerShell AST 73: PASS.
- Python lock: 41 direct pins, 124 exact Windows wheel hashes: PASS.
- GitHub Actions: 28/28 immutable SHA pins; IRON addition scan: PASS.
- SDD open-phase validator and `git diff --check`: PASS.

Functional, native, clean-checkout, GUI, hardware and security execution remain
strictly assigned to T404–T413. This receipt proves implementation integrity,
not release readiness.
