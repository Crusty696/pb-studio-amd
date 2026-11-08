# QC Report: Chat-Token-Deltas

## Ergebnis

PASS — fokussierte QC am 2026-09-24.

## Verifikation

- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest Tests\test_chat_agent.py Tests\test_chat_router.py -q`
- Ergebnis im sequenziellen Featurelauf: 28/28 Tests bestanden.
- LM Studio live: Modell `qwen3-4b-computer-science`, REST-Antwort `PB_STUDIO_LM_OK`.
- Vollsuite: 1855 passed, 12 skipped, 0 failed.

## Restbefund

Modellqualität bleibt abhängig vom lokal geladenen Modell.
