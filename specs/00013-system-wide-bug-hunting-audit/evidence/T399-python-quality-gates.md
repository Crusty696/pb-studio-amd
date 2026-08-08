# T399 Python Quality Gates

Date: 2026-07-31
Result: PASS

## Change

- Added a branch-coverage configuration with a 53.0 percent non-regression floor.
- Added an owned skip allowlist with mandatory owner, reason and expiry.
- Added a pytest plugin that rejects unapproved or expired skips and writes a machine-readable receipt.
- Added a quality runner that uses a unique system-temp directory and removes only that owned directory.
- Added before/after directory and tree-digest checks protecting all eight historical `.pytest_t362_*` evidence directories.
- Added `.pytest_t362_*/` to `.gitignore`; no historical directory was deleted or modified.

## Fail-closed contracts

- Missing/invalid schema, coverage below 53, nonzero unapproved-skip limit, invalid temp root or empty/unsafe globs stop before the suite.
- Skip patterns must be exact or use only a final `::*`; duplicate, empty, overbroad and expired entries fail.
- New repository `.pytest_*` directories fail the run.
- Deleted, renamed or content-mutated T362 evidence fails even when pytest or coverage already failed.
- Primary and hygiene failures are preserved in the same error.

## Verification

- Independent review round 1 found missing historical-digest and weak skip-schema checks.
- Independent review round 2 found error-path hygiene, threshold-schema and wildcard gaps.
- Both rounds were corrected; independent round 3: PASS.
- Python compile, JSON parse, PowerShell AST and `git diff --check`: PASS.
- Functional coverage/test execution remains intentionally assigned to T405.
