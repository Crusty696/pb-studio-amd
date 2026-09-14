# Design Review: Render-Retention und Fortschritt (Spec 00024)

Datum: 2026-09-12

## Architekturentscheidungen
1. Terminal-Status-Definition: Nur Jobs mit Status COMPLETED, FAILED oder CANCELLED duerfen bereinigt werden. Laufende Jobs mit aktivem Thread sind unberuehrbar.
2. UTC-Zeitstempel: Abschlusszeitpunkt completed_at wird in UTC gefuehrt. Fehlt ein Zeitstempel, bleibt der Job als Schutzmassnahme erhalten.
3. Bidirektionale Kompatibilitaet: In RenderProgress wird progress_percent als fuehrend definiert, percent synchron gehalten.
4. Idempotenz: Wiederholte Aufrufe von _cleanup_old_render_tasks fuehren zu keinem weiteren Datenverlust oder Fehlern.
