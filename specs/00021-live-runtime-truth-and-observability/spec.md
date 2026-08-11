# Spezifikation: OBJ-76 Live-Runtime-Wahrheit und Observability

**Status:** IMPLEMENTING
**Feature-Workspace:** `specs/00021-live-runtime-truth-and-observability`

## Problem

Der Laufzeitmitschnitt vom 2026-08-09 belegt einen weitgehend stabilen Betrieb,
aber keine vollständig verlässliche Analysewahrheit: 342 Videoanalysen wurden
gestartet, 341 beantwortet, davon 209 ohne KI-Tags. Beim Schließen blieb eine
Analyse unvollständig. GPU-Sensortelemetrie war wegen fehlender LHM-Trust-Anker
deaktiviert. Der Mitschnitt selbst vermischte eine alte Backend-Sitzung mit dem
aktuellen Lauf und enthielt private Pfade sowie Health-Proof-Nonces.

Das Log wurde mit Commit `3beb229` erzeugt. Der aktuelle Stand enthält danach
implementierte und fokussiert geprüfte T052/T053-Änderungen. Diese Änderungen
sind noch nicht durch denselben realen App-Ablauf verifiziert worden und dürfen
nicht erneut als offene Ursache vorausgesetzt werden.

## Evidence-Klassifikation

### Bestätigt

- 342 Videojobs gestartet, 341 mit HTTP 200 abgeschlossen, ein Job beim Shutdown
  ohne terminale Analyseantwort.
- 209 abgeschlossene Jobs speicherten 0 Tags; 132 speicherten 9 oder 10 Tags.
- LM Studio meldete Modell-Ladefehler, 5xx und Timeouts; später funktionierte
  `qwen2.5-vl-7b-instruct` wieder.
- `PBSTUDIO_LHM_MANIFEST_SHA256` fehlte im gestarteten Backendprozess.
- SigLIP-Text-ONNX war nicht verfügbar; der akzeptierte DirectML-only-Vertrag
  verbietet einen CPU-/PyTorch-Fallback.
- 340 von 342 Clips nutzten den Ein-Szenen-Fallback.
- Recovery-Snapshot, FAISS-Save, Projekt-Save und Backend-Shutdown wurden
  abgeschlossen.
- Der Capture-Monitor lief mit `SupervisorPid=0`, las bestehende Backend-Dateien
  ab Offset 0 und schrieb keinen terminalen `monitor_stopped`-Receipt.

### Bereits nach dem Log geändert

- T052/T053: gemeinsame Caption-Deadline, ehrliche Stage-Zustände,
  GPU-Lock-Cancellation, stage-aware Batch-Retry und UI-Sortierung.
- Diese Punkte gelten als implementiert und fokussiert testgrün, aber noch nicht
  als live auf dem aktuellen Build bestätigt.
- OBJ-76 Gate 1 und Gate 2 sind implementiert und fokussiert geprüft. Der
  kanonische Lauf vom 2026-08-11 band LHM manifest- und hashgebunden an die live
  ausgewählte RX 7800 XT und erzeugte einen sitzungsreinen Capture-Export.
- Der fokussierte Shutdown-Fix ist im echten Captioning-Abbruchlauf bestätigt:
  alle drei Prozesse endeten mit Exitcode 0, aktive Stages wurden dauerhaft als
  `interrupted` gespeichert und es trat kein ASGI-`No response returned` auf.
- SigLIP-Text bleibt ohne registriertes, hashpassendes DirectML-ONNX-Artefakt
  explizit unavailable; die Warnung ist pro Capability-Generation dedupliziert.
- Die reale Scene-Detection traf in zwei Durchläufen aller sechs
  deterministischen Ground-Truth-Fixtures exakt die kontinuierlichen und harten
  Schnittgrenzen; Thresholds blieben unverändert.

### Ungeklärt

- Ob die aktuellen Analysewahrheits- und Resume-Verträge im normalen realen
  Tagging-Erfolgsfall vollständig greifen.
- Warum LM Studios Engine-Protokoll-Start sowohl für das konfigurierte
  qwen3.6-VLM als auch die qwen2.5-VL-Kontrollprobe abbricht. Der korrigierte
  Lauf belegt den externen Runtime-Blocker, aber keine OOM-, ABI- oder
  Treiberursache.

## Scope

### Enthalten

- Live-Abnahme des unveränderten aktuellen T052/T053-Builds vor neuen Fixes
- explizite `completed`-, `partial`-, `failed`- und `interrupted`-Wahrheit pro
  Analysestufe und eine sichere stage-aware Wiederaufnahme
- bounded LM-Studio-Diagnose, Modell-Receipts und Quarantäne ohne Crashloop
- realer crash-sicherer Captioning-Shutdown plus fokussierte
  Cancellation-/Resume-Verträge für andere aktive Video-Stages
- kanonischer Runtime-Contract für Agent-Launcher einschließlich LHM-Trust-Anker
  und Owner-Capability
- DirectML-only Capability-Gate für SigLIP-Text
- gelabelte Scene-Detection-Stichprobe vor jeder Threshold-Änderung
- sitzungsreiner privater Rohmitschnitt und separat redigierbarer Export
- Canary- und Recovery-Gates vor einer Bestandsnachanalyse tagloser Clips

### Ausgeschlossen

- neue Python-/NuGet-Abhängigkeiten
- CUDA-, ROCm- oder CPU-Fallback innerhalb PB Studio
- ungeprüfte Änderung von Scene-Thresholds
- sofortige Massen-Nachanalyse aller aktuell 465 taglosen Clips
- SQLite-/FAISS-Schemamigration
- breite Fullsuite, solange kein gemeinsam genutzter Kernvertrag geändert wird
- Produktionsdeployment oder Push ohne eigenen Auftrag

## Objective

**OBJ-76:** PB Studio muss Analysequalität, Degradationsursache, Shutdown und
Laufzeittelemetrie im echten aktuellen Build korrekt und wiederaufnehmbar
abbilden. Diagnoselogs müssen sitzungsrein sein und sich sicher weitergeben
lassen.

## Functional Requirements

- **FR-392:** Jede Videoanalyse publiziert und persistiert pro Stage einen
  terminalen Zustand sowie Provider-, Modell-, Attempt- und Fehler-Receipt.
- **FR-393:** Wenn Caption/Tagging angefordert wurde, darf `tags=[]` nur mit
  explizitem `partial`/`unavailable`-Grund auftreten. Nicht angeforderte Stages
  beeinflussen den terminalen Gesamtstatus nicht.
- **FR-394:** Wiederaufnahme führt nur fehlende, unterbrochene oder gescheiterte
  Stages aus und überschreibt valide Embeddings, Szenen oder Motion-Daten nicht.
- **FR-395:** Shutdown blockiert neue Jobs, drainiert laufende Writes begrenzt,
  markiert nicht fertiggestellte Stages atomar als `interrupted` und startet ohne
  ASGI-`No response returned` wieder.
- **FR-396:** Modellwahl verwendet live verifizierte Capabilities. Ein
  fehlerhaftes Modell wird mit begrenztem Cooldown quarantänisiert; höchstens die
  registrierte Kandidatenzahl wird versucht.
- **FR-397:** Der Agent-Launcher übernimmt Python, FFmpeg, LHM-Hashes und
  Owner-Capability ausschließlich aus dem kanonischen Runtime-Contract.
- **FR-398:** Fehlende SigLIP-Text-Assets machen Textsemantik explizit nicht
  verfügbar. Nur manifest- und hashgebundene DirectML-ONNX-Assets dürfen die
  Capability aktivieren.
- **FR-399:** Scene-Detection-Thresholds ändern sich nur, wenn eine gelabelte
  Kurz-/Langclip-Stichprobe reproduzierbare False-Negatives belegt.
- **FR-400:** Ein Capture enthält nur die benannte Sitzung, einen echten
  Supervisor-/Prozess-Receipt, Exitcodes und einen terminalen Stop-Marker.
- **FR-401:** Der private Rohmitschnitt bleibt lokal; ein separater Export
  redigiert Secrets, Health-Proof-Nonces und private absolute Pfade.

## Operational Requirements

- **OR-355:** Der erste Live-Gate läuft auf dem unveränderten aktuellen Commit.
  Neue Fixes beginnen erst nach dokumentiertem Ergebnis dieses Gates.
- **OR-356:** Jede Fehlerklasse erhält einen eigenen, attributierbaren Patch und
  fokussierten Verify-Receipt; keine Sammeländerung über Runtime, Video und Logs.
- **OR-357:** Vor Canary- oder Bulk-Nachanalyse wird eine validierte Recovery-
  Generation erstellt; Originalmedien werden nie verändert.
- **OR-358:** Bulk-Nachanalyse benötigt nach Dry-Run einen Canary mit zehn
  repräsentativen taglosen Clips und eine explizite Go/No-Go-Auswertung.
- **OR-359:** Lokale `config.json`-Änderungen und fremde Arbeitsdateien bleiben
  erhalten und werden nicht in OBJ-76 übernommen.
- **OR-360:** Tests bleiben risikobasiert minimal. Eine breite Suite ist nur bei
  Änderung eines Shared-Core-Vertrags erforderlich.

## Test Requirements

- **TR-378:** Der aktuelle Build absolviert je einen realen Tagging-,
  Degradations-, Shutdown- und Restart/Resume-Lauf mit Commit-/Config-Fingerprint.
- **TR-379:** Fokustests beweisen Statuswahrheit, stage-aware Retry,
  Quarantäne/Cooldown und atomaren Interrupted-Commit.
- **TR-380:** Launcher-Smoke beweist gesetzte Runtime-Trust-Anker und einen
  ehrlichen LHM-Status ohne fremde Adapteridentität.
- **TR-381:** Eine gelabelte Stichprobe umfasst mindestens drei kurze
  kontinuierliche Clips und drei Clips mit bekannten Schnitten; Thresholds
  bleiben unverändert, wenn der Ist-Output zur Ground Truth passt.
- **TR-382:** Capture-Verträge beweisen Session-Offsets, Rotation, Exitcode,
  `monitor_stopped` sowie null Secret-/Nonce-/Privatpfadtreffer im Export.
- **TR-383:** Canary-Nachanalyse beweist für zehn Clips Resume ohne Verlust
  vorhandener Stage-Daten; erst danach darf ein Bulk-Lauf geplant werden.

## Success Criteria

- **SC-103:** Kein Live-Shutdown erzeugt einen ASGI-Traceback oder einen
  uneindeutigen letzten Clipzustand.
- **SC-104:** Kein tagloses Ergebnis wird als vollständig erfolgreich angezeigt
  oder persistiert.
- **SC-105:** Ein LM-Studio-Ausfall löst keinen ungebremsten Kandidaten- oder
  Clip-Crashloop aus und bleibt anhand eines Receipts erklärbar.
- **SC-106:** GPU-Telemetrie ist entweder manifestgebunden aktiv oder nennt
  Adapter und Unavailable-Grund explizit; erfundene Sensorwerte sind verboten.
- **SC-107:** Der Capture-Export enthält genau eine Sitzung, einen Abschluss und
  keine privaten Pfade, Nonces oder Credentials.
- **SC-108:** Bestandsdaten werden erst nach Recovery-Probe, Dry-Run und grünem
  Canary nachanalysiert.

## Task Range

T001–T020 planen und verifizieren OBJ-76. Umsetzung und fokussierte
Live-Verifikation laufen; offene Analyse-, Resume- und Canary-Gates verhindern
weiterhin Release-Readiness.
