# T358 Local Security Review

Status: CONFIRMED
Date: 2026-07-30
Scope: T340–T357 working-tree diff plus directly supporting model-management and runtime-trust code

## Findings and closure

1. **HIGH — Unprotected model mutations**
   - Finding: Pull, delete, activation, mode changes, and GPU model tests were callable by any loopback client; pull accepted arbitrary IDs with an unbounded timeout and delete accepted arbitrary Ollama IDs.
   - Closed: All five routes require `X-PBStudio-Owner-Capability`; WPF forwards the launcher capability. Pull accepts only a live registry-verified Ollama candidate with bounded timeouts/no redirects. Delete accepts only one exact installed Ollama ID.

2. **HIGH — Receipt/client provider mismatch**
   - Finding: Chat inferred provider identity from URL substrings, so custom base URLs could execute a receipt against the wrong HTTP provider.
   - Closed: `ChatAgent` stores provider identity explicitly, creates clients from `receipt.provider`, and tracks exclusions as canonical `(provider, model_id)` pairs. URL heuristics were removed.

3. **HIGH — Ambiguous fuzzy model identity**
   - Finding: Namespace/tag aliases could attach capabilities or activation to the wrong model when multiple IDs collided.
   - Closed: Capability joins prefer exact IDs and accept a legacy alias only when unique. Explicit/persisted receipt selection and activation fail closed on ambiguity; explicit missing/incompatible IDs no longer fall through to another model.

4. **MEDIUM — User-writable CLI execution**
   - Finding: Every inventory refresh executed `%USERPROFILE%\.lmstudio\bin\lms.exe` based only on file existence.
   - Closed: CLI execution was removed. LM Studio loaded state now comes from the supported native `/api/v0/models` HTTP inventory and its explicit `state=loaded` field.

5. **MEDIUM — Non-atomic configuration and reflected internals**
   - Finding: Direct unlocked writes could truncate `config.json`, save errors were swallowed, and provider/GPU exceptions could expose internal URLs, paths, or stderr to API/UI.
   - Closed: `ConfigManager` uses a process lock, same-directory temporary file, flush/fsync, and `os.replace`; failures propagate and temporary files are cleaned. Provider base URLs are credential/query-redacted and public errors are stable bounded summaries; full details remain in backend logs.

## Confirmed safe areas

- LHM bundle containment, regular-file checks, manifest/main/dependency SHA-256 validation, and in-memory assembly loading are fail-closed.
- The central DXGI/DirectML adapter resolver rejects software/non-AMD adapters and integrated-device selection when a discrete AMD adapter exists.
- Ollama manifest verification uses a fixed HTTPS registry origin and disabled redirects.

## Static verification

```text
.venv\Scripts\python.exe -m py_compile <all T358 Python changes and T357 tests>
PASS

Forbidden-pattern scan:
timeout=None | create_subprocess_exec | lms.exe |
URL-substring provider inference | reflected error=str(exc)
PASS (no matches in reviewed paths)

git diff --check
PASS (line-ending conversion notices only)
```

No pytest, dotnet build, GUI run, hardware probe, or external security scan was executed.
