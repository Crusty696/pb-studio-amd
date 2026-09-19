# Plan: AI Models and Chat Functional Completion

## Instructions Check

- DirectML-only neural inference, bounded local providers, runtime-truth decision, Windows paths, WPF MVVM, project isolation, and existing provider APIs remain authoritative.
- No provider/model mutation, dependency change, migration, test, build, GUI run, or live probe is performed during this implementation phase.
- Work remains sequential across model registry/provider surfaces and chat lifecycle because both share selection and runtime status.

## Implementation

1. Catalog the active MODELLE and CHAT paths from XAML through ViewModels, ApiClient, routers, registry/client, chat agent, tool registry, SSE, history, and config persistence.
2. Audit model inventory/state distinctions, task preferences/overrides, capability filters, selection/fallback receipts, and every model mutation lifecycle.
3. Audit chat send/stream/cancel/clear, event ordering, history bounds, error classification, model/provider fallback, status publication, and project transitions.
4. Audit every registered chat tool against its schema, backend endpoint, argument translation, timeout class, and error publication.
5. Implement only proven active-path defects and record them without claiming runtime success.
6. Report the completed fix set to the user and leave all verification/QC tasks pending until explicitly authorized.

## Deferred Verification

- Python/C# regression suites and compile/build checks.
- Live LM Studio/Ollama inventory and selection probes.
- Tool-call API runs and cancellation/restart scenarios.
- MODELLE/CHAT GUI validation.
- Completion/QC markers.
