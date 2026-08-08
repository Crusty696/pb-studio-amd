# Security Review: Pb_studio_AMD_version

## Scope

Whole-repository standard security scan of the immutable release-candidate commit, augmented with Secret, Python and NuGet dependency gates.

- Scan mode: repository
- Target kind: git_revision
- Target ID: target_sha256_21bf4f38604eb29128f49276d0ea477afdd635521584ed6cb42004c177a2b5bf
- Revision: 814d2389e3ab687253328ab844ff3498a787621f
- Inventory strategy: repository
- Included paths: .
- Excluded paths: none
- Runtime or test status: Static source/control/sink validation was used for the full ledger; focused gate commands ran for secrets and dependency reports. No exploit payload was executed against user data.
- Artifacts reviewed: 1,683-file deterministic repository inventory, Threat model generated for this scan, 26-candidate validation and attack-path ledger, Git-history secret scan, Python OSV and NuGet vulnerability reports
- Scan context: The default product is a single-user Windows WPF application with a loopback FastAPI child process. Other same-host processes remain relevant attackers.

Limitations and exclusions:
- Legacy pickle exploitability remains deferred because no supported attacker-controlled placement path was proven.
- Python package reachability was statically assessed; release remains blocked until lock upgrades, residual-exception policy and a rerun close the gate.

### Scan Summary

| Field | Value |
| --- | --- |
| Reportable findings | 17 |
| Severity mix | medium: 1, low: 16 |
| Confidence mix | high: 15, medium: 2 |
| Coverage | partial |
| Validation mode | Compact standard-scan validation plus compact attack-path analysis for every candidate. |

Canonical artifacts: `scan-manifest.json`, `findings.json`, and `coverage.json`. This report is a deterministic projection of those files.

## Threat Model

Protect project isolation, media/timeline/render state, prompts, local logs and release artifacts across WPF-to-loopback, user-input-to-parser, storage, local-model and build-supply-chain boundaries.

### Assets

- Project and timeline state
- Imported media and render output
- SQLite and FAISS consistency
- Chat prompts and tool confirmations
- Runtime/model/release provenance

### Trust Boundaries

- WPF to FastAPI loopback HTTP/SSE
- User media/project data to parsers and ML runtimes
- Background jobs to project-scoped storage
- Chat model to tool registry
- Repository to external dependency and runtime sources

### Attacker Capabilities

- Same-host process can bind or call loopback ports
- User can open crafted media or project content
- Local AI provider can return adversarial tool requests
- Supply-chain source can serve modified dependencies or artifacts

### Security Objectives

- Authenticate the intended child backend
- Prevent cross-project or unauthorized state access
- Bound parser and job resources
- Keep secrets and prompts out of logs
- Bind release artifacts to reviewed immutable inputs

### Assumptions

- Supported topology remains loopback-only single-user Windows
- The Windows account and OS are not already fully compromised
- Remote backend deployment requires additional authentication and transport controls

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [The desktop trusts any loopback process returning HTTP success from /health as the PB Studio backend and can then send its owner capability to that process](#finding-1) | medium | high | inline below |
| [Loopback client can replace the active project timeline without an owner capability](#finding-2) | low | high | inline below |
| [Current project metadata is disclosed without the launcher owner capability](#finding-3) | low | high | inline below |
| [Loopback client can delete a video clip and its persisted vector state without an owner capability](#finding-4) | low | high | inline below |
| [Loopback client can batch-delete audio clips without an owner capability](#finding-5) | low | high | inline below |
| [The complete process-global chat history is returned by a loopback endpoint without owner authorization](#finding-6) | low | high | inline below |
| [Unauthenticated timeline endpoint exposes project media paths and editing metadata](#finding-7) | low | high | inline below |
| [Project close and job cancellation are reachable without the launcher owner capability](#finding-8) | low | high | inline below |
| [Project activation is reachable without the launcher owner capability](#finding-9) | low | high | inline below |
| [Project creation is reachable without the launcher owner capability](#finding-10) | low | high | inline below |
| [Brain feedback allows unauthenticated learning-state mutation](#finding-11) | low | high | inline below |
| [Project MCP configuration executes an unpinned latest npm package](#finding-12) | low | medium | inline below |
| [Timeline replacement accepts an unbounded entry collection](#finding-13) | low | medium | inline below |
| [VRAM resource limits can be changed without the launcher owner capability](#finding-14) | low | high | inline below |
| [Loopback client can delete an audio clip without an owner capability](#finding-15) | low | high | inline below |
| [Loopback client can batch-delete video and vector state without an owner capability](#finding-16) | low | high | inline below |
| [Full user chat prompts and assistant responses are copied verbatim into the live backend log channel](#finding-17) | low | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] The desktop trusts any loopback process returning HTTP success from /health as the PB Studio backend and can then send its owner capability to that process

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Backend identity spoofing |
| CWE | CWE-290, CWE-346 |
| Affected lines | PBStudio.UI/Services/PythonBridgeService.cs:114-117, PBStudio.UI/Services/PythonBridgeService.cs:343-348, PBStudio.UI/Services/ApiClient.cs:1056-1061 |

#### Summary

The desktop trusts any loopback process returning HTTP success from /health as the PB Studio backend and can then send its owner capability to that process.

#### Root Cause

A same-user process can pre-bind 127.0.0.1:8765. StartAsync calls IsBackendAlreadyHealthyAsync, which checks only response.IsSuccessStatusCode, then AttachToExistingBackend marks the service ready without a challenge or process identity check. Later owner-authorized ApiClient calls attach BackendOwnerCapability to the same BaseAddress, allowing the spoof service to capture it and return attacker-controlled application state. Closest-control assessment: The capability is random, but the pre-bound spoof service receives it on a later owner-authorized request because /health is the only attachment check.

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:114-117`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
            {
                AttachToExistingBackend("Python Backend läuft bereits auf Port {Port} - kein neuer Start nötig");
                return;
```

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:343-348`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
private async Task<bool> IsBackendAlreadyHealthyAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/health").ConfigureAwait(false);
            return response.IsSuccessStatusCode;
```

**Sink evidence** — `PBStudio.UI/Services/ApiClient.cs:1056-1061`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
};
            request.Headers.TryAddWithoutValidation(
                BackendOwnerCapability.HeaderName,
                capability);
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:114-117`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
            {
                AttachToExistingBackend("Python Backend läuft bereits auf Port {Port} - kein neuer Start nötig");
                return;
```

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:343-348`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
private async Task<bool> IsBackendAlreadyHealthyAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/health").ConfigureAwait(false);
            return response.IsSuccessStatusCode;
```

**Sink evidence** — `PBStudio.UI/Services/ApiClient.cs:1056-1061`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
};
            request.Headers.TryAddWithoutValidation(
                BackendOwnerCapability.HeaderName,
                capability);
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);
```

Evidence:
- Independent static trace confirmed in the immutable target: A same-user process can pre-bind 127.0.0.1:8765. StartAsync calls IsBackendAlreadyHealthyAsync, which checks only response.IsSuccessStatusCode, then AttachToExistingBackend marks the service ready without a challenge or process identity check. Later owner-authorized ApiClient calls attach BackendOwnerCapability to the same BaseAddress, allowing the spoof service to capture it and return attacker-controlled application state.
- Cited target-commit ranges re-read: PBStudio.UI/Services/PythonBridgeService.cs:114-117 \[root_control\]; PBStudio.UI/Services/PythonBridgeService.cs:343-348 \[root_control\]; PBStudio.UI/Services/ApiClient.cs:1056-1061 \[sink\]

Counterevidence and remaining uncertainty:
- The capability is random, but the pre-bound spoof service receives it on a later owner-authorized request because /health is the only attachment check.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A same-host process binds 127.0.0.1:8765 before desktop startup and returns success from /health. Flow: root_control PBStudio.UI/Services/PythonBridgeService.cs:114-117 -\> root_control PBStudio.UI/Services/PythonBridgeService.cs:343-348 -\> sink PBStudio.UI/Services/ApiClient.cs:1056-1061. Effect: A same-user process can pre-bind 127.0.0.1:8765. StartAsync calls IsBackendAlreadyHealthyAsync, which checks only response.IsSuccessStatusCode, then AttachToExistingBackend marks the service ready without a challenge or process identity check. Later owner-authorized ApiClient calls attach BackendOwnerCapability to the same BaseAddress, allowing the spoof service to capture it and return attacker-controlled application state.

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:114-117`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
            {
                AttachToExistingBackend("Python Backend läuft bereits auf Port {Port} - kein neuer Start nötig");
                return;
```

**Root Control evidence** — `PBStudio.UI/Services/PythonBridgeService.cs:343-348`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
private async Task<bool> IsBackendAlreadyHealthyAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/health").ConfigureAwait(false);
            return response.IsSuccessStatusCode;
```

**Sink evidence** — `PBStudio.UI/Services/ApiClient.cs:1056-1061`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```csharp
};
            request.Headers.TryAddWithoutValidation(
                BackendOwnerCapability.HeaderName,
                capability);
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);
```

#### Reachability

A process pre-binds 127.0.0.1:8765, answers /health successfully, the desktop attaches without backend identity proof, and later sends the random owner capability and application requests to the spoof service.

#### Severity

**Medium** — Severity matrix: impact=high and likelihood=medium yields severity=medium; loopback/same-user constraints are included rather than treated as blanket suppression.

Severity drops if attachment cryptographically challenges the child capability/process identity before any trusted request, or if a verified child PID/handle exclusively owns the port.

#### Remediation

Require a nonce-based HMAC challenge response from the child backend before attaching or sending the owner capability; reject a health-only pre-bound process and test port-prebinding attacks.

Tests:
- A fake loopback /health responder cannot become the trusted backend.
- The owner capability is never sent before successful backend identity proof.

Preventive controls:
- Centralize backend identity verification in PythonBridgeService.
- Never treat HTTP success alone as process identity.

<a id="finding-2"></a>

### [2] Loopback client can replace the active project timeline without an owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Missing authorization |
| CWE | CWE-862 |
| Affected lines | backend/routers/pacing_router.py:328-341, backend/main.py:617-626, backend/routers/pacing_router.py:419-421 |

#### Summary

Loopback client can replace the active project timeline without an owner capability

#### Root Cause

POST /pacing/timeline accepts caller-controlled entries and commits them with state.set_timeline. The mounted router has no owner-capability/auth dependency. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/pacing_router.py:328-341`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/timeline",
    response_model=StatusResponse,
    summary="Timeline manuell aktualisieren",
    description="Ersetzt die aktuelle Timeline durch eine manuell bearbeitete Version.",
)
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:419-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/pacing_router.py:328-341`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/timeline",
    response_model=StatusResponse,
    summary="Timeline manuell aktualisieren",
    description="Ersetzt die aktuelle Timeline durch eine manuell bearbeitete Version.",
)
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:419-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /pacing/timeline accepts caller-controlled entries and commits them with state.set_timeline. The mounted router has no owner-capability/auth dependency.
- Cited target-commit ranges re-read: backend/routers/pacing_router.py:328-341 \[entrypoint\]; backend/main.py:617-626 \[root_control\]; backend/routers/pacing_router.py:419-421 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/pacing_router.py:328-341 -\> root_control backend/main.py:617-626 -\> sink backend/routers/pacing_router.py:419-421. Effect: POST /pacing/timeline accepts caller-controlled entries and commits them with state.set_timeline. The mounted router has no owner-capability/auth dependency.

**Entrypoint evidence** — `backend/routers/pacing_router.py:328-341`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/timeline",
    response_model=StatusResponse,
    summary="Timeline manuell aktualisieren",
    description="Ersetzt die aktuelle Timeline durch eine manuell bearbeitete Version.",
)
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:419-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

#### Reachability

A same-host caller replaces the active timeline with caller-controlled entries; validation/probing completes and state.set_timeline commits the editing state without owner authentication.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if timeline replacement requires per-launch owner authentication or action-bound confirmation.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-3"></a>

### [3] Current project metadata is disclosed without the launcher owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Security boundary violation |
| CWE | CWE-306 |
| Affected lines | backend/routers/project_router.py:746-750, backend/owner_capability.py:12-23, backend/routers/project_router.py:751-754 |

#### Summary

Current project metadata is disclosed without the launcher owner capability

#### Root Cause

GET /project/info has no authentication dependency and returns the current project object, including its absolute path, database project identifier, timestamps, and media counts. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Source evidence** — `backend/routers/project_router.py:746-750`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:751-754`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_data = dict(state.current_project)
    project_data["audio_count"] = len(state.get_audio_clips_snapshot())
    project_data["video_count"] = len(state.get_video_clips_snapshot())
    return ProjectInfo(**project_data)
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/project_router.py:746-750`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:751-754`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_data = dict(state.current_project)
    project_data["audio_count"] = len(state.get_audio_clips_snapshot())
    project_data["video_count"] = len(state.get_video_clips_snapshot())
    return ProjectInfo(**project_data)
```

Evidence:
- Independent static trace confirmed in the immutable target: GET /project/info has no authentication dependency and returns the current project object, including its absolute path, database project identifier, timestamps, and media counts.
- Cited target-commit ranges re-read: backend/routers/project_router.py:746-750 \[source\]; backend/owner_capability.py:12-23 \[root_control\]; backend/routers/project_router.py:751-754 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/project_router.py:746-750 -\> root_control backend/owner_capability.py:12-23 -\> sink backend/routers/project_router.py:751-754. Effect: GET /project/info has no authentication dependency and returns the current project object, including its absolute path, database project identifier, timestamps, and media counts.

**Source evidence** — `backend/routers/project_router.py:746-750`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/info", response_model=ProjectInfo)
async def project_info(state: AppState = Depends(get_app_state)) -> ProjectInfo:
    """Gibt Informationen zum aktuellen Projekt zurück."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="Kein Projekt geöffnet")
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:751-754`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_data = dict(state.current_project)
    project_data["audio_count"] = len(state.get_audio_clips_snapshot())
    project_data["video_count"] = len(state.get_video_clips_snapshot())
    return ProjectInfo(**project_data)
```

#### Reachability

A same-host process GETs /project/info and obtains the active project absolute path, database identifier, timestamps, and media counts.

#### Severity

**Low** — Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if sensitive path/identifier fields are removed or the endpoint gains per-launch authentication.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-4"></a>

### [4] Loopback client can delete a video clip and its persisted vector state without an owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Missing authorization |
| CWE | CWE-862 |
| Affected lines | backend/routers/video_router.py:677-687, backend/main.py:617-626, backend/routers/video_router.py:687 |

#### Summary

Loopback client can delete a video clip and its persisted vector state without an owner capability

#### Root Cause

The video DELETE route directly invokes state.delete_video_clip, whose documented effect includes SQLite and FAISS cleanup, without requiring the owner capability used by /shutdown. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/video_router.py:677-687`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Video-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Video-Clip aus In-Memory + SQLite + FAISS-Cache."""
    if state.delete_video_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:687`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(clip_id):
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/video_router.py:677-687`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Video-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Video-Clip aus In-Memory + SQLite + FAISS-Cache."""
    if state.delete_video_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:687`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(clip_id):
```

Evidence:
- Independent static trace confirmed in the immutable target: The video DELETE route directly invokes state.delete_video_clip, whose documented effect includes SQLite and FAISS cleanup, without requiring the owner capability used by /shutdown.
- Cited target-commit ranges re-read: backend/routers/video_router.py:677-687 \[entrypoint\]; backend/main.py:617-626 \[root_control\]; backend/routers/video_router.py:687-687 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/video_router.py:677-687 -\> root_control backend/main.py:617-626 -\> sink backend/routers/video_router.py:687-687. Effect: The video DELETE route directly invokes state.delete_video_clip, whose documented effect includes SQLite and FAISS cleanup, without requiring the owner capability used by /shutdown.

**Entrypoint evidence** — `backend/routers/video_router.py:677-687`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Video-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Video-Clip aus In-Memory + SQLite + FAISS-Cache."""
    if state.delete_video_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:687`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(clip_id):
```

#### Reachability

A same-host caller supplies one video clip ID; the route durably removes its catalog and persisted vector state without owner authentication.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if deletion requires per-launch owner authentication or an action-bound confirmation.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-5"></a>

### [5] Loopback client can batch-delete audio clips without an owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Missing authorization |
| CWE | CWE-862 |
| Affected lines | backend/routers/audio_router.py:492-505, backend/main.py:617-626, backend/routers/audio_router.py:505 |

#### Summary

Loopback client can batch-delete audio clips without an owner capability

#### Root Cause

The batch DELETE endpoint accepts caller-selected clip_ids and invokes state.delete_audio_clip for each id, while the mounted router has no authentication or owner-capability dependency. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/audio_router.py:492-505`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Audio-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Audio-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_audio_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:505`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(cid):
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/audio_router.py:492-505`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Audio-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Audio-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_audio_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:505`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(cid):
```

Evidence:
- Independent static trace confirmed in the immutable target: The batch DELETE endpoint accepts caller-selected clip_ids and invokes state.delete_audio_clip for each id, while the mounted router has no authentication or owner-capability dependency.
- Cited target-commit ranges re-read: backend/routers/audio_router.py:492-505 \[entrypoint\]; backend/main.py:617-626 \[root_control\]; backend/routers/audio_router.py:505-505 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/audio_router.py:492-505 -\> root_control backend/main.py:617-626 -\> sink backend/routers/audio_router.py:505-505. Effect: The batch DELETE endpoint accepts caller-selected clip_ids and invokes state.delete_audio_clip for each id, while the mounted router has no authentication or owner-capability dependency.

**Entrypoint evidence** — `backend/routers/audio_router.py:492-505`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Audio-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Audio-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_audio_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:505`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(cid):
```

#### Reachability

A same-host caller supplies multiple audio clip IDs; the batch route durably removes matching active-project clip state without per-launch owner authorization.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if deletion requires the launcher/session owner capability or another action-bound authenticated confirmation.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-6"></a>

### [6] The complete process-global chat history is returned by a loopback endpoint without owner authorization

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Sensitive data exposure |
| CWE | CWE-200, CWE-862 |
| Affected lines | backend/routers/chat_router.py:279-285 |

#### Summary

The complete process-global chat history is returned by a loopback endpoint without owner authorization.

#### Root Cause

GET /chat/history has no owner-capability dependency and returns every stored user and assistant entry from _history_store. Any other process under the same host that can reach 127.0.0.1:8765 can retrieve the current user conversation, including project-related content retained by the server. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Sink evidence** — `backend/routers/chat_router.py:279-285`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    """Liefert die Server-Side Chat-History."""
    entries = await _history_store.snapshot()
    return HistoryResponse(
        entries=[ChatHistoryEntry(**e) for e in entries],
        count=len(entries),
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Sink evidence** — `backend/routers/chat_router.py:279-285`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    """Liefert die Server-Side Chat-History."""
    entries = await _history_store.snapshot()
    return HistoryResponse(
        entries=[ChatHistoryEntry(**e) for e in entries],
        count=len(entries),
```

Evidence:
- Independent static trace confirmed in the immutable target: GET /chat/history has no owner-capability dependency and returns every stored user and assistant entry from _history_store. Any other process under the same host that can reach 127.0.0.1:8765 can retrieve the current user conversation, including project-related content retained by the server.
- Cited target-commit ranges re-read: backend/routers/chat_router.py:279-285 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: sink backend/routers/chat_router.py:279-285. Effect: GET /chat/history has no owner-capability dependency and returns every stored user and assistant entry from _history_store. Any other process under the same host that can reach 127.0.0.1:8765 can retrieve the current user conversation, including project-related content retained by the server.

**Sink evidence** — `backend/routers/chat_router.py:279-285`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get("/history", response_model=HistoryResponse)
async def get_history() -> HistoryResponse:
    """Liefert die Server-Side Chat-History."""
    entries = await _history_store.snapshot()
    return HistoryResponse(
        entries=[ChatHistoryEntry(**e) for e in entries],
        count=len(entries),
```

#### Reachability

Any same-host process can GET /chat/history while PB Studio is running and receive the process-global retained conversation without an owner/session proof.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore only if the route is removed, returns caller-scoped history, or all application routes receive an authenticated per-launch owner/session control.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-7"></a>

### [7] Unauthenticated timeline endpoint exposes project media paths and editing metadata

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Sensitive data exposure |
| CWE | CWE-200, CWE-862 |
| Affected lines | backend/main.py:617-626, backend/routers/pacing_router.py:285-325 |

#### Summary

Unauthenticated timeline endpoint exposes project media paths and editing metadata

#### Root Cause

GET /pacing/timeline returns each entry's file_path, full metadata, and state.current_audio_path. The router is globally mounted without authentication or an owner-capability dependency. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:285-325`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Aktuelle Timeline abrufen",
    description=(
        "Gibt die zuletzt generierte Timeline zurück. "
        "Enthält alle Clip-Zuweisungen mit Start/End-Zeiten, Trigger-Typ und -Stärke. "
        "Leere Timeline wenn noch keine Cut-Liste generiert wurde."
    ),
)
async def get_timeline(state: AppState = Depends(get_app_state)) -> TimelineResponse:
    """Gibt die aktuelle Timeline zurück."""
    entries = []
    for cut in state.get_timeline_snapshot():
        meta = cut.get("metadata", {})
        entries.append(TimelineEntrySchema(
            clip_id=cut.get("clip_id", ""),
            clip_name=meta.get("clip_name", "Unknown"),
            file_path=meta.get("file_path", ""),
            start_time=cut.get("start_time", 0.0),
            end_time=cut.get("end_time", 0.0),
            clip_start=meta.get("clip_start", 0.0),
            trigger_type=meta.get("trigger_type", ""),
            trigger_strength=meta.get("trigger_strength", 0.0),
            segment_type=meta.get("segment_type"),
            brain_confidence=float(meta.get("brain_final_score", 0.0) or 0.0),
            cut_id=meta.get("cut_id"),
            feature_confidence=float(meta.get("feature_confidence", 0.0) or 0.0),
            semantic_status=str(meta.get("semantic_status", "unavailable")),
            semantic_reason=meta.get("semantic_reason"),
            trigger_provenance=dict(meta.get("trigger_provenance") or {}),
            brain_axis_status=dict(meta.get("brain_axis_status") or {}),
            metadata=dict(meta),
        ))

    total = entries[-1].end_time if entries else 0.0
    return TimelineResponse(
        entries=entries,
        total_duration=total,
        audio_path=state.current_audio_path,
    )
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:285-325`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Aktuelle Timeline abrufen",
    description=(
        "Gibt die zuletzt generierte Timeline zurück. "
        "Enthält alle Clip-Zuweisungen mit Start/End-Zeiten, Trigger-Typ und -Stärke. "
        "Leere Timeline wenn noch keine Cut-Liste generiert wurde."
    ),
)
async def get_timeline(state: AppState = Depends(get_app_state)) -> TimelineResponse:
    """Gibt die aktuelle Timeline zurück."""
    entries = []
    for cut in state.get_timeline_snapshot():
        meta = cut.get("metadata", {})
        entries.append(TimelineEntrySchema(
            clip_id=cut.get("clip_id", ""),
            clip_name=meta.get("clip_name", "Unknown"),
            file_path=meta.get("file_path", ""),
            start_time=cut.get("start_time", 0.0),
            end_time=cut.get("end_time", 0.0),
            clip_start=meta.get("clip_start", 0.0),
            trigger_type=meta.get("trigger_type", ""),
            trigger_strength=meta.get("trigger_strength", 0.0),
            segment_type=meta.get("segment_type"),
            brain_confidence=float(meta.get("brain_final_score", 0.0) or 0.0),
            cut_id=meta.get("cut_id"),
            feature_confidence=float(meta.get("feature_confidence", 0.0) or 0.0),
            semantic_status=str(meta.get("semantic_status", "unavailable")),
            semantic_reason=meta.get("semantic_reason"),
            trigger_provenance=dict(meta.get("trigger_provenance") or {}),
            brain_axis_status=dict(meta.get("brain_axis_status") or {}),
            metadata=dict(meta),
        ))

    total = entries[-1].end_time if entries else 0.0
    return TimelineResponse(
        entries=entries,
        total_duration=total,
        audio_path=state.current_audio_path,
    )
```

Evidence:
- Independent static trace confirmed in the immutable target: GET /pacing/timeline returns each entry's file_path, full metadata, and state.current_audio_path. The router is globally mounted without authentication or an owner-capability dependency.
- Cited target-commit ranges re-read: backend/main.py:617-626 \[root_control\]; backend/routers/pacing_router.py:285-325 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: root_control backend/main.py:617-626 -\> sink backend/routers/pacing_router.py:285-325. Effect: GET /pacing/timeline returns each entry's file_path, full metadata, and state.current_audio_path. The router is globally mounted without authentication or an owner-capability dependency.

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/pacing_router.py:285-325`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Aktuelle Timeline abrufen",
    description=(
        "Gibt die zuletzt generierte Timeline zurück. "
        "Enthält alle Clip-Zuweisungen mit Start/End-Zeiten, Trigger-Typ und -Stärke. "
        "Leere Timeline wenn noch keine Cut-Liste generiert wurde."
    ),
)
async def get_timeline(state: AppState = Depends(get_app_state)) -> TimelineResponse:
    """Gibt die aktuelle Timeline zurück."""
    entries = []
    for cut in state.get_timeline_snapshot():
        meta = cut.get("metadata", {})
        entries.append(TimelineEntrySchema(
            clip_id=cut.get("clip_id", ""),
            clip_name=meta.get("clip_name", "Unknown"),
            file_path=meta.get("file_path", ""),
            start_time=cut.get("start_time", 0.0),
            end_time=cut.get("end_time", 0.0),
            clip_start=meta.get("clip_start", 0.0),
            trigger_type=meta.get("trigger_type", ""),
            trigger_strength=meta.get("trigger_strength", 0.0),
            segment_type=meta.get("segment_type"),
            brain_confidence=float(meta.get("brain_final_score", 0.0) or 0.0),
            cut_id=meta.get("cut_id"),
            feature_confidence=float(meta.get("feature_confidence", 0.0) or 0.0),
            semantic_status=str(meta.get("semantic_status", "unavailable")),
            semantic_reason=meta.get("semantic_reason"),
            trigger_provenance=dict(meta.get("trigger_provenance") or {}),
            brain_axis_status=dict(meta.get("brain_axis_status") or {}),
            metadata=dict(meta),
        ))

    total = entries[-1].end_time if entries else 0.0
    return TimelineResponse(
        entries=entries,
        total_duration=total,
        audio_path=state.current_audio_path,
    )
```

#### Reachability

A same-host process can GET /pacing/timeline and receive absolute media paths, current audio path, editing metadata, and state for the active project.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Reassess if response fields are minimized or the route gains per-launch caller authentication.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-8"></a>

### [8] Project close and job cancellation are reachable without the launcher owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Security boundary violation |
| CWE | CWE-306 |
| Affected lines | backend/routers/project_router.py:713-716, backend/owner_capability.py:12-23, backend/routers/project_router.py:721-728 |

#### Summary

Project close and job cancellation are reachable without the launcher owner capability

#### Root Cause

POST /project/close has no authentication parameter; it invalidates project context, drains project jobs, sets every render cancel flag, and resets state. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Source evidence** — `backend/routers/project_router.py:713-716`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/close", response_model=StatusResponse)
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    async with state.project_lifecycle_lock:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:721-728`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
state.invalidate_project_context()
        _, pending = await state.cancel_and_drain_project_tasks()
        # In-flight Render-Threads nutzen weiterhin ihre bestehenden Cancel-Flags.
        with state._state_lock:
            task_ids = list(state.render_tasks.keys())
        for task_id in task_ids:
            state.set_cancel_flag(task_id, True)
        state.reset(invalidate_context=False)
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/project_router.py:713-716`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/close", response_model=StatusResponse)
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    async with state.project_lifecycle_lock:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:721-728`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
state.invalidate_project_context()
        _, pending = await state.cancel_and_drain_project_tasks()
        # In-flight Render-Threads nutzen weiterhin ihre bestehenden Cancel-Flags.
        with state._state_lock:
            task_ids = list(state.render_tasks.keys())
        for task_id in task_ids:
            state.set_cancel_flag(task_id, True)
        state.reset(invalidate_context=False)
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /project/close has no authentication parameter; it invalidates project context, drains project jobs, sets every render cancel flag, and resets state.
- Cited target-commit ranges re-read: backend/routers/project_router.py:713-716 \[source\]; backend/owner_capability.py:12-23 \[root_control\]; backend/routers/project_router.py:721-728 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/project_router.py:713-716 -\> root_control backend/owner_capability.py:12-23 -\> sink backend/routers/project_router.py:721-728. Effect: POST /project/close has no authentication parameter; it invalidates project context, drains project jobs, sets every render cancel flag, and resets state.

**Source evidence** — `backend/routers/project_router.py:713-716`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/close", response_model=StatusResponse)
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Schließt das aktuelle Projekt und räumt State auf."""
    async with state.project_lifecycle_lock:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:721-728`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
state.invalidate_project_context()
        _, pending = await state.cancel_and_drain_project_tasks()
        # In-flight Render-Threads nutzen weiterhin ihre bestehenden Cancel-Flags.
        with state._state_lock:
            task_ids = list(state.render_tasks.keys())
        for task_id in task_ids:
            state.set_cancel_flag(task_id, True)
        state.reset(invalidate_context=False)
```

#### Reachability

A same-host caller POSTs /project/close; the backend invalidates the project context, drains jobs, cancels renders, and resets active state, disrupting the owner workflow.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if close/cancel becomes owner-authenticated or is made idempotent without cancelling owner work.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-9"></a>

### [9] Project activation is reachable without the launcher owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Security boundary violation |
| CWE | CWE-306 |
| Affected lines | backend/routers/project_router.py:488-500, backend/owner_capability.py:12-23, backend/routers/project_router.py:571-577 |

#### Summary

Project activation is reachable without the launcher owner capability

#### Root Cause

POST /project/open accepts a caller-selected in-root directory and ultimately invokes _activate_project, switching Brain binding, project epoch, media catalog, timeline, and current state. No capability header or authorization dependency appears in the route. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Source evidence** — `backend/routers/project_router.py:488-500`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path).resolve()
    # SEC-001: Path-Traversal-Schutz für Open (gegen globalen Basis-Ordner)
    allowed_base = Path(config.project_dir).resolve()
    if not project_path.is_relative_to(allowed_base):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    if not project_path.exists():
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:571-577`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        await _activate_project(
            state,
            project_path,
            project_data,
            candidate_state,
        )
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/project_router.py:488-500`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path).resolve()
    # SEC-001: Path-Traversal-Schutz für Open (gegen globalen Basis-Ordner)
    allowed_base = Path(config.project_dir).resolve()
    if not project_path.is_relative_to(allowed_base):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    if not project_path.exists():
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:571-577`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        await _activate_project(
            state,
            project_path,
            project_data,
            candidate_state,
        )
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /project/open accepts a caller-selected in-root directory and ultimately invokes _activate_project, switching Brain binding, project epoch, media catalog, timeline, and current state. No capability header or authorization dependency appears in the route.
- Cited target-commit ranges re-read: backend/routers/project_router.py:488-500 \[source\]; backend/owner_capability.py:12-23 \[root_control\]; backend/routers/project_router.py:571-577 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/project_router.py:488-500 -\> root_control backend/owner_capability.py:12-23 -\> sink backend/routers/project_router.py:571-577. Effect: POST /project/open accepts a caller-selected in-root directory and ultimately invokes _activate_project, switching Brain binding, project epoch, media catalog, timeline, and current state. No capability header or authorization dependency appears in the route.

**Source evidence** — `backend/routers/project_router.py:488-500`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/open", response_model=ProjectInfo)
async def open_project(
    request: ProjectOpen,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Öffnet ein bestehendes Projekt."""

    project_path = Path(request.path).resolve()
    # SEC-001: Path-Traversal-Schutz für Open (gegen globalen Basis-Ordner)
    allowed_base = Path(config.project_dir).resolve()
    if not project_path.is_relative_to(allowed_base):
        raise HTTPException(status_code=403, detail="Pfad außerhalb des erlaubten Projektverzeichnisses")
    if not project_path.exists():
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:571-577`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        await _activate_project(
            state,
            project_path,
            project_data,
            candidate_state,
        )
```

#### Reachability

A same-host caller selects an existing in-root project; _activate_project rebinds Brain and replaces project epoch, catalog, timeline, and current state while the owner may be working.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if activation is owner-authenticated or limited to an action-bound desktop capability.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-10"></a>

### [10] Project creation is reachable without the launcher owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Security boundary violation |
| CWE | CWE-306 |
| Affected lines | backend/routers/project_router.py:353-360, backend/owner_capability.py:12-23, backend/routers/project_router.py:379-414 |

#### Summary

Project creation is reachable without the launcher owner capability

#### Root Cause

POST /project/create accepts caller-controlled path/name and creates directories, a state database, a global repository record, and metadata before atomically publishing the directory. The route signature has no owner-capability header or authorization dependency even though the repository provides authorize_owner for destructive loopback operations. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Source evidence** — `backend/routers/project_router.py:353-360`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/create", response_model=ProjectInfo)
async def create_project(
    request: ProjectCreate,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Erstellt ein neues Projekt."""

    project_path = (Path(request.path) / request.name).resolve()
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:379-414`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path = Path(
            tempfile.mkdtemp(
                prefix=".pb-studio-create-",
                dir=str(project_path.parent),
            )
        ).resolve()
        _write_creation_owner(
            staging_path,
            owner_token=owner_token,
            target_path=project_path,
        )
        for directory_name in ("audio", "video", "output", "cache"):
            (staging_path / directory_name).mkdir()
        _prepare_project_state_db(staging_path)

        created_at = _utc_now_iso()
        project_data = {
            "name": request.name,
            "path": str(project_path),
            "audio_count": 0,
            "video_count": 0,
            "has_timeline": False,
            "created_at": created_at,
            "modified_at": created_at,
        }
        project_id = ProjectRepository().create_owned_project(
            request.name,
            project_data,
            owner_token,
        )
        project_data["db_project_id"] = project_id
        _write_project_meta(staging_path, project_data)

        # Same-volume rename publishes the fully prepared directory atomically.
        os.replace(str(staging_path), str(project_path))
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/project_router.py:353-360`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/create", response_model=ProjectInfo)
async def create_project(
    request: ProjectCreate,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Erstellt ein neues Projekt."""

    project_path = (Path(request.path) / request.name).resolve()
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:379-414`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path = Path(
            tempfile.mkdtemp(
                prefix=".pb-studio-create-",
                dir=str(project_path.parent),
            )
        ).resolve()
        _write_creation_owner(
            staging_path,
            owner_token=owner_token,
            target_path=project_path,
        )
        for directory_name in ("audio", "video", "output", "cache"):
            (staging_path / directory_name).mkdir()
        _prepare_project_state_db(staging_path)

        created_at = _utc_now_iso()
        project_data = {
            "name": request.name,
            "path": str(project_path),
            "audio_count": 0,
            "video_count": 0,
            "has_timeline": False,
            "created_at": created_at,
            "modified_at": created_at,
        }
        project_id = ProjectRepository().create_owned_project(
            request.name,
            project_data,
            owner_token,
        )
        project_data["db_project_id"] = project_id
        _write_project_meta(staging_path, project_data)

        # Same-volume rename publishes the fully prepared directory atomically.
        os.replace(str(staging_path), str(project_path))
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /project/create accepts caller-controlled path/name and creates directories, a state database, a global repository record, and metadata before atomically publishing the directory. The route signature has no owner-capability header or authorization dependency even though the repository provides authorize_owner for destructive loopback operations.
- Cited target-commit ranges re-read: backend/routers/project_router.py:353-360 \[source\]; backend/owner_capability.py:12-23 \[root_control\]; backend/routers/project_router.py:379-414 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/project_router.py:353-360 -\> root_control backend/owner_capability.py:12-23 -\> sink backend/routers/project_router.py:379-414. Effect: POST /project/create accepts caller-controlled path/name and creates directories, a state database, a global repository record, and metadata before atomically publishing the directory. The route signature has no owner-capability header or authorization dependency even though the repository provides authorize_owner for destructive loopback operations.

**Source evidence** — `backend/routers/project_router.py:353-360`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/create", response_model=ProjectInfo)
async def create_project(
    request: ProjectCreate,
    state: AppState = Depends(get_app_state),
) -> ProjectInfo:
    """Erstellt ein neues Projekt."""

    project_path = (Path(request.path) / request.name).resolve()
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/project_router.py:379-414`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
project_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path = Path(
            tempfile.mkdtemp(
                prefix=".pb-studio-create-",
                dir=str(project_path.parent),
            )
        ).resolve()
        _write_creation_owner(
            staging_path,
            owner_token=owner_token,
            target_path=project_path,
        )
        for directory_name in ("audio", "video", "output", "cache"):
            (staging_path / directory_name).mkdir()
        _prepare_project_state_db(staging_path)

        created_at = _utc_now_iso()
        project_data = {
            "name": request.name,
            "path": str(project_path),
            "audio_count": 0,
            "video_count": 0,
            "has_timeline": False,
            "created_at": created_at,
            "modified_at": created_at,
        }
        project_id = ProjectRepository().create_owned_project(
            request.name,
            project_data,
            owner_token,
        )
        project_data["db_project_id"] = project_id
        _write_project_meta(staging_path, project_data)

        # Same-volume rename publishes the fully prepared directory atomically.
        os.replace(str(staging_path), str(project_path))
```

#### Reachability

A same-host caller POSTs a permitted project name/path; PB Studio creates directories, metadata, state DB, and a repository record using application semantics.

#### Severity

**Low** — Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if project creation requires owner authorization or cannot affect the active/global PB project repository.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-11"></a>

### [11] Brain feedback allows unauthenticated learning-state mutation

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Security boundary violation |
| CWE | CWE-306 |
| Affected lines | backend/routers/brain_router.py:142-146, backend/routers/brain_router.py:362-393, backend/routers/brain_router.py:193-210 |

#### Summary

Brain feedback allows unauthenticated learning-state mutation

#### Root Cause

POST /brain/feedback accepts cut_id and rating and persists feedback through lease.run_write without an owner capability. In the same router, the destructive /brain/reset route explicitly requires and verifies the launcher capability, demonstrating that the control exists but is not applied to feedback. Closest-control assessment: The reset route uses authorize_owner, confirming owner authorization exists but is absent from feedback.

**Source evidence** — `backend/routers/brain_router.py:142-146`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/feedback", response_model=BrainFeedbackResponse)
async def feedback(
    req: BrainFeedbackRequest,
    state: AppState = Depends(get_app_state),
) -> BrainFeedbackResponse:
```

**Root Control evidence** — `backend/routers/brain_router.py:362-393`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/reset",
    response_model=BrainResetResponse,
    responses={
        403: {"description": "Owner-Capability oder Token-Owner ungueltig."},
        503: {"description": "Backend wurde ohne Owner-Capability gestartet."},
    },
    openapi_extra={
        "parameters": [
            {
                "name": OWNER_CAPABILITY_HEADER,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": (
                    "Runtime-required launcher capability; confirmation "
                    "tokens are bound to this owner."
                ),
            }
        ]
    },
)
async def reset(
    req: Optional[BrainResetRequest] = None,
    owner_capability: str | None = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
        include_in_schema=False,
    ),
) -> BrainResetResponse:
    """Owner-bound two-step reset with an expiring, single-use token."""
    owner_id = _authorize_reset_owner(owner_capability)
```

**Sink evidence** — `backend/routers/brain_router.py:193-210`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
def _apply_feedback(_connection):
                    return feedback_logger.log_feedback(
                        cut_id=req.cut_id,
                        rating=req.rating,
                        context_keys=context_keys,
                        assignments=assignments,
                    )

                # Z2 / GPU-F4: log_feedback macht SQLite-INSERT + WeightStore-Math
                # (~10-50ms). db_write_lock bleibt der globale Vertrag; der
                # Lease-Guard linearisiert zusaetzlich gegen Projektwechsel.
                from ..dependencies import db_write_lock
                async with db_write_lock:
                    try:
                        bumps = await asyncio.to_thread(
                            lease.run_write,
                            _apply_feedback,
                        )
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/brain_router.py:142-146`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/feedback", response_model=BrainFeedbackResponse)
async def feedback(
    req: BrainFeedbackRequest,
    state: AppState = Depends(get_app_state),
) -> BrainFeedbackResponse:
```

**Root Control evidence** — `backend/routers/brain_router.py:362-393`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/reset",
    response_model=BrainResetResponse,
    responses={
        403: {"description": "Owner-Capability oder Token-Owner ungueltig."},
        503: {"description": "Backend wurde ohne Owner-Capability gestartet."},
    },
    openapi_extra={
        "parameters": [
            {
                "name": OWNER_CAPABILITY_HEADER,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": (
                    "Runtime-required launcher capability; confirmation "
                    "tokens are bound to this owner."
                ),
            }
        ]
    },
)
async def reset(
    req: Optional[BrainResetRequest] = None,
    owner_capability: str | None = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
        include_in_schema=False,
    ),
) -> BrainResetResponse:
    """Owner-bound two-step reset with an expiring, single-use token."""
    owner_id = _authorize_reset_owner(owner_capability)
```

**Sink evidence** — `backend/routers/brain_router.py:193-210`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
def _apply_feedback(_connection):
                    return feedback_logger.log_feedback(
                        cut_id=req.cut_id,
                        rating=req.rating,
                        context_keys=context_keys,
                        assignments=assignments,
                    )

                # Z2 / GPU-F4: log_feedback macht SQLite-INSERT + WeightStore-Math
                # (~10-50ms). db_write_lock bleibt der globale Vertrag; der
                # Lease-Guard linearisiert zusaetzlich gegen Projektwechsel.
                from ..dependencies import db_write_lock
                async with db_write_lock:
                    try:
                        bumps = await asyncio.to_thread(
                            lease.run_write,
                            _apply_feedback,
                        )
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /brain/feedback accepts cut_id and rating and persists feedback through lease.run_write without an owner capability. In the same router, the destructive /brain/reset route explicitly requires and verifies the launcher capability, demonstrating that the control exists but is not applied to feedback.
- Cited target-commit ranges re-read: backend/routers/brain_router.py:142-146 \[source\]; backend/routers/brain_router.py:362-393 \[root_control\]; backend/routers/brain_router.py:193-210 \[sink\]

Counterevidence and remaining uncertainty:
- The reset route uses authorize_owner, confirming owner authorization exists but is absent from feedback.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/brain_router.py:142-146 -\> root_control backend/routers/brain_router.py:362-393 -\> sink backend/routers/brain_router.py:193-210. Effect: POST /brain/feedback accepts cut_id and rating and persists feedback through lease.run_write without an owner capability. In the same router, the destructive /brain/reset route explicitly requires and verifies the launcher capability, demonstrating that the control exists but is not applied to feedback.

**Source evidence** — `backend/routers/brain_router.py:142-146`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/feedback", response_model=BrainFeedbackResponse)
async def feedback(
    req: BrainFeedbackRequest,
    state: AppState = Depends(get_app_state),
) -> BrainFeedbackResponse:
```

**Root Control evidence** — `backend/routers/brain_router.py:362-393`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/reset",
    response_model=BrainResetResponse,
    responses={
        403: {"description": "Owner-Capability oder Token-Owner ungueltig."},
        503: {"description": "Backend wurde ohne Owner-Capability gestartet."},
    },
    openapi_extra={
        "parameters": [
            {
                "name": OWNER_CAPABILITY_HEADER,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": (
                    "Runtime-required launcher capability; confirmation "
                    "tokens are bound to this owner."
                ),
            }
        ]
    },
)
async def reset(
    req: Optional[BrainResetRequest] = None,
    owner_capability: str | None = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
        include_in_schema=False,
    ),
) -> BrainResetResponse:
    """Owner-bound two-step reset with an expiring, single-use token."""
    owner_id = _authorize_reset_owner(owner_capability)
```

**Sink evidence** — `backend/routers/brain_router.py:193-210`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
def _apply_feedback(_connection):
                    return feedback_logger.log_feedback(
                        cut_id=req.cut_id,
                        rating=req.rating,
                        context_keys=context_keys,
                        assignments=assignments,
                    )

                # Z2 / GPU-F4: log_feedback macht SQLite-INSERT + WeightStore-Math
                # (~10-50ms). db_write_lock bleibt der globale Vertrag; der
                # Lease-Guard linearisiert zusaetzlich gegen Projektwechsel.
                from ..dependencies import db_write_lock
                async with db_write_lock:
                    try:
                        bumps = await asyncio.to_thread(
                            lease.run_write,
                            _apply_feedback,
                        )
```

#### Reachability

A same-host caller submits cut_id/rating feedback; the backend persists it into the active project Brain learning state without owner confirmation, allowing targeted model-behavior poisoning.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if feedback is bound to an authenticated owner action or becomes non-persistent/untrusted telemetry excluded from learning.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-12"></a>

### [12] Project MCP configuration executes an unpinned latest npm package

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | medium |
| Confidence rationale | The static source/control/sink trace is complete, while practical impact magnitude or an environment-specific precondition was not exercised at runtime. |
| Category | Security boundary violation |
| CWE | CWE-829 |
| Affected lines | .claude/settings.local.json:26-27, .mcp.json:3-7 |

#### Summary

Project MCP configuration executes an unpinned latest npm package

#### Root Cause

The repository MCP entry uses npx -y @upstash/context7-mcp@latest. This resolves and executes mutable future package content instead of a reviewed immutable version. The checked-in Claude settings disable project MCP servers locally, but that client-specific setting is not an integrity control for other MCP-capable clients or users who enable the declared server. Closest-control assessment: Claude local settings disable project MCP servers by default, but that client-specific setting does not pin the package when the project MCP entry is enabled or used elsewhere.

**Root Control evidence** — `.claude/settings.local.json:26-27`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"enableAllProjectMcpServers": false,
  "enabledMcpjsonServers": [],
```

**Sink evidence** — `.mcp.json:3-7`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "description": "Live-Dokumentation fuer onnxruntime, FastAPI, WPF, librosa, demucs und andere PB Studio Bibliotheken"
    }
```

#### Validation

The candidate survived compact validation as reportable with medium confidence. The static source/control/sink trace is complete, while practical impact magnitude or an environment-specific precondition was not exercised at runtime.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Root Control evidence** — `.claude/settings.local.json:26-27`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"enableAllProjectMcpServers": false,
  "enabledMcpjsonServers": [],
```

**Sink evidence** — `.mcp.json:3-7`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "description": "Live-Dokumentation fuer onnxruntime, FastAPI, WPF, librosa, demucs und andere PB Studio Bibliotheken"
    }
```

Evidence:
- Independent static trace confirmed in the immutable target: The repository MCP entry uses npx -y @upstash/context7-mcp@latest. This resolves and executes mutable future package content instead of a reviewed immutable version. The checked-in Claude settings disable project MCP servers locally, but that client-specific setting is not an integrity control for other MCP-capable clients or users who enable the declared server.
- Cited target-commit ranges re-read: .claude/settings.local.json:26-27 \[root_control\]; .mcp.json:3-7 \[sink\]

Counterevidence and remaining uncertainty:
- Claude local settings disable project MCP servers by default, but that client-specific setting does not pin the package when the project MCP entry is enabled or used elsewhere.
- Execution depends on a compatible MCP client enabling the project configuration.

#### Dataflow

Attacker/precondition: A compatible MCP client enables and launches the project MCP server. Flow: root_control .claude/settings.local.json:26-27 -\> sink .mcp.json:3-7. Effect: The repository MCP entry uses npx -y @upstash/context7-mcp@latest. This resolves and executes mutable future package content instead of a reviewed immutable version. The checked-in Claude settings disable project MCP servers locally, but that client-specific setting is not an integrity control for other MCP-capable clients or users who enable the declared server.

**Root Control evidence** — `.claude/settings.local.json:26-27`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"enableAllProjectMcpServers": false,
  "enabledMcpjsonServers": [],
```

**Sink evidence** — `.mcp.json:3-7`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```json
"context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "description": "Live-Dokumentation fuer onnxruntime, FastAPI, WPF, librosa, demucs und andere PB Studio Bibliotheken"
    }
```

#### Reachability

An MCP-capable client that enables the checked-in server runs npx -y @upstash/context7-mcp@latest; compromise or malicious future publication of that mutable package executes under the developer account.

#### Severity

**Low** — Severity matrix: impact=high and likelihood=low yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if the MCP package is pinned to a reviewed immutable version/integrity and clients enforce that lock, or if the project MCP declaration is removed.

#### Remediation

Replace the @latest MCP package reference with an reviewed exact version and integrity-bound lock or local installed executable.

Tests:
- Configuration rejects moving tags such as latest.
- The resolved package/version/integrity tuple is recorded in release provenance.

Preventive controls:
- Automate moving-tag detection for executable package configuration.

<a id="finding-13"></a>

### [13] Timeline replacement accepts an unbounded entry collection

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | medium |
| Confidence rationale | The static source/control/sink trace is complete, while practical impact magnitude or an environment-specific precondition was not exercised at runtime. |
| Category | Uncontrolled resource consumption |
| CWE | CWE-400 |
| Affected lines | backend/routers/pacing_router.py:334-358, backend/schemas/pacing_schemas.py:116-118, backend/routers/pacing_router.py:358-421 |

#### Summary

Timeline replacement accepts an unbounded entry collection

#### Root Cause

TimelineUpdateRequest has no maximum length. The route copies metadata for every entry, validates the full list, probes media, and persists it, allowing one request to consume unbounded memory and CPU and inflate persistent project state. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/pacing_router.py:334-358`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _update_timeline_for_project(
    request: TimelineUpdateRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> StatusResponse:
    """Aktualisiert die Timeline im State."""
    current_audio_path = state.current_audio_path
    internal_cuts = []
    for entry in request.entries:
```

**Root Control evidence** — `backend/schemas/pacing_schemas.py:116-118`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
class TimelineUpdateRequest(BaseModel):
    """Request: Timeline manuell aktualisieren."""
    entries: list[TimelineEntrySchema]
```

**Sink evidence** — `backend/routers/pacing_router.py:358-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
for entry in request.entries:
        metadata = dict(entry.metadata)
        metadata.update({
            "clip_name": entry.clip_name,
            "file_path": entry.file_path,
            "clip_start": entry.clip_start,
            "trigger_type": entry.trigger_type,
            "trigger_strength": entry.trigger_strength,
            "segment_type": entry.segment_type,
            "brain_final_score": entry.brain_confidence,
            "cut_id": entry.cut_id,
            "feature_confidence": entry.feature_confidence,
            "semantic_status": entry.semantic_status,
            "semantic_reason": entry.semantic_reason,
            "trigger_provenance": dict(entry.trigger_provenance),
            "brain_axis_status": dict(entry.brain_axis_status),
        })
        internal_cuts.append({
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": metadata,
        })

    try:
        internal_cuts = validate_timeline_media_paths(
            internal_cuts,
            state.get_video_clips_snapshot(),
        )
        if current_audio_path:
            current_audio_path = validate_registered_media_path(
                current_audio_path,
                (
                    clip.get("path", "")
                    for clip in state.get_audio_clips_snapshot().values()
                ),
                label="Timeline audio_path",
            )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # L-TI-3: clip_start + duration gegen Source-Video-Laenge cappen.
    # Auto-Pfad hat diesen Cap in pacing_service._process_pacing_cuts_to_cutlist
    # (R12b/SEV-004) — manueller Update-Endpoint war ungeschuetzt:
    # User-Drag konnte Dauer > source_duration setzen -> Render erzeugte
    # truncated frames / FFmpeg-Errors.
    internal_cuts = _cap_entries_against_source(internal_cuts, state)

    audio_dur = 0.0
    if current_audio_path:
        from pb_studio.rendering.render_service import RenderService
        # AP1.2 (Audit 2026-06-10): ffprobe-Subprocess blockierte den Event-Loop
        # (SSE-Keepalives/parallele Requests froren ein) -> to_thread
        audio_dur = await asyncio.to_thread(
            RenderService()._get_audio_duration, current_audio_path
        ) or 0.0

    warnings, errors = validate_timeline(internal_cuts, audio_duration=audio_dur)
    if errors:
        raise HTTPException(status_code=400, detail=f"Ungültige Timeline: {'; '.join(errors)}")

    with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

#### Validation

The candidate survived compact validation as reportable with medium confidence. The static source/control/sink trace is complete, while practical impact magnitude or an environment-specific precondition was not exercised at runtime.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/pacing_router.py:334-358`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _update_timeline_for_project(
    request: TimelineUpdateRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> StatusResponse:
    """Aktualisiert die Timeline im State."""
    current_audio_path = state.current_audio_path
    internal_cuts = []
    for entry in request.entries:
```

**Root Control evidence** — `backend/schemas/pacing_schemas.py:116-118`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
class TimelineUpdateRequest(BaseModel):
    """Request: Timeline manuell aktualisieren."""
    entries: list[TimelineEntrySchema]
```

**Sink evidence** — `backend/routers/pacing_router.py:358-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
for entry in request.entries:
        metadata = dict(entry.metadata)
        metadata.update({
            "clip_name": entry.clip_name,
            "file_path": entry.file_path,
            "clip_start": entry.clip_start,
            "trigger_type": entry.trigger_type,
            "trigger_strength": entry.trigger_strength,
            "segment_type": entry.segment_type,
            "brain_final_score": entry.brain_confidence,
            "cut_id": entry.cut_id,
            "feature_confidence": entry.feature_confidence,
            "semantic_status": entry.semantic_status,
            "semantic_reason": entry.semantic_reason,
            "trigger_provenance": dict(entry.trigger_provenance),
            "brain_axis_status": dict(entry.brain_axis_status),
        })
        internal_cuts.append({
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": metadata,
        })

    try:
        internal_cuts = validate_timeline_media_paths(
            internal_cuts,
            state.get_video_clips_snapshot(),
        )
        if current_audio_path:
            current_audio_path = validate_registered_media_path(
                current_audio_path,
                (
                    clip.get("path", "")
                    for clip in state.get_audio_clips_snapshot().values()
                ),
                label="Timeline audio_path",
            )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # L-TI-3: clip_start + duration gegen Source-Video-Laenge cappen.
    # Auto-Pfad hat diesen Cap in pacing_service._process_pacing_cuts_to_cutlist
    # (R12b/SEV-004) — manueller Update-Endpoint war ungeschuetzt:
    # User-Drag konnte Dauer > source_duration setzen -> Render erzeugte
    # truncated frames / FFmpeg-Errors.
    internal_cuts = _cap_entries_against_source(internal_cuts, state)

    audio_dur = 0.0
    if current_audio_path:
        from pb_studio.rendering.render_service import RenderService
        # AP1.2 (Audit 2026-06-10): ffprobe-Subprocess blockierte den Event-Loop
        # (SSE-Keepalives/parallele Requests froren ein) -> to_thread
        audio_dur = await asyncio.to_thread(
            RenderService()._get_audio_duration, current_audio_path
        ) or 0.0

    warnings, errors = validate_timeline(internal_cuts, audio_duration=audio_dur)
    if errors:
        raise HTTPException(status_code=400, detail=f"Ungültige Timeline: {'; '.join(errors)}")

    with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

Evidence:
- Independent static trace confirmed in the immutable target: TimelineUpdateRequest has no maximum length. The route copies metadata for every entry, validates the full list, probes media, and persists it, allowing one request to consume unbounded memory and CPU and inflate persistent project state.
- Cited target-commit ranges re-read: backend/routers/pacing_router.py:334-358 \[entrypoint\]; backend/schemas/pacing_schemas.py:116-118 \[root_control\]; backend/routers/pacing_router.py:358-421 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- The request size that materially degrades service is environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/pacing_router.py:334-358 -\> root_control backend/schemas/pacing_schemas.py:116-118 -\> sink backend/routers/pacing_router.py:358-421. Effect: TimelineUpdateRequest has no maximum length. The route copies metadata for every entry, validates the full list, probes media, and persists it, allowing one request to consume unbounded memory and CPU and inflate persistent project state.

**Entrypoint evidence** — `backend/routers/pacing_router.py:334-358`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im unveraenderlichen Projektkontext."""
    try:
        async with state.project_operation() as context:
            return await _update_timeline_for_project(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _update_timeline_for_project(
    request: TimelineUpdateRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> StatusResponse:
    """Aktualisiert die Timeline im State."""
    current_audio_path = state.current_audio_path
    internal_cuts = []
    for entry in request.entries:
```

**Root Control evidence** — `backend/schemas/pacing_schemas.py:116-118`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
class TimelineUpdateRequest(BaseModel):
    """Request: Timeline manuell aktualisieren."""
    entries: list[TimelineEntrySchema]
```

**Sink evidence** — `backend/routers/pacing_router.py:358-421`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
for entry in request.entries:
        metadata = dict(entry.metadata)
        metadata.update({
            "clip_name": entry.clip_name,
            "file_path": entry.file_path,
            "clip_start": entry.clip_start,
            "trigger_type": entry.trigger_type,
            "trigger_strength": entry.trigger_strength,
            "segment_type": entry.segment_type,
            "brain_final_score": entry.brain_confidence,
            "cut_id": entry.cut_id,
            "feature_confidence": entry.feature_confidence,
            "semantic_status": entry.semantic_status,
            "semantic_reason": entry.semantic_reason,
            "trigger_provenance": dict(entry.trigger_provenance),
            "brain_axis_status": dict(entry.brain_axis_status),
        })
        internal_cuts.append({
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": metadata,
        })

    try:
        internal_cuts = validate_timeline_media_paths(
            internal_cuts,
            state.get_video_clips_snapshot(),
        )
        if current_audio_path:
            current_audio_path = validate_registered_media_path(
                current_audio_path,
                (
                    clip.get("path", "")
                    for clip in state.get_audio_clips_snapshot().values()
                ),
                label="Timeline audio_path",
            )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # L-TI-3: clip_start + duration gegen Source-Video-Laenge cappen.
    # Auto-Pfad hat diesen Cap in pacing_service._process_pacing_cuts_to_cutlist
    # (R12b/SEV-004) — manueller Update-Endpoint war ungeschuetzt:
    # User-Drag konnte Dauer > source_duration setzen -> Render erzeugte
    # truncated frames / FFmpeg-Errors.
    internal_cuts = _cap_entries_against_source(internal_cuts, state)

    audio_dur = 0.0
    if current_audio_path:
        from pb_studio.rendering.render_service import RenderService
        # AP1.2 (Audit 2026-06-10): ffprobe-Subprocess blockierte den Event-Loop
        # (SSE-Keepalives/parallele Requests froren ein) -> to_thread
        audio_dur = await asyncio.to_thread(
            RenderService()._get_audio_duration, current_audio_path
        ) or 0.0

    warnings, errors = validate_timeline(internal_cuts, audio_duration=audio_dur)
    if errors:
        raise HTTPException(status_code=400, detail=f"Ungültige Timeline: {'; '.join(errors)}")

    with state.project_commit(context):
        state.current_audio_path = current_audio_path
        state.set_timeline(internal_cuts)
```

#### Reachability

A same-host caller sends an arbitrarily large timeline entry array; PB copies, probes, validates, and persists it, enabling application-specific memory/CPU pressure and durable timeline inflation.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if request-body/entry-count/storage quotas are enforced before allocation and persistence.

#### Remediation

Enforce a documented maximum timeline-entry count and request-body size in the backend schema before allocation, validation or persistence.

Tests:
- Oversized timeline arrays fail with a bounded 4xx response and do not mutate state.
- Boundary-size timelines still persist atomically.

Preventive controls:
- Keep collection and body-size limits in shared API policy and generated contracts.

<a id="finding-14"></a>

### [14] VRAM resource limits can be changed without the launcher owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Uncontrolled resource consumption |
| CWE | CWE-306, CWE-400 |
| Affected lines | backend/routers/health_router.py:77-84, backend/owner_capability.py:12-23, backend/routers/health_router.py:100-103 |

#### Summary

VRAM resource limits can be changed without the launcher owner capability

#### Root Cause

POST /health/vram/limit accepts a request body and directly calls VRAMBudgetManager.update_max_vram. The route has no capability header or authorization dependency. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Source evidence** — `backend/routers/health_router.py:77-84`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/vram/limit",
    response_model=VramLimitResponse,
    summary="Dynamisches VRAM-Limit aktualisieren",
)
async def update_vram_limit(
    payload: VramLimitRequest,
) -> dict[str, Any]:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/health_router.py:100-103`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        manager = get_vram_manager()
        manager.update_max_vram(payload.limit_mb)
        stats = manager.get_stats()
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Source evidence** — `backend/routers/health_router.py:77-84`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/vram/limit",
    response_model=VramLimitResponse,
    summary="Dynamisches VRAM-Limit aktualisieren",
)
async def update_vram_limit(
    payload: VramLimitRequest,
) -> dict[str, Any]:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/health_router.py:100-103`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        manager = get_vram_manager()
        manager.update_max_vram(payload.limit_mb)
        stats = manager.get_stats()
```

Evidence:
- Independent static trace confirmed in the immutable target: POST /health/vram/limit accepts a request body and directly calls VRAMBudgetManager.update_max_vram. The route has no capability header or authorization dependency.
- Cited target-commit ranges re-read: backend/routers/health_router.py:77-84 \[source\]; backend/owner_capability.py:12-23 \[root_control\]; backend/routers/health_router.py:100-103 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: source backend/routers/health_router.py:77-84 -\> root_control backend/owner_capability.py:12-23 -\> sink backend/routers/health_router.py:100-103. Effect: POST /health/vram/limit accepts a request body and directly calls VRAMBudgetManager.update_max_vram. The route has no capability header or authorization dependency.

**Source evidence** — `backend/routers/health_router.py:77-84`

This range is the source in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post(
    "/vram/limit",
    response_model=VramLimitResponse,
    summary="Dynamisches VRAM-Limit aktualisieren",
)
async def update_vram_limit(
    payload: VramLimitRequest,
) -> dict[str, Any]:
```

**Root Control evidence** — `backend/owner_capability.py:12-23`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
OWNER_CAPABILITY_HEADER = "X-PBStudio-Owner-Capability"
_OWNER_CAPABILITY = os.environ.pop(OWNER_CAPABILITY_ENV, None)


def authorize_owner(owner_capability: str | None, *, operation: str) -> str:
    """Validate the launcher-provisioned capability and return its stable owner id."""
    expected = _OWNER_CAPABILITY
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{operation} ist ohne Owner-Capability deaktiviert",
        )
```

**Sink evidence** — `backend/routers/health_router.py:100-103`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
try:
        manager = get_vram_manager()
        manager.update_max_vram(payload.limit_mb)
        stats = manager.get_stats()
```

#### Reachability

A same-host caller POSTs an arbitrary VRAM limit; the health router directly changes the process-wide resource budget and can destabilize model workloads.

#### Severity

**Low** — Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if the route becomes owner-authenticated, read-only, or clamps caller changes to a non-disruptive policy controlled by the desktop owner.

#### Remediation

Add the missing control at the cited root boundary and prove the attacker-controlled value cannot reach the protected sink.

Tests:
- A focused negative test exercises the cited attacker path.
- A positive test preserves the supported workflow.

Preventive controls:
- Keep the control centralized and fail closed.

<a id="finding-15"></a>

### [15] Loopback client can delete an audio clip without an owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Missing authorization |
| CWE | CWE-862 |
| Affected lines | backend/routers/audio_router.py:476-486, backend/main.py:617-626, backend/routers/audio_router.py:486 |

#### Summary

Loopback client can delete an audio clip without an owner capability

#### Root Cause

The audio DELETE route is mounted without a global authorization dependency and directly calls state.delete_audio_clip. In the same application, /shutdown explicitly requires and verifies OWNER_CAPABILITY_HEADER, showing that an owner capability exists but is not enforced here. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/audio_router.py:476-486`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Audio-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Audio-Clip aus In-Memory + SQLite."""
    if state.delete_audio_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:486`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(clip_id):
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/audio_router.py:476-486`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Audio-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Audio-Clip aus In-Memory + SQLite."""
    if state.delete_audio_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:486`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(clip_id):
```

Evidence:
- Independent static trace confirmed in the immutable target: The audio DELETE route is mounted without a global authorization dependency and directly calls state.delete_audio_clip. In the same application, /shutdown explicitly requires and verifies OWNER_CAPABILITY_HEADER, showing that an owner capability exists but is not enforced here.
- Cited target-commit ranges re-read: backend/routers/audio_router.py:476-486 \[entrypoint\]; backend/main.py:617-626 \[root_control\]; backend/routers/audio_router.py:486-486 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/audio_router.py:476-486 -\> root_control backend/main.py:617-626 -\> sink backend/routers/audio_router.py:486-486. Effect: The audio DELETE route is mounted without a global authorization dependency and directly calls state.delete_audio_clip. In the same application, /shutdown explicitly requires and verifies OWNER_CAPABILITY_HEADER, showing that an owner capability exists but is not enforced here.

**Entrypoint evidence** — `backend/routers/audio_router.py:476-486`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Audio-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Audio-Clip aus In-Memory + SQLite."""
    if state.delete_audio_clip(clip_id):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/audio_router.py:486`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_audio_clip(clip_id):
```

#### Reachability

A same-host caller supplies one audio clip ID; the route durably removes that active-project clip state without per-launch owner authorization.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if deletion requires per-launch owner authentication or an action-bound confirmation.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-16"></a>

### [16] Loopback client can batch-delete video and vector state without an owner capability

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Missing authorization |
| CWE | CWE-862 |
| Affected lines | backend/routers/video_router.py:693-706, backend/main.py:617-626, backend/routers/video_router.py:706 |

#### Summary

Loopback client can batch-delete video and vector state without an owner capability

#### Root Cause

The caller controls clip_ids and the unauthenticated batch endpoint invokes state.delete_video_clip for every id. No router/global authorization dependency is installed. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/video_router.py:693-706`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Video-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Video-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_video_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:706`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(cid):
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/video_router.py:693-706`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Video-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Video-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_video_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:706`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(cid):
```

Evidence:
- Independent static trace confirmed in the immutable target: The caller controls clip_ids and the unauthenticated batch endpoint invokes state.delete_video_clip for every id. No router/global authorization dependency is installed.
- Cited target-commit ranges re-read: backend/routers/video_router.py:693-706 \[entrypoint\]; backend/main.py:617-626 \[root_control\]; backend/routers/video_router.py:706-706 \[sink\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/video_router.py:693-706 -\> root_control backend/main.py:617-626 -\> sink backend/routers/video_router.py:706-706. Effect: The caller controls clip_ids and the unauthenticated batch endpoint invokes state.delete_video_clip for every id. No router/global authorization dependency is installed.

**Entrypoint evidence** — `backend/routers/video_router.py:693-706`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Video-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Video-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_video_clip(cid):
```

**Root Control evidence** — `backend/main.py:617-626`

This range is the root_control in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
app.include_router(project_router)
app.include_router(audio_router)
app.include_router(video_router)
app.include_router(pacing_router)
app.include_router(render_router)
app.include_router(events_router)
app.include_router(brain_router)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)
```

**Sink evidence** — `backend/routers/video_router.py:706`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if state.delete_video_clip(cid):
```

#### Reachability

A same-host caller supplies multiple video clip IDs; the route durably removes catalog and related vector state for each active-project clip.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if deletion requires per-launch owner authentication or an action-bound confirmation.

#### Remediation

Require the verified launcher session capability for this endpoint through one fail-closed backend authorization dependency or middleware, and send it only after backend identity verification.

Tests:
- Missing, incorrect and replayed session capabilities are rejected before the protected read or mutation.
- The WPF client succeeds with the verified per-launch capability.

Preventive controls:
- Default-deny all non-health loopback API and SSE routes.
- Inventory protected routes in an authorization regression test.

<a id="finding-17"></a>

### [17] Full user chat prompts and assistant responses are copied verbatim into the live backend log channel

| Field | Value |
| --- | --- |
| Severity | low |
| Confidence | high |
| Confidence rationale | The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required. |
| Category | Sensitive information in logs |
| CWE | CWE-532 |
| Affected lines | backend/routers/chat_router.py:159-166, backend/routers/chat_router.py:180-182, backend/routers/chat_router.py:214-216, backend/dependencies.py:356-366 |

#### Summary

Full user chat prompts and assistant responses are copied verbatim into the live backend log channel.

#### Root Cause

The message endpoint accepts arbitrary user content, then calls publish_log with the complete user_text and final_text. publish_log places that text into a log event and broadcasts it through publish_event. Chat prompts commonly contain project paths or project content, so an additional log/SSE consumer receives material that was already available only in the originating chat stream. Closest-control assessment: Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.

**Entrypoint evidence** — `backend/routers/chat_router.py:159-166`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/message")
async def post_message(request: ChatMessageRequest) -> StreamingResponse:
    """SSE-Stream — verarbeitet eine User-Message und liefert ChatEvents."""
    # Wichtig: Agent + Resourcen sind PRO Request — sonst Lebenszyklus-Konflikte.
    from pb_studio.ai.chat_agent import ChatAgent  # lazy

    if request.history is not None:
        history = [h.model_dump() for h in request.history]
```

**Sink evidence** — `backend/routers/chat_router.py:180-182`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
await _history_store.append("user", user_text)

        await publish_log(f"User: {user_text}", level="info", source="chat.user")
```

**Sink evidence** — `backend/routers/chat_router.py:214-216`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if save_history and final_text:
                            await _history_store.append("assistant", final_text)
                        await publish_log(f"KI: {final_text}", level="info", source="chat.assistant")
```

**Concrete Implementation evidence** — `backend/dependencies.py:356-366`

This range is the concrete_implementation in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
async def publish_log(message: str, *, level: str = "info", detail: str | None = None, source: str | None = None) -> None:
    """Publiziert ein strukturiertes Log-Event für /events/log."""
    payload: dict[str, Any] = {
        "level": (level or "info").lower(),
        "message": message,
    }
    if detail:
        payload["detail"] = detail
    if source:
        payload["source"] = source
    await publish_event("log", payload)
```

#### Validation

The candidate survived compact validation as reportable with high confidence. The route or tool flow, missing closest control, and protected sink are explicit in the immutable source; no speculative chain is required.

Validation method: Bounded independent static source/control/sink validation against immutable Git commit 814d2389e3ab687253328ab844ff3498a787621f; no full runtime started.

**Entrypoint evidence** — `backend/routers/chat_router.py:159-166`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/message")
async def post_message(request: ChatMessageRequest) -> StreamingResponse:
    """SSE-Stream — verarbeitet eine User-Message und liefert ChatEvents."""
    # Wichtig: Agent + Resourcen sind PRO Request — sonst Lebenszyklus-Konflikte.
    from pb_studio.ai.chat_agent import ChatAgent  # lazy

    if request.history is not None:
        history = [h.model_dump() for h in request.history]
```

**Sink evidence** — `backend/routers/chat_router.py:180-182`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
await _history_store.append("user", user_text)

        await publish_log(f"User: {user_text}", level="info", source="chat.user")
```

**Sink evidence** — `backend/routers/chat_router.py:214-216`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if save_history and final_text:
                            await _history_store.append("assistant", final_text)
                        await publish_log(f"KI: {final_text}", level="info", source="chat.assistant")
```

**Concrete Implementation evidence** — `backend/dependencies.py:356-366`

This range is the concrete_implementation in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
async def publish_log(message: str, *, level: str = "info", detail: str | None = None, source: str | None = None) -> None:
    """Publiziert ein strukturiertes Log-Event für /events/log."""
    payload: dict[str, Any] = {
        "level": (level or "info").lower(),
        "message": message,
    }
    if detail:
        payload["detail"] = detail
    if source:
        payload["source"] = source
    await publish_event("log", payload)
```

Evidence:
- Independent static trace confirmed in the immutable target: The message endpoint accepts arbitrary user content, then calls publish_log with the complete user_text and final_text. publish_log places that text into a log event and broadcasts it through publish_event. Chat prompts commonly contain project paths or project content, so an additional log/SSE consumer receives material that was already available only in the originating chat stream.
- Cited target-commit ranges re-read: backend/routers/chat_router.py:159-166 \[entrypoint\]; backend/routers/chat_router.py:180-182 \[sink\]; backend/routers/chat_router.py:214-216 \[sink\]; backend/dependencies.py:356-366 \[concrete_implementation\]

Counterevidence and remaining uncertainty:
- Binding to 127.0.0.1 limits exposure to the host but does not authenticate other same-host processes; no route-level owner control blocks the stated effect.
- No full runtime exploit was needed for the direct static route-to-effect trace; operational impact magnitude remains environment-dependent.

#### Dataflow

Attacker/precondition: A separate same-host process can reach the default loopback API while PB Studio is running. Flow: entrypoint backend/routers/chat_router.py:159-166 -\> sink backend/routers/chat_router.py:180-182 -\> sink backend/routers/chat_router.py:214-216 -\> concrete_implementation backend/dependencies.py:356-366. Effect: The message endpoint accepts arbitrary user content, then calls publish_log with the complete user_text and final_text. publish_log places that text into a log event and broadcasts it through publish_event. Chat prompts commonly contain project paths or project content, so an additional log/SSE consumer receives material that was already available only in the originating chat stream.

**Entrypoint evidence** — `backend/routers/chat_router.py:159-166`

This range is the entrypoint in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
@router.post("/message")
async def post_message(request: ChatMessageRequest) -> StreamingResponse:
    """SSE-Stream — verarbeitet eine User-Message und liefert ChatEvents."""
    # Wichtig: Agent + Resourcen sind PRO Request — sonst Lebenszyklus-Konflikte.
    from pb_studio.ai.chat_agent import ChatAgent  # lazy

    if request.history is not None:
        history = [h.model_dump() for h in request.history]
```

**Sink evidence** — `backend/routers/chat_router.py:180-182`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
await _history_store.append("user", user_text)

        await publish_log(f"User: {user_text}", level="info", source="chat.user")
```

**Sink evidence** — `backend/routers/chat_router.py:214-216`

This range is the sink in the validated source-to-sink path and carries or fails to control the security-sensitive operation.

```python
if save_history and final_text:
                            await _history_store.append("assistant", final_text)
                        await publish_log(f"KI: {final_text}", level="info", source="chat.assistant")
```

#### Reachability

User and assistant text is copied verbatim into the broadcast log event stream; another same-host log/SSE client can observe content from a chat it did not initiate.

#### Severity

**Low** — Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression.

Ignore if chat content is redacted/minimized before all log sinks or log subscribers are authenticated to the same owner session.

#### Remediation

Stop copying prompt and response bodies into the live log stream; log only event type, bounded lengths and correlation identifiers after centralized redaction.

Tests:
- Synthetic secrets in prompts and responses never appear in SSE or file logs.
- Operational metadata remains available without message bodies.

Preventive controls:
- Apply one redaction policy to every log and SSE sink.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| Unauthenticated loopback API acts as a file-reading deputy for local video paths | Sensitive data exposure | Rejected | UNC, device, network, and reparse paths are rejected. No supported lower-integrity sandbox or cross-user caller that can reach this user-scoped loopback listener is evidenced. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| The complete process-global chat history is returned by a loopback endpoint without owner authorization | Sensitive data exposure | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Unauthenticated timeline endpoint exposes project media paths and editing metadata | Sensitive data exposure | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| The desktop trusts any loopback process returning HTTP success from /health as the PB Studio backend and can then send its owner capability to that process | Backend identity spoofing | Reported | Severity medium: Severity matrix: impact=high and likelihood=medium yields severity=medium; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| VRAM resource limits can be changed without the launcher owner capability | Uncontrolled resource consumption | Reported | Severity low: Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Brain feedback allows unauthenticated learning-state mutation | Security boundary | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Project creation is reachable without the launcher owner capability | Security boundary | Reported | Severity low: Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Project activation is reachable without the launcher owner capability | Security boundary | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Durable project save is reachable without the launcher owner capability | Security boundary | Rejected | Save has consistency controls and no request body carrying attacker state. A harmful chain would first require a separate mutation finding, which should be assessed independently rather than attributed here. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Project close and job cancellation are reachable without the launcher owner capability | Security boundary | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Current project metadata is disclosed without the launcher owner capability | Security boundary | Reported | Severity low: Severity matrix: impact=low and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can evict all eligible GPU models without an owner capability | Uncontrolled resource consumption | Rejected | Only eligible idle models with unload callbacks are evicted and failure is reported. A same-user malicious process can already consume equivalent host resources; no durable state or secret is affected. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Each unauthenticated GPU SSE connection starts an uncapped polling loop | Uncontrolled resource consumption | Rejected | Each loop sleeps five seconds and exits on disconnect; no durable state, privilege, secret, or cross-user boundary impact is shown. The same-user process can consume CPU/memory directly. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Preview rendering duration has no upper bound | Uncontrolled resource consumption | Rejected | Clip spans and per-segment 60-second timeouts constrain units of work; no durable corruption or privilege boundary is shown, and the same-user caller can consume comparable resources directly. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Timeline replacement accepts an unbounded entry collection | Uncontrolled resource consumption | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Video import accepts an unbounded path list and performs expensive work sequentially | Uncontrolled resource consumption | Rejected | Each path is policy-checked, probed, and hashed; no cross-boundary read or durable corruption is established for this unbounded-list row. The same-user process can generate equivalent I/O directly. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| A still-runnable archived model downloader enables Hugging Face remote Python code without pinning a repository revision or verifying downloaded code | Security boundary | Rejected | The file is under archive/tools-old, is not invoked by release/setup/runtime workflows, and the prerequisite already requires deliberate developer execution of obsolete tooling. This is not the shipped model-provisioning path. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Legacy vector metadata is deserialized with pickle during automatic startup migration | Security boundary | Needs follow-up | Whether the supported user-opened project workflow can deliver the required .faiss + sibling .pkl layout to automatic startup migration remains unproven. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Full user chat prompts and assistant responses are copied verbatim into the live backend log channel | Sensitive information in logs | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Project MCP configuration executes an unpinned latest npm package | Security boundary | Reported | Severity low: Severity matrix: impact=high and likelihood=low yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can batch-delete audio clips without an owner capability | Missing authorization | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can delete an audio clip without an owner capability | Missing authorization | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Destructive chat-tool approval is exposed without the backend owner capability, so a local HTTP client can approve a destructive tool call from its own chat stream | Missing authorization | Rejected | The random ID is not leaked cross-client; it is intentionally returned to the request stream that created it. Owner capability is documented for destructive lifecycle operations, while chat confirmation is an action-consent control. No extra privilege or independently protected sink is shown beyond the already separate route findings. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can replace the active project timeline without an owner capability | Missing authorization | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can batch-delete video and vector state without an owner capability | Missing authorization | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Loopback client can delete a video clip and its persisted vector state without an owner capability | Missing authorization | Reported | Severity low: Severity matrix: impact=medium and likelihood=medium yields severity=low; loopback/same-user constraints are included rather than treated as blanket suppression. Evidence: artifacts/02_discovery/candidate_ledger.jsonl |
| Python dependency vulnerability audit | Software supply chain | Needs follow-up | OSV completed the full pinned inventory and normalized 69 advisories; 27 lock upgrades and formal, exact, expiring treatment of residual non-reachable advisories remain release blockers. Evidence: artifacts/03_sca/python-sca-assessment.json, artifacts/03_sca/python-sca-gate-design.md |
| Tracked files and Git-history secret scan | Secrets | No issue found | 1,451 tracked entries and 3,965 historical entries passed; all seven seeded secret rules were detected. Evidence: artifacts/02_discovery/secret-sca.log, artifacts/03_sca/security-gate-receipts/secret-scan-receipt.json |
| NuGet dependency vulnerability audit | Software supply chain | No issue found | Both production NuGet graphs are clean and the intentionally vulnerable Newtonsoft.Json fixture was detected. Evidence: artifacts/02_discovery/nuget-sca.log, artifacts/03_sca/security-gate-receipts/nuget-sca-receipt.json |

## Open Questions And Follow Up

- Can any supported project import or legacy upgrade path place attacker-controlled vector metadata at the automatic pickle migration sink?
  - Follow-up prompt: At commit 814d2389e3ab687253328ab844ff3498a787621f, trace every supported project-open/import path to src/pb_studio/data/vector_db.py legacy pickle migration and either prove safe placement or replace pickle with a restricted format.
- Which advisories remain after the compatible Python lock refresh and exact OSV inventory gate?
  - Follow-up prompt: At commit 814d2389e3ab687253328ab844ff3498a787621f, implement the documented OSV gate, refresh the Python 3.11 CPU-only lock, and validate every residual advisory against exact package/version/aliases and expiry policy.
- Whether the supported user-opened project workflow can deliver the required .faiss + sibling .pkl layout to automatic startup migration remains unproven.
  - Follow-up prompt: Review deferred unit deferred_91913d5dbaff86fe and close its stated proof gap. Paths: src/pb_studio/data/vector_store.py. Surfaces: surface_91913d5dbaff86fe.
- The current lock has 27 upgradeable advisory instances and the existing PyPI-mode gate cannot audit the +cpu Torch distribution completely; OSV-gate repair and a refreshed lock are required.
  - Follow-up prompt: Review deferred unit deferred_python_sca_release_closure and close its stated proof gap. Paths: requirements.txt, requirements-direct.txt, .github/workflows/security.yml, scripts/security_gate.py. Surfaces: surface_python_sca.
