# T307 Decision, Architecture, and Security Review — 2026-07-29

- Result: CONFIRMED
- Decision register: `decision-register-2026-07-29.md`
- Approved decisions recorded: D01–D08
- One-way data gate: D04 after live mutation
- Remote-history gate: D07
- Brain path-scope gate: D08
- Sequential boundaries: production data, shared files/public contracts, Model Registry, output publication, repository push
- Open causes: EOF stage, FFmpeg version, Brain migration applicability
- Blockers: none
- Tests executed: none

Repository threat-model cache is generated separately under the Codex Security scan-artifact path and versioned to the T307 worktree snapshot.

- Threat model: `C:\Users\david\AppData\Local\Temp\codex-security-scans\Pb_studio_AMD_version\threat_model.md`
- Repository target: `sha256:91a75bdf4f79f00c09bbbaeaa67e5bcb9854fb80365ce4b12d5ef1f3c1b82fda`
