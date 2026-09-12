# Requirements Matrix: Render-Retention (Spec 00024)

| Anforderung | Beschreibung | Implementierung | Test | Status |
|---|---|---|---|---|
| FR-001 | 30 Tage & 50 Jobs Alters-/Mengengrenze fuer terminale Jobs | backend/routers/render_router.py | test_select_terminal_retention_rules | VERIFIED |
| FR-002 | Idempotenter Cleanup & Queue/Memory-Paritaet | backend/routers/render_router.py | test_render_queue_cleanup_terminal, test_cleanup_old_render_tasks_syncs_memory_and_queue | VERIFIED |
| FR-003 | Keine Loeschung geschuetzter Artefakte, Cancel-Schutz | backend/routers/render_router.py | test_running_jobs_are_requeued_on_startup | VERIFIED |
| FR-004 | progress_percent 0..100 kanonisch, percent als Alias | backend/schemas/render_schemas.py | test_render_progress_schema_bidirectional_sync | VERIFIED |
| TR-001 | UTC Wanduhr, keine neue DB-Migration | backend/routers/render_router.py | test_render_persistence.py (17 Tests) | VERIFIED |
