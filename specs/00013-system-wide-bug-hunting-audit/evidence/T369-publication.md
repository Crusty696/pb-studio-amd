# T369 — Zoned Publication and Remote Verification

Status: CONFIRMED publication / RELEASE-READY
Executed: 2026-07-30T09:14+02:00–2026-07-30T12:18+02:00

## Scope and D07

- Baseline: `81dc9fcbb9b72124dc600ca8f2ba398297b3b3d9`
- PB branch: `00013-system-wide-bug-hunting-audit`
- Brain branch: `master`
- PB pre-push divergence after fetch: 0 remote-only, 7 local-only
- Brain pre-push divergence after fetch: 0 remote-only, 1 local-only
- Force-push: not used
- Rebase: not used
- Full PB range `git diff --check`: PASS
- Range size: 164 files, 15,366 insertions, 1,624 deletions

## Secret and scope scan

The exact PB publication range contained 163 present files:

- text scanned: 140
- binary artifacts classified: 23
- credential/private-key/token content matches: 0
- suspicious credential filenames: 0
- package or lockfile changes: 0
- path-list SHA-256:
  `D589FBEF9821609E5E84F865D75AFA26A4C863A11D5278B461A30C720BE1A346`

`gitleaks`, `trufflehog` and `detect-secrets` were unavailable. The bounded
repository-native scan covered PEM headers, GitHub/AWS/OpenAI/Slack token
forms, JWTs, credential URLs, assigned secret values and suspicious filenames.
The earlier T358 security review independently closed all reportable findings.

The four Brain publication files were scanned with the same credential classes
and produced 0 matches. Staging outside `10_Projects/PB_studio/**` was 0.

## PB Studio zoned commits

| Zone | Commit | Subject |
|---|---|---|
| Runtime/Core | `b6cb6b3dda6a65aaa065cb96fa28bc9fa9489f06` | `fix(runtime): unify DirectML hardware identity` |
| Provider/Models | `3ea63428cbe98f1593234ac80a3aeb7d75de440a` | `fix(models): bind live inventory and selection receipts` |
| DirectML consumers | `d0c626d5fb381c2b6b4aac35f01ba70413bc67b6` | `fix(directml): bind inference consumers to adapter contract` |
| UI/contracts | `c86384c8aae787a829e8deab835cc12625e337c4` | `fix(ui): show truthful GPU and model state` |
| Tests | `01e85dc65bff35a72d74621783406c85af609a22` | `test: cover runtime hardware and provider truth` |
| Docs/evidence | `ddf718124eb2fd6706445b0ada11e293420e5629` | `docs(qc): record blocked OBJ-71 truth gate` |
| Repository evidence | `b04ca4f9479021c932c53b1fb14df50600781821` | `chore(repo): preserve immutable runtime evidence` |

PB payload push:

- local SHA: `b04ca4f9479021c932c53b1fb14df50600781821`
- `ls-remote` SHA: `b04ca4f9479021c932c53b1fb14df50600781821`
- result: byte-identical

PB completion ledger:

- local SHA: `78d0c3f9009a382ecb6eacf6ab97da240688c77f`
- `ls-remote` SHA: `78d0c3f9009a382ecb6eacf6ab97da240688c77f`
- result: byte-identical before this receipt-only follow-up

Post-audit marker truth:

- local SHA: `241f112317eea382a06e7ff56cf9c9e7040d1957`
- `ls-remote` SHA: `241f112317eea382a06e7ff56cf9c9e7040d1957`
- result: byte-identical before the final receipt-only follow-up

Brain final publication:

- local SHA: `82b570df2524f2eb10e37baed34b8d165330b6aa`
- `ls-remote` SHA: `82b570df2524f2eb10e37baed34b8d165330b6aa`
- result: byte-identical

## Preserved exclusions

PB Studio left eight `.pytest_t362_*` temporary cache directories untracked.
They are test-run scratch state, not plan deliverables.

Brain left all unrelated state unstaged and unchanged:

- `Unbenannt 1.base`
- deleted `Unbenannt 1.canvas` and `Unbenannt.canvas`
- `.obsidian/backlink.json`
- `.obsidian/page-preview.json`
- `_wiki/learnings/2026-07-30-onnx-runtime-implicit-cpu-provider.md`

## Verdict

OR-334 and T369 are PASS / CONFIRMED. The original blocked-state publication
was followed by the authorized T363 model-asset remediation and final T368
truth gate.

## T363/T368 closing publication

- PB pre-push divergence: 0 remote-only, 2 local-only
- exact 31-file publication Secret-Scan: 0 credential/private-key matches
- DirectML/model commit:
  `c2e3e8440547c0d9d3f081e531657a37a0299e8a`
- QC/evidence commit:
  `669d9d320774261d6881437760431f7d86ab2b85`
- PB payload local/remote SHA:
  `669d9d320774261d6881437760431f7d86ab2b85`
- Brain pre-push divergence: 0 remote-only, 1 local-only
- Brain PB-Studio-only payload local/remote SHA:
  `aa2585979ed625f1ae51decff08b20c40155ff11`
- force-push/rebase: not used

T363 / TR-344 and T368 are PASS. `.completed` and `.qc-passed` are valid;
PB Studio is release-ready. This document update is the receipt-only follow-up
to the byte-identical payload SHAs above.
