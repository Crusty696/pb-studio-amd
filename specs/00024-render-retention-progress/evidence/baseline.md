# Baseline: Render-Retention und Fortschritts-Normalisierung (Spec 00024)

Datum: 2026-09-12

## Status Quo vor Refactoring
1. backend/routers/render_router.py:
   - _cleanup_old_render_tasks hatte unvollstaendige Sortierung und loeschte aelteste Tasks bei >50 ohne Pruefung von Terminal-Status oder Worker-Lebenszyklus.
   - Cancel-Flags wurden separat ueber mono-time geloescht.
2. backend/schemas/render_schemas.py:
   - RenderProgress besass percent (0..100), waehrend Queue-Objekte progress_percent nutzten.
   - Risiko von Inkonsistenzen zwischen HTTP-Payload, SSE-Events und WPF-Export-UI.

## Geaenderte Dateien
- backend/routers/render_router.py: Implementiert select_terminal_tasks_for_cleanup mit deterministischer UTC-Sortierung, Altersgrenze (30 Tage) und Mengengrenze (max 50 Jobs). Aktive/laufende/wartende Worker bleiben strikt geschuetzt.
- backend/schemas/render_schemas.py: Bidirektionale Synchronisation zwischen progress_percent und percent.
- Tests/test_render_persistence.py: 17 Regressionstests fuer Queue-Persistenz, Retention, Restart und Fortschrittssynchronisation.
