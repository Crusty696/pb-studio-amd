# T021 Full-Test-Konvergenz

Datum: 2026-08-09
Runtime: Python 3.11.9, `PYTHONPATH=src`, .NET 9 Release

## Python-Gesamtsuite

```text
1383 items collected / 1 skipped during collection
1368 passed, 13 skipped, 3 failed
Duration: 1692.83 s (00:28:12)
```

Unverändertes JUnit: `pytest-full.xml`. Alle drei Fehler lagen in derselben neuen
HTTP-/Coroutine-Cancellation-Grenze:

- `test_cancel_preserves_checkpoint_and_blocks_late_worker_commit`
- `test_project_switch_cancels_a_job_without_mutating_b[audio]`
- `test_project_switch_cancels_a_job_without_mutating_b[video]`

Minimalfix: Lifecycle-Cancellation wird nur bei von FastAPI injiziertem `Request`
in HTTP 409 übersetzt. Direkte Coroutine-Aufrufe und externe Cancellation bleiben
`CancelledError`; OpenAPI bleibt unverändert.

## Gezielte Nachprüfung

```text
11 passed, 0 failed in 7.13 s
```

Umfang: exakt fehlerhafte Audio-Resume- und T410-Projektwechselverträge plus alle
Lifecycle-Verträge. Zusätzlicher OpenAPI-Snapshot-Guard: `4 passed, 0 failed`.
Dieser Nachlauf schloss die Regressionen vor dem finalen Gesamtgate.

## Finaler Python-Gesamtlauf

```text
1383 items collected / 1 skipped during collection
1371 passed, 13 skipped, 0 failed
Duration: 1299.09 s (00:21:39)
```

Unverändertes grünes JUnit: `pytest-full-final.xml`.

## Native C#-Tests

```text
54 passed, 0 failed, 0 skipped
```

Unverändertes TRX: `dotnet-full.trx`.

## WPF Release-Build

```text
Build succeeded
0 warnings, 0 errors
```

## Ergebnis

PASS. Vollständige Baseline, gezielte Reparatur und vollständiger Post-fix-Lauf
sind getrennt und maschinenlesbar belegt.
