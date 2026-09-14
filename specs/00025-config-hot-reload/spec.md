# Externes Config-Hot-Reload mit letztem gültigen Stand

**Status:** SPECIFIED, 2026-09-07. **Quelle:** Nutzerauftrag Punkt 13; specs/00023-backlog-completion.

## Ziel und Geltungsbereich
Den genannten Backlogpunkt vollständig im realen App-Pfad schließen. Die folgenden Designentscheidungen sind Vorschläge dieser Spezifikation, keine behaupteten früheren Beschlüsse. Keine Implementations- oder Live-Abnahme wird hier behauptet.

## Befund
Der reale Manager ist `src/pb_studio/config_manager.py`, nicht der in älteren Aufgaben genannte `core/config.py`. Er lädt beim Singleton-Start, gibt Deep-Copies zurück und speichert atomar unter Recovery-Barriere. Ein externer Watcher fehlt. `models_router.py` liest Task-/Provider-Overrides, `video_router.py` liest `ai.default_mode`. `settings.json` besitzt eigene Verbraucher und ist keine Aliasdatei für `config.json`.
## Anforderungen
- FR-001: Änderungen der bestehenden externen `config.json` werden bei laufender App spätestens 3 Sekunden nach stabilem gültigem Inhalt erkannt; atomarer Replace und gleiche Dateigröße funktionieren.
- FR-002: Vollständiges JSON-Objekt und unterstützte Key-Typen vor Publish validieren. Ungültiger/fehlender/halb geschriebener Inhalt lässt den letzten gültigen Snapshot aktiv, verändert die Datei nicht und meldet einmal pro Fehlerversion die Ablehnung.
- FR-003: Revision und Diff publizieren erst nach atomarem Snapshotwechsel. Eigene Saves erzeugen keine Schleife; externe Änderungen und UI-Saves dürfen nicht still gegenseitig überschrieben werden.
- FR-004: Explizite Consumer-Matrix vor Implementation: mindestens `ai.task_overrides`, `ai.task_provider_overrides`, `ai.default_mode` wirken auf den nächsten Auftrag. Caches dieser Verbraucher werden invalidiert. Laufende Jobs behalten ihren ursprünglichen Snapshot.
- FR-005: Für sämtliche übrigen tatsächlich gelesenen Keys ist `live`, `next_job` oder `restart_required` im Status dokumentiert. DB-/Recovery-Pfade, GPU-Provider und Modellruntime wechseln niemals in laufenden Jobs. Unbekannte Keys erzeugen keine behauptete Live-Wirkung.
- TR-001: Ein lifecycle-gebundener Poller ohne neue Paketabhängigkeit; Start genau einmal, sauberes Stop/Join. Recovery-Restore und Save koordinieren Snapshot-/Dateizugriff.
## Abnahme
Echter externer Datei-Replace ändert den nächsten Modell-/Modus-Auftrag sichtbar. Ungültiger JSON- und Typfall bleiben last-good. Race-Test Save/Reload, Restart-required-Anzeige, Recovery und sauberer Shutdown; Originalkonfiguration nach Liveprobe identisch wiederherstellen.

## Gates
Getrenntes Feature gemäß specs/00020-obj75-open-bug-fixes/residual-remediation-plan.md. Dessen OBJ-75-Release-Vorbedingung vor Implementierung anhand aktueller Marker prüfen; fehlendes Gate explizit beim Parent behandeln. Spec → Plan → Tasks → Implement → QC. Keine .completed/.qc-passed ohne reale Belege. Python 3.11/NumPy 1.26.4, DirectML/AMF und bestehende Recovery-Grenzen gelten.
