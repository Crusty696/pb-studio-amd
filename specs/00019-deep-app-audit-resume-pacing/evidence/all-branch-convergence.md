# All-Branch Convergence — 2026-08-08

## Scope

- Baseline: `origin/main` at `192a103ee1f770342181dbcca59d4464a84eeb40`
- Integration branch: `codex/obj74-branch-convergence`
- Audited refs: 24 local and remote refs excluding `main`, `origin/main` and the integration branch itself
- Method: ancestry, ahead/behind, patch identity, function-level current-tree comparison and merge-tree risk

## Already contained before this convergence

| Ref | Tip | State |
|---|---:|---|
| `00013-system-wide-bug-hunting-audit` | `c6ae67b5c10a` | Exact ancestor |
| `backup/pre-hybrid-alignment-2026-03-09` | `2b0af6e314ec` | Local old tip is an ancestor |
| `claude/competent-shaw` | `843fef6678f5` | Exact ancestor |
| `claude/cranky-hodgkin` | `6791213ea0c2` | Exact ancestor |
| `claude/nifty-sammet` | `cf3b731d02d5` | Exact ancestor |
| `claude/upbeat-liskov` | `fb748f87fe0a` | Exact ancestor |
| `codex/finalize-obj73-release` | `345b89adeb8e` | Exact ancestor |
| `codex/obj74-deep-audit-claude-integration` | `34bfcdc94da9` | Exact ancestor |
| `origin/00013-system-wide-bug-hunting-audit` | `c6ae67b5c10a` | Exact ancestor |
| `origin/claude/cranky-hodgkin` | `07067bc77a34` | Exact ancestor |
| `origin/claude/nifty-sammet` | `79d4580c032a` | Exact ancestor |
| `origin/codex/finalize-obj73-release` | `345b89adeb8e` | Exact ancestor |
| `origin/codex/obj74-deep-audit-claude-integration` | `34bfcdc94da9` | Exact ancestor |
| `origin/feat-preview-renderer-tests-15077044930625159154` | `97861699353f` | Exact ancestor |
| `origin/jules-15487637999750232221-8724e04d` | `4d36225f24df` | Exact ancestor |
| `origin/pacing-service-dead-code-removal-14057687362481284002` | `50598512bb5f` | Exact ancestor |
| `origin/pacing-structure-weighting-4362049196895279299` | `6cd80dc738e6` | Exact ancestor |

## Non-ancestor tips and decisions

| Ref / tip | Functional audit | Decision | History merge |
|---|---|---|---|
| `origin/backup/pre-hybrid-alignment-2026-03-09` / `2057a0c4eda9` | Unique patches remove the current FastAPI video-analysis stack and replace it with a 32-line Flask dummy. Tip comparison would change 1,677 files and delete about 500,000 lines. | Reject tree; preserve no product hunk. | `fa93d06` using `ours` |
| `origin/bolt-optimize-checkerboard-novelty-4639455432380006930` / `20b659aeee43` | Vectorization changes the established odd-kernel result and can materialize a large temporary operand. | Reject as behavior and memory regression. | `5ddce350` using `ours` |
| `origin/bolt-semantic-matcher-cache-10971711345514938352` / `ae58484150d9` | Targets deleted `semantic_matcher.py`; cache can become stale on same-length metadata replacement. Current selection lives in `ClipSelector`. | Reject obsolete implementation. | `93f5ae70` using `ours` |
| `origin/bolt-sqlite-synchronous-optimization-12870257090745113121` / `ed49d12531ca` | `DatabaseCore` lacked the `synchronous=NORMAL` policy already used by `storage/sqlite_init.py` and approved in the data plan. | Port one current-architecture line plus contract test. | `6a41bc47` using `ours` |
| `origin/fix-dummy-embeddings-pacing-5699629546609309049` / `fdf8e3998b33` | Current `ClipSelector` is a tested superset: FAISS preference, real embedding fallback, validation and path normalization. | No port; current implementation wins. | `45e4d090` using `ours` |
| `origin/perf-optimize-media-dedup-audit-query-5659391175589865201` / `fdd4a7764a5e` | Patch identity existed historically, but the current audit script again performed an N+1 foreign-key discovery loop. | Re-port only the correlated pragma query plus end-to-end test; discard temporary symlinks. | `f32e5fb2` using `ours` |
| `origin/security-fix-cors-restriction-18420067296954344044` / `c3f6d6a20983` | Current loopback allowlist and owner capability are stricter and functional. The old empty-origin policy would break legitimate local preflight. | No port; current implementation wins. | `11fdcd32` using `ours` |

Every `ours` merge was guarded by an identical tree hash. Baseline and post-merge tree were both `1b8961798343e2de7ecbcd3811bd8a9438918086`; therefore no rejected branch tree, conflict debris, local settings or temporary symlink entered the integration branch.

## Selective product delta

- `src/pb_studio/data/database_core.py`: enable `PRAGMA synchronous=NORMAL` after WAL.
- `Tests/test_database_core_synchronous.py`: mock-only connection contract; no migration or real database mutation.
- `scripts/media_dedup_audit.py`: discover all references to `media` with one correlated `pragma_foreign_key_list` query.
- `Tests/test_media_dedup_audit.py`: real temporary SQLite schema verifies metadata, filtering and one discovery query.

## Verification

- `py_compile` for the four selectively changed Python files: PASS.
- Combined minimal regression: `2 passed` on Python 3.11.9.
- Full Python compile sweep over `src`, `backend`, `scripts`, `Tests`: PASS.
- SDD open validation: `valid=true`, zero findings.
- `git diff --check origin/main...HEAD`: PASS.
- Conflict-marker scan over every changed file: PASS.
- Ancestry audit: 24 refs checked, 0 non-ancestors of integration `HEAD`.
- Intended tree delta versus `origin/main`: exactly four SDD files, this evidence file, two product files and two focused tests.

## Ref cleanup gate

No branch ref was deleted. Redundant local and remote refs are eligible for cleanup only after this integration reaches protected `main` and the user gives a fresh explicit deletion confirmation.
