# Baseline

## Environment

- Python 3.11.9
- NumPy 1.26.4
- `PYTHONPATH=src`
- .NET target: `net9.0-windows`

## Python Pacing/Timeline/Anchor Baseline

| Receipt | Result | Duration |
|---|---:|---:|
| `baseline-python-a.xml` | 81 passed, 0 failed | 113.94 s |
| `baseline-python-b.xml` | 68 passed, 0 failed | 144.58 s |
| `baseline-python-c.xml` | 42 passed, 0 failed | 206.28 s |
| `baseline-python-d.xml` | 41 passed, 0 failed | 78.90 s |
| **Total** | **232 passed, 0 failed** | **543.70 s** |

Warnings are existing dependency deprecations and short synthetic-signal warnings. No Pacing assertion failed.

## C# UI Baseline

- Receipt: `baseline-csharp.trx`
- Result: 64 passed, 0 failed, 0 skipped
- Duration: 981 ms

## Baseline Decision

Existing regressions are green. They do not prove all 41 catalog entries: visible Director-control bounds/effectiveness, preview project isolation/interval truth, and several real-media GUI behaviors require additional focused evidence.
