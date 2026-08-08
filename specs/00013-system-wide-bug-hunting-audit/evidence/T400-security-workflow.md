# T400 Security Workflow

Date: 2026-07-31
Result: PASS

## Change

- Added all-branch/PR secret, Python/NuGet SCA, dependency-review and SBOM jobs.
- Pinned every GitHub Action to an immutable commit SHA.
- Added exact negative fixtures for every secret rule, `urllib3==1.26.5` and `Newtonsoft.Json==12.0.1`.
- Bound every uploaded gate receipt to `${{ github.sha }}`.
- Bound the synthetic secret exception to its exact Git blob and SHA-256.
- Added strict report schemas, expected project paths, package versions and advisory validation.
- Included both UI and native-test NuGet locks in audit and deduplicated SBOM generation.
- Replaced vulnerable transitive `System.Text.Json 8.0.3` with direct `9.0.18` in both locked graphs.
- Dependency review runs both on PRs and on the final `main`/`release/*`
  push, comparing `event.before` to `${{ github.sha }}` and recording both
  SHAs in the receipt.

## Verification

- Current/history scan: 1,297 current text files and 3,753 historical text paths, zero active secret findings.
- Seven-rule secret fixture with no allowlist: 7/7 rules detected, including
  `github_pat_...` and encrypted private-key headers.
- Python and NuGet clean/vulnerable/malformed schema self-checks: PASS.
- Real locked NuGet restore and production audits: zero vulnerabilities in both project graphs.
- Real NuGet negative fixture: exact package/version and GHSA detected.
- Independent reviews: R1 six findings, R2 one finding, R3 final PASS.
- Full hosted Python SCA and remote workflow execution remain deliberately assigned to T413/T415.
