# Design Review: Externes Config-Hot-Reload (Spec 00025)

Datum: 2026-09-12

## Architekturentscheidungen
1. Zweistufige SHA256-Erkennung im Poller: Verhindert das Lesen unvollstaendig geschriebener Dateien waehrend eines atomaren Replaces.
2. Snapshot-Isolation: Laufende Operationen behalten ihren urspruenglichen Config-Snapshot.
3. Last-Known-Good Schutz: Ungueltiges JSON oder falsche Feldtypen belassen den vorherigen Snapshot aktiv und loggen einmalig pro Digest.
4. Key-Klassifikation: Explizite Dokumentation via KEY_CLASSIFICATION fuer live, next_job und restart_required.
