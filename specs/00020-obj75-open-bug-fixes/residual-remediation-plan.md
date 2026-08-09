# Restfehler- und Releaseplan: OBJ-75

**Quelle:** `FULLSTACK_DOUBLE_AUDIT_PB_STUDIO_2026-08-09.md`

**Status:** PLANNED / NOT RELEASE-READY

**Ziel:** Drei High-Risiken schließen, vollständige QC konvergieren und erst
danach OBJ-75 für den Release freigeben.

## Prioritäten

| Priorität | Arbeitspaket | Zone | Abhängigkeit |
|---|---|---|---|
| P0.1 | Chat-Toolaufrufe über den gesamten Stream an einen Projektkontext binden | Z-CHAT/Z-PROJECT | sequenziell wegen Projekt-Lifecycle |
| P0.2 | Projector-Training pro Projekt dauerhaft checkpointen | Z-BRAIN/Z-DATA | autorisierte UUID-Migration nach Backup/Restore-Probe |
| P0.3 | Alle Wahrheitsquellen als crash-konsistente Recovery-Generation behandeln | Z-DATA/Z-PROJECT | Recovery-ADR, Manifest, Journal und Startup-Gate |
| P1-separat | Render-Retention, Config-Reload und Chat-Tokenstream | neues Feature-Workspace | vorläufige technische Scope-Entscheidung |
| P0-QC | Full-Suite, API/SSE, echte Medien und 14-View-GUI vollständig abnehmen | Z-TESTS/QC | P0.1–P0.3 abgeschlossen |

## Phase 1 — Baseline einfrieren

1. HEAD, `git status --porcelain=v2`, Diff-Digest und Artefakt-SHA-256 erfassen;
   aktuellen Diff nach Zone inventarisieren und keine fremden Änderungen verwerfen.
2. Python `compileall`, WPF Release-Build und die bereits grünen Zonencluster
   einmal als Ausgangsbeleg speichern.
3. Für jeden P0-Fix einen roten Reproduktionstest vor der Produktänderung anlegen.
4. Eindeutiges pytest-Basetemp pro Lauf verwenden und vor/nach dem Lauf nach
   verwaisten Workspace-pytest-Prozessen suchen.
5. Vor jeder Datenmigration vollständiges Backup, reales Restore-Dry-Run und
   einen benannten Rollback-Punkt mit Hash-/Schema-Receipt erzeugen.
6. Die fünf nach dem Doppel-Audit geänderten Video-/UI-Dateien separat prüfen;
   die frühere Runde-2-PASS-Aussage gilt dafür nicht.

**Gate:** Baseline-Belege vorhanden; keine unerklärten Änderungen oder Locks.

## Phase 2 — P0.1 Chat-Projektgrenze

1. Projektkontext beim Start des SSE-Generators erfassen und validieren.
2. `project_operation()` während des vollständigen Agent-/Tool-Turns halten.
3. Tool-Dispatch nur mit derselben Projekt-Capability zulassen; bei Epochwechsel
   abbrechen und einen eindeutigen 409-/SSE-Fehler liefern.
4. History weiterhin ausschließlich unter dem initialen Projekt-Key speichern.
5. Race-Tests: Projekt A → langsamer Toolcall → Wechsel zu B; weder Mutation noch
   History darf in B landen.

**Gate:** Chat ohne Tool, bestätigter Toolcall, Abbruch und Projektwechsel bestehen.

## Phase 3 — P0.2 Projector-Checkpoint

1. **Entscheidung:** Die robuste Lösung verwendet eine autorisierte
   SQLite-/Datenmigration. Jedes Projekt erhält eine dauerhafte `project_uuid`,
   jedes Feedback eine eindeutige `event_uuid`; bestehende Zeilen werden
   deterministisch und konfliktgeprüft zurückgefüllt.
2. Vor der Migration alle betroffenen `state.db`-Dateien und das V1-NPZ sichern,
   Restore wirklich ausführen und erst nach erfolgreichem Vergleich migrieren.
3. Das Projector-Artefakt auf Formatversion 2 erweitern: Matrizen,
   Modellidentität, per-project Checkpoints, verarbeitete Event-UUIDs und Pending-
   Events gemeinsam speichern. V1 bleibt als unveränderlicher Rollback erhalten.
4. Vor dem V1→V2-Rebuild sämtliche registrierten Projekte, State-DBs, Timeline-
   Verknüpfungen und Audio-/Video-Embeddings inventarisieren. Fehlt eine Quelle,
   bleibt V1 aktiv; ein partieller globaler Rebuild ist verboten.
5. Den Rebuild aus festem Seed in stabiler `(project_uuid, event_uuid)`-Reihenfolge
   auf einer privaten Projector-Kopie ausführen. Erst das vollständig validierte
   Ergebnis darf den aktiven Snapshot ersetzen.
6. Laufendes Training liest nur noch unbestätigte Event-UUIDs. Fehlende Embeddings
   bleiben als Pending-Events erhalten und werden erneut versucht, ohne bestätigte
   Events zu wiederholen.
7. Fit und Publish serialisieren, aber Reader nicht auf in-place mutierte Matrizen
   zugreifen lassen: private Kopie trainieren, Same-volume-NPZ schreiben, flushen,
   fsyncen, wieder laden, validieren und per `os.replace` veröffentlichen. Danach
   den immutable In-Memory-Snapshot unter kurzem Lock austauschen.
8. Tests mit A/B/A-Projektwechsel, ID-Wiederverwendung, parallelen Readern,
   fehlendem Embedding, Fit-/Save-/Replace-Fehler, V1-Rollback und Prozessneustart.

**Gate:** Jede Feedback-ID wirkt höchstens einmal; Retry nach Fehler bleibt möglich.

## Phase 4 — P0.3 Atomare Recovery-Generation

1. Vor dem ADR eine vollständige Truth-Source-Matrix mit Owner, Pfad,
   Konsistenzgruppe, Klasse (`owned`, `external-reference`, `derived`), Quiesce,
   Snapshot, Restore und Validierung registrieren.
2. Recovery-ADR und Manifest umfassen mindestens globale `pb_studio.db`, alle
   Projekt-`state.db`, `project.json`, `timeline.json`, `anchors.json`,
   `chat_history.json`, Brain-DBs, `feedback_outbox.json`,
   `feedback_receipts.json`, `embeddings/`, Projector-NPZ, Main-DB/Vector-Outbox,
   FAISS-Metadaten/Index/Tombstones, Config/Settings und Stem-Marker.
3. Recovery-Control verwendet einen festen Root, der nicht aus der zu
   restaurierenden Config, Settings-Datei oder Produktdatenbank gelesen wird.
4. Writes über Projekt-Lifecycle, BrainStore-, Feedback-Outbox-, Cache-, Vector-
   und DB-Owner-Grenzen
   quieszen. SQLite-Snapshots über die Backup-API erzeugen; Datei-/Verzeichnisdaten
   anschließend in unveränderliche, hashgeprüfte Generationen schreiben.
5. Absolute Embedding-Pfade im Rahmen der autorisierten Migration auf eine
   generation-relative Auflösung umstellen und Legacy-Pfade kontrolliert migrieren.
6. Projekt-/App-eigene mutable Artefakte sichern. Externe Originalmedien und
   Renderziele als Pfad-/Hashreferenz validieren und bei Abweichung explizit als
   nicht verfügbar markieren; abgeleitete Daten dürfen invalidiert werden.
7. Pro Volume vollständig staging und verifizieren. Ein dauerhafter Recovery-
   Journalzustand protokolliert `prepared`, `publishing`, `committed` oder
   `rolling_back`; nur der `CURRENT`-Pointer bestimmt die lesbare Generation.
8. Bei Prozess- oder Systemabbruch startet die App zunächst ausschließlich den
   Recovery-Koordinator. Er führt idempotent Roll-forward oder Rollback aus und
   öffnet Produktdaten erst nach vollständiger Manifest-/Hash-/Schema-Prüfung.
9. Fehlende `.npy`, halbe Brain-Operation, Main-DB/FAISS-Mismatch, defekte Config,
   fehlende externe Medien, korrupte DB, gemischte Generation, offene Handles,
   Datenträgergrenze und Unterbrechung nach jeder Publish-Stufe reproduzieren.
10. Retention ausschließlich auf vollständig committed Generationen anwenden;
   aktive und letzte bekannte gute Generation bleiben geschützt.

**Gate:** Lookup nach Restore liefert dieselben Embeddings wie zum Backupzeitpunkt;
keine DB darf auf fehlende Dateien zeigen.

## Separater P1-Backlog — nicht Teil der OBJ-75-Phasenfolge

1. Neues Feature-Workspace für Render-Retention und `progress_percent` anlegen.
2. Config-Hot-Reload und Chat-Tokenstream als getrennte Features spezifizieren.
3. Keine dieser Arbeiten vor dem OBJ-75-Release-Gate implementieren.

**Gate:** Backlog ist registriert, beeinflusst OBJ-75-QC und Release aber nicht.

## Phase 6 — Vollständige QC

1. Alle zonierten Python-Cluster ausführen.
2. Aktuelle Collection und breite Suite einmal erfassen. Einen einzelnen
   erklärten Last-Harness-Ausreißer per Root-Cause-Korrektur, vollständigem
   Fokusvertrag und zehn Stressläufen schließen; Langsuite nicht wiederholen.
3. `dotnet test PBStudio.UI.Tests` und WPF Release-Build ausführen.
4. IRON-Scan: DirectML-Flags, keine Produktions-CUDA/NVIDIA-Pfade, AMF-only,
   Python/NumPy-Pins, `Tests/` und `PYTHONPATH=src`.
5. API-/SSE-Smokes für Projektwechsel, Chat-Tool, Audio/Video-Resume, Render-Cancel
   und Replay-Gap ausführen.
6. Echte Medien-Smokes sowie die benannten 14 Hauptviews aus `MainWindow.xaml`
   inklusive Tabwechsel, Timeline, Terminal und Settings prüfen.
7. Projector- und Recovery-Fault-Injection mit Neustart nach jeder Commit-Stufe
   ausführen; Weiterarbeit muss ohne Mischgeneration oder Datenverlust möglich sein.

**Gate:** 0 Failures, keine unerklärten Skips, keine verwaisten Prozesse, keine
offenen Critical/High-Findings.

## Phase 7 — SDD- und Releaseabschluss

1. `tasks.md`, Evidence und `qc-report.md` mit exakten Receipts aktualisieren.
2. OBJ-75-SDD-Validator für `qc-progress`, danach `qc` ausführen.
3. `.completed` erst nach vollständiger Implementationsevidence erzeugen.
4. `.qc-passed` erst nach grünem Full-/Live-/GUI-QC erzeugen.
5. Brain-Log und Hauptbericht mit finalem Releaseentscheid aktualisieren.

## Definition of Done

- Drei High-Risiken reproduzierbar geschlossen.
- Zonen-, Full-, C#-, Build-, API/SSE-, Medien- und GUI-Prüfungen grün.
- Keine IRON-Rule-Verletzung; autorisierte Migrationen besitzen Backup-, Restore-,
  Rollback- und Digestbelege.
- Jeder simulierte Crash konvergiert vor Produktöffnung zu einer validen Generation;
  die Arbeit kann am letzten bestätigten Stand fortgesetzt werden.
- SDD-Evidence digestgebunden; `.completed` und `.qc-passed` valide.
- Worktree-Zustand und verbleibende Low/Design-Risiken transparent dokumentiert.
