# PB Studio Security Threat Model

## Overview

PB Studio is a local Windows WPF desktop application backed by a Python/FastAPI service. It imports and analyzes user-selected audio and video, maintains project/timeline/render state in SQLite and FAISS-backed indexes, invokes local AI providers, and starts FFmpeg, DirectML, and model workloads. The normal deployment binds FastAPI to `127.0.0.1:8765`; this is a same-host boundary, not a public web service. The protected assets are project isolation, imported media and generated outputs, SQLite/FAISS consistency, render identity and queue state, chat prompts/tool arguments, local logs, model and FFmpeg artifacts, and release provenance.

Relevant attackers are: (1) an untrusted media/project/model artifact opened by the user; (2) another process running under the same Windows account or host; (3) a compromised or malicious local LM Studio/Ollama provider; (4) a compromised dependency, model source, CI action, or downloaded runtime; and (5) a remote network client only if the loopback binding or deployment assumptions are changed. Public multi-tenant web, browser, CSRF, and XSS threats are out of scope for the default desktop deployment.

## Threat Model, Trust Boundaries, and Assumptions

### Trust boundaries

1. **WPF client to FastAPI over loopback HTTP/SSE.** Requests, streamed events, project identifiers, paths, and job state cross a process boundary. Another local process can attempt to call loopback endpoints. Destructive owner operations additionally require a random 256-bit capability passed only to the backend child process.
2. **User-controlled project and media inputs to parsers and compute engines.** Project names/paths, audio/video bytes, clip IDs, render destinations, chat prompts, model names, and tool arguments are untrusted. Media reaches Python decoders, FFmpeg, and ML models, increasing parser and resource-exhaustion exposure.
3. **Backend orchestration to project-scoped storage.** Async jobs write SQLite, FAISS, thumbnails, analysis results, timelines, and render outputs. Project switching, cancellation, retries, process restart, and concurrent workers must not redirect writes or corrupt identity/state.
4. **Chat/LLM to tool registry and internal HTTP.** Model-generated tool names and arguments are untrusted. Mutating operations require an explicit visible confirmation and one-time confirmation state.
5. **PB Studio to local AI providers.** LM Studio/Ollama are separate local trust domains. Prompts, chat history, tool arguments, and project metadata supplied to them are not confidential from those providers.
6. **Application to filesystem and subprocesses.** Python, FFmpeg, DirectML, model files, logs, project files, and spawned processes cross OS boundaries. Path canonicalization, reparse/device/network path policy, process ownership, and command construction are security controls.
7. **Build and release supply chain.** GitHub Actions, PyPI, NuGet, Gyan FFmpeg, model sources, installer inputs, and generated provenance are external trust domains. A compromised artifact can execute with the user's privileges.

### Assumptions

- The supported production topology remains a single-user Windows desktop application with FastAPI bound exclusively to loopback.
- The Windows account and OS are not already fully compromised; same-user malicious processes remain relevant because loopback endpoints and local files can still be attacked.
- The owner capability has sufficient entropy, is not logged, and is passed only to the intended child process.
- Project operations preserve an immutable project identity/epoch from request admission through commit.
- DirectML, Python, NumPy, FFmpeg/AMF, and model versions follow the locked release policy; provenance and hashes are verified before promotion.
- Externally managed backends or non-loopback binding expand the threat model and require authentication, authorization, transport protection, and network hardening not assumed here.

### Existing mitigations

- Loopback-only backend startup, child-process ownership, owner capability for destructive lifecycle calls, and kill-on-close handling.
- Canonical path containment and rejection of UNC, network, device, and reparse-point media paths where applicable.
- Project operation context/epoch checks, serialized project switching, transactionally guarded render status transitions, content-derived render identity, SQLite WAL/foreign keys/busy timeout, and outbox-based consistency controls.
- One-time confirmation for mutating chat tools and explicit treatment of model-generated tool calls as untrusted.
- Redaction of terminal/crash output, with local file logs still treated as same-user sensitive data.
- Hash-locked Python dependencies, locked NuGet restore, SHA-pinned CI actions, restricted workflow permissions, approved immutable model revisions, archive/file hashes, ZIP allowlists, symlink rejection, atomic asset promotion, and FFmpeg archive/binary verification.

## Attack Surface, Mitigations, and Attacker Stories

### Loopback API and SSE

- **Surface:** project, media, audio/video analysis, pacing, render, chat, events, model management, and lifecycle endpoints.
- **Attacker story:** a same-host process enumerates or invokes unprotected endpoints to read project status, start expensive jobs, manipulate state, or observe SSE events.
- **Required controls:** loopback binding must remain enforced; destructive endpoints require capability/confirmation; endpoint input schemas, project context, cancellation, and resource bounds must fail closed. If remote binding is introduced, add authenticated principals, authorization, TLS, CSRF-equivalent request-origin controls as applicable, and deployment-specific rate limits.

### Project paths and cross-project isolation

- **Surface:** project creation/opening, media imports, catalog references, output destinations, project switching, queued/running background jobs.
- **Attacker story:** a crafted path escapes the project root, or a job admitted under project A commits after project B becomes current, causing disclosure, overwrite, or database/index divergence.
- **Required controls:** resolved-path containment, rejection of unsafe path types, immutable per-operation project identity/epoch, commit-time revalidation, and atomic storage updates. UI success must only follow durable backend success.

### Media, FFmpeg, and model inputs

- **Surface:** untrusted audio/video/container bytes, thumbnails, model packages, tensors, metadata, and command-line parameters.
- **Attacker story:** malformed media exploits a decoder/FFmpeg vulnerability, crafted dimensions/duration exhaust memory or disk, or a malicious model/archive writes outside its staging root or executes code.
- **Required controls:** verified/pinned runtimes, argument-array subprocess invocation, allowlisted formats and archive entries, symlink/path traversal rejection, bounded work, cancellation/timeouts, staging plus atomic promotion, and no loading of unverified executable/model artifacts.

### Chat tools and local AI providers

- **Surface:** prompts, model responses, tool names/arguments, confirmation IDs, internal HTTP tool calls, provider management.
- **Attacker story:** prompt injection induces a mutating tool call, replays a confirmation, exfiltrates project metadata to a local provider, or causes resource exhaustion.
- **Required controls:** strict tool registry allowlist/schema validation, one-time action-bound confirmation, no trust in model text, project-context enforcement inside the backend, redaction/minimization of provider inputs, and bounded calls/timeouts.

### Persistence, retries, and concurrent jobs

- **Surface:** SQLite/FAISS state, render queue/history, analysis results, restart recovery, deduplication, cancellation, and concurrent workers.
- **Attacker story:** races or crashes create false success, terminal-state mutation, duplicate processing, stale commits, or divergence between database, vector index, and files.
- **Required controls:** explicit state-transition graph, transactional compare-and-set, content-based identity, process-safe deduplication, idempotent resume, durable error reporting, and recovery tests across real process boundaries.

### Logs and local confidentiality

- **Surface:** terminal events, crash messages, app logs, file paths, prompts, model responses, and diagnostic evidence.
- **Attacker story:** secrets, capabilities, personal paths, prompts, or project metadata are disclosed via logs/SSE or retained too broadly.
- **Required controls:** structured redaction at every sink, never log owner capabilities or tokens, least-retention file logging, restrictive file permissions, and tests for redaction bypasses.

### Supply chain and release artifacts

- **Surface:** package indexes, NuGet, CI actions, FFmpeg, Python runtime, DirectML/model assets, installer/bundle assembly, SBOM, signatures/hashes, and provenance.
- **Attacker story:** a dependency or downloaded archive is replaced, an unpinned CI action changes, installer assembly includes an unverified executable, or provenance references a different commit/artifact.
- **Required controls:** immutable versions/revisions, cryptographic hashes, locked restores, least-privilege CI, secret and dependency scanning, SBOM generation, exact commit/artifact binding, deterministic allowlists, and verification on a clean checkout.

## Severity Calibration

- **Critical:** reliable arbitrary code execution or release-chain compromise through a shipped dependency, installer, FFmpeg/model/runtime artifact; or complete project takeover/destructive filesystem escape with little or no user interaction.
- **High:** reachable owner-capability/confirmation bypass; cross-project destructive write or path escape; RCE requiring a crafted media/model opened through the supported workflow; persistent corruption of project state that defeats recovery or provenance controls.
- **Medium:** same-host disclosure of project, prompt, event, or log data; durable state divergence or false success without broad filesystem compromise; reliable resource exhaustion that materially blocks normal use; exploitable weakness requiring a malicious local provider.
- **Low:** limited disclosure or denial of service that already requires access as the same Windows user, manual inspection of local files, or a deliberately compromised local AI provider, with no privilege or project-boundary crossing.

Repository: target_sha256_21bf4f38604eb29128f49276d0ea477afdd635521584ed6cb42004c177a2b5bf
Version: 814d2389e3ab687253328ab844ff3498a787621f