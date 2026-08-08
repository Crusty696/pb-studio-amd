# T394 Fatal Exception Policy

Date: 2026-07-31
Result: PASS

## Change

- An unknown dispatcher exception is redacted, logged critically and triggers
  exactly one fatal dialog followed by controlled shutdown.
- Failure inside the fatal handler returns control to WPF with
  `Handled=false`.
- Fatal shutdown skips automatic project save because the in-memory state may
  be inconsistent; normal shutdown keeps the existing bounded save path.
- Unobserved task and AppDomain exceptions use redacted logging.

## Verification

- Static policy scan and `git diff --check`: PASS.
- WPF Release build: PASS, 0 warnings, 0 errors.
- `PBStudio.UI/App.xaml.cs` SHA-256:
  `46ef92605ab6f4b6a6c3af1e931b73fdfbd5ab7c02279d6efd43e78436b52e14`.

Injected runtime validation remains T404/T408.
