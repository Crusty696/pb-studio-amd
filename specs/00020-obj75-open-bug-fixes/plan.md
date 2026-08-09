# Plan: OBJ-75 belegte Restfehler

**Status:** PLANNED
**Spec:** `specs/00020-obj75-open-bug-fixes/spec.md`

## Entscheidungen

- Die korrekte ffprobe-Dauer ist die Obergrenze für sichtbare Video-Frames und
  publizierte Segmentdauer; OpenCV-Paket-/Framezählung bleibt nur Hilfswert.
- Einzelne unlesbare Samples werden begrenzt ersetzt oder verworfen; eine
  leere Samplemenge bleibt Fehler.
- Der bestehende vollständige Stem-Marker wird harte Erfolgsbedingung.
- Router-/UI-Ereignisse werden korreliert. Der Nutzer hat die zuvor LOCKED
  Separator-Grenze mit „weiter“ für den eng begrenzten Resume-Fix freigegeben.
- Das frühere Nutzer-Testverbot ist aufgehoben. Tests, Builds, API/SSE-, Medien-,
  GUI- und QC-Läufe sind vollständig freigegeben.
- Zwei getrennte Auditdurchgänge sind Pflicht. Runde 2 prüft den reparierten
  Stand unabhängig und darf Runde-1-PASS-Aussagen nicht übernehmen.
- CRITICAL/HIGH-Fixes werden gegen Primärquellen und lokale Reproduktionen
  bewertet; bestehende Architekturentscheidungen werden nicht blind geändert.
- Der Nutzer hat notwendige SQLite-/Datenmigrationen und vollständige QC
  freigegeben. Migrationen starten erst nach Backup, Restore-Probe und
  dokumentiertem Rollback-Punkt.
- Chat-Toolrequests tragen eine serverprüfbare Projektidentität; ein
  `project_operation()`-Scope allein reicht für Loopback-HTTP nicht aus.
- Projector-V2 verwendet stabile Projekt-/Event-UUIDs, Copy-on-write-Training und
  ein atomar publiziertes Artefakt aus Matrizen, Checkpoint und Pending-Events.
- Produktweite Recovery ist logisch atomar: unveränderliche Generationen,
  validierte Manifeste, ein dauerhafter Commit-/Restore-Journalzustand und ein
  atomarer `CURRENT`-Pointer. Bei mehreren Volumes stellt Startup-Recovery den
  Abschluss oder Rollback vor dem Öffnen von Produktdaten sicher.
- Recovery-Control liegt an einem festen, nicht aus `config.json` oder
  `settings.json` abgeleiteten Root. Jede Truth-Source wird vor Implementierung
  als `owned`, `external-reference` oder `derived` klassifiziert.
- App-/projekteigene mutable Daten werden generationsgebunden gesichert. Externe
  Originalmedien werden per Pfad/Hash validiert und bei Abweichung als nicht
  verfügbar gemeldet, nicht stillschweigend kopiert oder als gültig restauriert.
- Der Baseline-Receipt bindet HEAD, Porcelain-Status, Diff-Digest und Artefakt-
  Hashes. Die fünf nach dem Doppel-Audit geänderten Video-/UI-Dateien werden
  gesondert geprüft; alte PASS-Aussagen gelten dafür nicht.
- Render-Retention, Config-Hot-Reload und Chat-Tokenstream werden nach OBJ-75 in
  einem separaten Feature-Workspace geplant. Dies ist eine reversible technische
  Scope-Entscheidung, keine bestätigte Nutzerpriorisierung.

## Reihenfolge

1. Read-only Inventar und Root-Cause-Evidenz abschließen.
2. Video-Sampling und Zeitmetadaten in Z-VIDEO reparieren.
3. Stem-Erfolg und terminale Korrelation in Z-AUDIO reparieren.
4. Notwendige UI-Filterung in Z-UI-VM/Z-UI-SERVICES verdrahten.
5. Pacing-Regler und unabhängigen Fehlerfallback in Z-PACING reparieren.
6. Mood-Tag-Kanonisierung in Z-BRAIN reparieren.
7. Source-/modellgebundenes per-Stem-Resume in Z-AUDIO implementieren.
8. Runde-1-Findings zoniert reparieren und fokussiert verifizieren.
9. Eine breite Python-Gesamtsuite, C#-Tests, WPF Release und lokale Runtime-
   Smokes ausführen; einzelne Last-Harness-Ausreißer per Root Cause, vollständigem
   Fokusvertrag und zehn Stressläufen schließen, ohne den Langlauf zu wiederholen.
10. Vollständigen zweiten zonierten Audit durchführen und Restbefunde erfassen.
11. Baseline-Manifest und vollständige Truth-Source-Matrix registrieren; spätere
    Video-/UI-Änderungen gesondert nachauditieren.
12. Chat-/Tool-Projektgrenze mit rotem Race-Vertrag, Projekt-Capability und
    typisiertem SSE-Abbruch schließen.
13. Vor Projector-Migration alle betroffenen DBs und V1-Artefakte sichern und
    einen realen Restore-Dry-Run ausführen.
14. Stabile Projekt-/Event-UUIDs migrieren; anschließend Projector-V2 als
    Copy-on-write-Snapshot mit atomarem Publish und V1-Rollback implementieren.
15. Recovery-ADR, fester Control-Root und Manifest-Schema registrieren.
16. Snapshot-/Restore-Koordinator mit immutable Generationen, relativierbaren
    Embedding-Pfaden, Commit-Journal und Startup-Recovery implementieren.
17. Adapter für Chat-History, Brain-Outbox/Receipts, Main-DB/FAISS, Config,
    Settings, Stem-Marker sowie externe Medien-/Outputreferenzen integrieren.
18. Fault-Injection für jede Publish-Stufe sowie fokussierte Chat-, Projector-
    und Recovery-Verträge ausführen.
19. Aktuelle Testzahl aus der breiten Suite neu sammeln; danach nur geänderte
    Risikokorridore, C#-Tests, WPF Release, API/SSE, reale Medien und alle 14
    Hauptviews abnehmen. Bereits grüne Langläufe und Live-Smokes nicht wiederholen.
20. Doppel-Audit-Bericht, SDD-Evidence, Marker und Brain-Status synchronisieren.

## Risiken

- VFR-Seeking kann gleiche Frames liefern; tatsächliche Samples müssen
  dedupliziert werden.
- `asyncio.to_thread` ist nicht hart abbrechbar; Router müssen späte Events
  logisch sperren.
- Partielle Stem-Dateien sind ohne Separator-Callback nicht sicher adoptierbar.
- Ein HTTP-409 ist nach dem Start eines SSE-Responses nicht mehr möglich;
  Kontextfehler brauchen einen eigenen Stream-Vertrag.
- `INTEGER PRIMARY KEY` ohne dauerhafte UUID ist nach Löschung keine ausreichende
  Exactly-once-Identität.
- In-place-SGD kann parallelen Readern einen halbfertigen Modellzustand zeigen;
  Training muss auf einer privaten Kopie erfolgen.
- Eine atomare Dateisystemoperation kann nicht mehrere Dateien, Verzeichnisse und
  Volumes gemeinsam committen. Logische Atomizität benötigt Pointer plus Journal.
- Absolute Embedding-Pfade erschweren Generation-Swaps und müssen während der
  autorisierten Migration auf generation-relative Auflösung umgestellt werden.
- V1-Rebuild und Restore sind ohne geprüftes Archiv/Rollback one-way doors.
- `chat_history.json`, Brain-Outbox/Receipts, WPF-Settings und Stem-Marker liegen
  außerhalb der bisherigen Manifestliste; DB-only-Restore erzeugt Mischzustände.
- `config.json` bestimmt selbst den Main-DB-Pfad. Der Recovery-Control-Root darf
  daher nicht erst nach erfolgreichem Config-Laden auflösbar sein.
- Main-DB-`vector_map` und FAISS besitzen getrennte Writer/Journale; T042 muss
  sowohl `storage/**` als auch die zuständigen `data/**`-Owner koordinieren.
- Die bisherige Zahl von 1.402 Tests ist nur historische Größenordnung. Aktuelle
  Collection und benannte 14-View-Matrix sind neue QC-Receipts.

## Verifikation

Rote Reproduktion vor jedem Rest-High-Fix; danach Fokustests pro disjunkter Zone.
Projector- und Recovery-Abnahme enthält Parallel-Reader, A/B/A, ID-Reuse,
Save-/Replace-Fehler, Prozessabbruch und Power-loss-nahe Fault-Injection.
Anschließend folgen breite Bestandsaufnahme, risikobasierte Delta-, Native-,
Release-, API/SSE-, Medien-, 14-View-GUI- und SDD-Verifikation. Jeder Lauf speichert Befehl,
Umgebung, stdout/stderr,
Exitcode, Laufzeit und Digest unter `specs/00020-obj75-open-bug-fixes/evidence/`.
