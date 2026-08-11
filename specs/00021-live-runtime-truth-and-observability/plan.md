# Plan: OBJ-76 Live-Runtime-Wahrheit und Observability

**Status:** ACTIVE
**Spec:** `specs/00021-live-runtime-truth-and-observability/spec.md`
**Ausgangslog:** `logs/pb_studio_full_20260809_123722.log`

## Leitentscheidungen

- Das alte Log ist Reproduktionsbeleg, aber kein Beweis gegen den aktuellen
  Stand. T052/T053 werden zuerst auf dem unveränderten aktuellen Build live
  geprüft.
- HTTP 200 bedeutet Transporterfolg, nicht vollständige Analyse. Stage-Status
  und Degradationsgrund sind die Produktwahrheit.
- Externe LM-Studio-Engine-Crashes werden anhand echter Engine-/CLI-Logs
  diagnostiziert. Exitcodes werden nicht aus PB-Studio-Logs heraus gedeutet.
- Kein CPU-, CUDA- oder ROCm-Fallback wird in PB Studio ergänzt. Fehlende
  DirectML-Assets deaktivieren die Capability sichtbar.
- Scene-Fallbacks sind ohne Ground Truth kein bestätigter Defekt.
- Rohlogs und teilbare Logs erfüllen unterschiedliche Zwecke: privat vollständig,
  Export strikt redigiert.
- Bestandsnachanalyse ist eine Datenmutation und folgt Recovery → Dry-Run →
  Canary → Go/No-Go. Sie ist nicht Teil der ersten Reparaturwelle.

## Gate 0 — Unveränderten aktuellen Stand beweisen

1. Aktuellen Commit, Dirty-State und `config.json`-Fingerprint erfassen.
2. WPF Release aus dem aktuellen Commit bauen; keine Produktdatei ändern.
3. Backend über `scripts/runtime_contract.ps1 -ApplyEnvironment` und den
   bestehenden Owner-Capability-Pfad starten, nicht über den unvollständigen
   Agent-Driver.
4. Mit bestehenden Medien vier getrennte Live-Proben ausführen:
   - normaler VLM-Tagging-Erfolg,
   - erzwungene Provider-Degradation ohne Datenverlust,
   - Schließen während einer laufenden Analyse,
   - Neustart und stage-aware Resume desselben Clips.
5. Ergebnisentscheidung:
   - PASS: T052/T053 bleiben geschlossen; keine erneute Codeänderung.
   - FAIL: nur der reproduzierte Restfehler geht in Gate 3 oder 4.

**Abnahme:** Commit-/Config-Fingerprint, API-/SSE-Receipt, persistierter
Stage-Zustand und Neustartnachweis. Kein ASGI-Traceback.

## Gate 1 — Launcher und GPU-Telemetrie kanonisieren

**Stand 2026-08-11:** implementiert und fokussiert geprüft. Der Live-Lauf
meldete manifestgebundene LHM-Sensoren für dieselbe live ausgewählte RX 7800 XT;
der frühere fehlende Trust-Anker ist damit für den aktuellen Lauf aufgelöst.
Ein später eigenständig gestarteter `health`-Befehl prüft den öffentlichen
Status, überspringt aber geschützte Probes ehrlich, wenn diese Driver-Sitzung
den bereits laufenden Backendprozess nicht besitzt.

1. `.agents/skills/run-pb-studio/driver.ps1` vor jedem Start den bestehenden
   `Get-PBStudioRuntimeContract -ApplyEnvironment` aufrufen lassen.
2. Owner-Capability über `scripts/owner_capability.ps1` pro Session beziehen und
   nur an Kindprozesse weiterreichen; Wert nie loggen.
3. Driver-`check` um Runtime-/Manifest-Hash, Python 3.11, NumPy 1.26.4,
   DirectML-Provider und FFmpeg-AMF-Vertrag erweitern.
4. `/gpu/status` muss ausgewählten DXGI-Adapter, LHM-Vertrauensstatus und einen
   konkreten Unavailable-Grund liefern. Fehlende physische Sensoren bleiben
   ehrlich unavailable.

**Abnahme:** Kein `PBSTUDIO_LHM_MANIFEST_SHA256 fehlt` im frischen Lauf; keine
fremde GPU-Identität; kein Secret im Launcher-Log.

## Gate 2 — Diagnosemitschnitt reparieren

1. Capture-Skript aus dem ignorierten `logs/`-Bereich als versioniertes
   Diagnosewerkzeug unter `scripts/diagnostics/` registrieren.
2. Vorhandene Quellen mit ihrem Startoffset erfassen. Nur explizit neue,
   sitzungseigene Dateien beginnen bei Offset 0.
3. `SupervisorPid=0` verbieten; zusätzlich WPF-/Backend-PID, Startzeit, Exitcode,
   monotone Sequenz, Drop-Zähler und Commit erfassen.
4. Rotation als neue Source-Generation behandeln, ohne Altinhalt einer früheren
   Sitzung zu übernehmen.
5. `try/finally` garantiert einen terminalen `monitor_stopped`-Receipt.
6. Zwei Ausgaben erzeugen:
   - lokales Raw-Log mit restriktivem Verwendungszweck,
   - sanitisiertes Export-Log mit Redaction für Credentials, Owner-Capability,
     Health-Proof-Nonces und private absolute Pfade.

**Abnahme:** Ein Start-/Stop-Smoke enthält genau eine Sitzung. Der Export hat
null Treffer für definierte Secret-, Nonce- und Benutzerpfad-Muster.

## Gate 3 — LM-Studio- und Analysewahrheit

**Stand 2026-08-11:** Der autoritative r4-Lauf belegt erfolgreichen Load und
SSE-Transport für qwen3.6 (kalt plus zwei warm) sowie qwen2.5-VL (Kontrolle).
qwen3.6 verbrauchte jedoch jeweils das vollständige 64-Token-Budget, ohne dass
der Diagnosevertrag finalen Tag-Inhalt belegte. Der reale PB-Studio-Lauf endete
nach drei bounded Kandidaten ohne Tags; T009 ist abgeschlossen, T003 bleibt bis
zum nutzbaren App-Tag-Commit und echten Restart/Resume offen.

Das 64-Token-Limit gehört nur zum Diagnose-Request. PB Studio setzt dieses
Limit im Produktaufruf nicht; daher wird vor jeder Video-Codeänderung zuerst der
isolierte reale App-Lauf wiederholt.

Der isolierte Wiederholungslauf ist zusätzlich durch einen externen Dienst
gesperrt: Hermes Research lädt sein 14,27-GB-Modell per Watchdog alle zehn
Sekunden erneut. Dieser fremde Dienst wird nur nach eigener Freigabe kurz
pausiert und danach exakt wiederhergestellt; OBJ-76 stoppt ihn nicht implizit.

1. Vor einer Codeänderung LM Studio mit offiziellen Werkzeugen beobachten:
   `lms ps`, `lms log stream --source server --json` und ein expliziter Load-
   Smoke des bevorzugten VLM. Offizielle JIT-/Load-Ereignisse liefern die
   Runtime-Wahrheit; PB Studio speichert nur korrelierte Receipts.
2. Bevorzugtes Video-Captioning-Modell explizit laden, einmal kalt und zweimal
   warm mit identischem Input prüfen und danach kontrolliert entladen. Context,
   Load-Time, TTFT, Engine, Exitcode und VRAM-Zustand erfassen.
3. Nur bestätigte App-Lücken ändern:
   - terminaler Stage-Status `completed|partial|failed|interrupted`,
   - Provider-/Modell-/Attempt-/Deadline-Receipt,
   - begrenzte Quarantäne mit Ablauf,
   - kein generisches `completed`, wenn eine angeforderte Tagging-Stage fehlt.
4. Die UI zeigt partielle Analyse und bietet gezieltes Retry der fehlenden Stage;
   valide Szenen, Motion und Embeddings bleiben erhalten.
5. Instabile Kandidaten werden nicht dauerhaft gelöscht. Ihre erneute Zulassung
   benötigt einen erfolgreichen, bounded Live-Smoke.
6. Gesamtstatus wird ausschließlich aus angeforderten Stages abgeleitet:
   `completed` bei allen angeforderten Stages, `partial` bei mindestens einem
   validen Commit plus fehlender/gescheiterter/unterbrochener Stage und `failed`
   ohne nutzbaren Commit.

**Abnahme:** Erfolgsfall liefert Tags; Ausfallfall liefert `partial` plus Ursache;
beide Fälle enden bounded und ohne Kandidaten-Crashloop.

Quellen: [LM Studio Server Settings](https://lmstudio.ai/docs/developer/core/server/settings),
[LM Studio Model Loading](https://lmstudio.ai/docs/typescript/manage-models/loading),
[LM Studio CLI](https://lmstudio.ai/docs/cli).

## Gate 4 — Shutdown, Persistenz und Resume

**Stand 2026-08-11:** Der fokussierte Transport-/Intake-Fix ist implementiert.
Ein echter Shutdown während Captioning endete ohne ASGI-Traceback, mit
persistierten `interrupted`-Stages und Exitcode 0 für WPF, Supervisor und
Backend. Die gemeinsame Cancellation-/Resume-Logik ist zusätzlich fokussiert
testgrün; ein realer erfolgreicher Restart/Resume-Lauf bleibt wegen des noch
fehlenden nutzbaren App-Tag-Commits offen.

1. Einen realen Shutdown während Captioning reproduzieren und die gemeinsame
   Cancellation-/Interrupted-Logik für andere aktive Stages durch fokussierte
   Injection abdecken. Zusätzliche teure Live-Runs nur bei abweichendem Vertrag.
2. Neue Requests sperren, aktive Projekt-/GPU-/Persistenz-Leases bounded
   drainieren und danach den Recovery-Snapshot erzeugen.
3. Nicht fertiggestellte Stages vor Prozessende atomar `interrupted` markieren.
   Späte Worker-Ergebnisse dürfen diesen Zustand nicht in `completed` drehen.
4. Client-Disconnect und Server-Shutdown als erwartete Cancellation normalisieren;
   `RuntimeError: No response returned` darf nicht als ASGI-Fehler erscheinen.
5. Nach Neustart denselben Clip laden und nur die fehlende Stage fortsetzen.

**Abnahme:** Reale Captioning-Probe plus fokussierte Injection, null Tracebacks,
null halbfertige Completed-Zustände, Recovery-Snapshot valid und Resume
idempotent.

## Gate 5 — DirectML-Assets und Scene Detection

### SigLIP-Text

**Stand 2026-08-11:** Kein registriertes Text-ONNX-Artefakt vorhanden. Die
Capability bleibt fail-closed unavailable; nur manifest- und hashpassende
DirectML-Assets können sie aktivieren. Die Warnung ist pro
Capability-Generation dedupliziert.

1. Prüfen, ob ein bereits registriertes, gepinntes Text-ONNX-Artefakt existiert.
2. Falls ja: Hash, Source-Revision, Shape-Vertrag und beide DirectML-Session-Flags
   validieren, dann Capability aktivieren.
3. Falls nein: Capability bleibt unavailable; Warnung höchstens einmal pro
   Capability-Generation, keine 342-fache Wiederholung.

### Scene Detection

1. Sechs deterministische, isolierte Medien-Fixtures verwenden: drei kurze
   kontinuierliche Clips und drei Clips mit bekannten harten Schnitten.
2. Ist-Ausgabe gegen Ground Truth vergleichen.
3. Nur bei reproduzierbaren False-Negatives Thresholds ändern; andernfalls
   Ein-Szenen-Fallback als erwarteten Status behandeln und Log-Level reduzieren.

**Abnahme:** Kein verbotener Fallback; Scene-Entscheidung besitzt Ground-Truth-
Receipt statt Ableitung aus der Warnungszahl.

## Gate 6 — Canary und optionale Bestandsreparatur

**Stand 2026-08-11:** Live-Recovery-Control-Plane read-only konsistent,
Restore-Vertrag gegen eine isolierte temporäre Kopie bestanden und Dry-Run ohne
Mutation abgeschlossen. 465 taglose Videos würden Captioning wiederholen. Der
Canary bleibt ohne separates Go und ohne erfolgreichen PB-Studio-Tag-Commit
gesperrt; Bulk ist NO-GO.

1. Validierte Recovery-Generation und Restore-Probe erstellen.
2. Dry-Run inventarisiert taglose Clips und zeigt, welche Stages wiederholt
   würden; keine Datenmutation.
3. Zehn repräsentative Clips als Canary nachanalysieren, rate-limited und
   checkpointed.
4. Vorher/Nachher vergleichen: Tags, Stage-Receipts, Embedding-/Scene-/Motion-
   Hashes, Laufzeit, Providerfehler und Recovery-Fähigkeit.
5. Bulk bleibt eigenes Go/No-Go. Bei Fehlerquote, Crashloop oder unerwarteter
   Änderung valider Stages abbrechen und Canary restaurieren.

**Abnahme für späteren Bulk:** 10/10 Canaries terminal korrekt; 0 Änderungen an
bereits validen Stages; 0 ungeklärte Providerfehler; Restore-Probe grün.

## Minimale Verifikation

1. Python: nur geänderte Module kompilieren und fokussierte Verträge für
   Runtime-Contract, Status/Resume, Shutdown und Capture ausführen.
2. C#: nur betroffene Video-/Lifecycle-Verträge; WPF Release einmal nach der
   letzten UI-Änderung.
3. Live: Gate 0 sowie nach Änderungen je ein Tagging-, Degradations-, Shutdown-
   und Restart/Resume-Lauf.
4. Scene: gelabeltes 6-Clip-Korpus, kein breiter Medienlauf.
5. Recovery: eine echte Snapshot-/Restore-Probe vor Canary.
6. Fullsuite nur, falls ein Shared-Core-, DB-Schema- oder globaler API-Vertrag
   geändert wird.

## Reihenfolge und Stop-Gates

1. Gate 0 unverändert ausführen.
2. Gate 1 und Gate 2 als getrennte Infra-Patches implementieren und prüfen.
3. Gate 3 nur mit korreliertem LM-Studio-Engine-Beleg beginnen.
4. Gate 4 nur für im aktuellen Build reproduzierbare Shutdown-Restfehler ändern.
5. Gate 5 entscheidet asset- und ground-truth-basiert; keine Pflichtänderung.
6. Gate 6 bleibt gesperrt, bis Gates 0–5 und Recovery grün sind.

## Risiken und Rückweg

- **Falschpositive Altbefunde:** altes Log gegen neuen Code. Rückweg: Gate 0 vor
  jeder Änderung.
- **LM-Studio-/Prompt-SPOF:** Diagnose-Transporterfolg ohne belegten finalen
  Inhalt oder konkurrierende Modellbelegung. Rückweg: zuerst isolierter
  Produktlauf, danach nur bei reproduziertem Produktfehler minimaler Fix;
  weiterhin partial Receipt, bounded Fallback/Quarantäne und kein Bulk.
- **Shutdown hängt am nativen Worker:** bounded Drain, atomarer Interrupted-
  Zustand, danach kontrollierter Prozessabschluss.
- **LHM liefert trotz korrekter Bindung keine Sensoren:** unavailable statt
  erfundener Werte; DirectML-Adapter- und Budgetvertrag bleiben aktiv.
- **Scene-Tuning verschlechtert kurze Clips:** keine Änderung ohne gelabelten
  Vorher/Nachher-Beleg.
- **Bestandsmutation:** Recovery-Generation, Canary und Stop-Gate; keine
  Schemamigration.

Gates 0–5 sind Two-Way Doors. Die Bestandsnachanalyse in Gate 6 ist trotz
Recovery und Canary eine kontrollierte datenwirksame One-Way Door und bleibt bis
zu einem separaten Go/No-Go gesperrt.
