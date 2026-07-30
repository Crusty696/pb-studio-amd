# Freigegebener Reparaturplan 2026-07-30

## GPU-, LLM-, Modellinventar- und Analyse-Wahrheit

**Workspace:** `C:\Users\david\Documents\Pb_studio_AMD_version`  
**Feature-Workspace:** `specs/00013-system-wide-bug-hunting-audit`  
**Fortsetzung:** OBJ-71, T340–T369  
**Status:** `DECIDED` und vollständig zur autonomen Ausführung freigegeben  
**Ausgangslog:** `logs/manual_app_test_20260730_020333.log`  
**Ausgangslog SHA-256:** `086DCC6F3F7B03872AD72B90148B260E9584FACF3556E01AF2797DC193181D52`

## 1. Verbindliche Autonomiefreigabe

Der Benutzer genehmigt die vollständige Ausführung dieses Plans bis zu dem Punkt, an dem PB Studio wieder für einen realen Benutzertest bereitsteht.

Innerhalb dieses Plans sind ohne weitere Rückfrage freigegeben:

- Lesen, Erstellen und Ändern aller zur Umsetzung erforderlichen PB-Studio-Dateien.
- Die in T340 vorgesehene Invaliderung und spätere Neuerzeugung von `.completed` und `.qc-passed`.
- Änderungen an öffentlichen DTOs und Verträgen, einschließlich `IApiClient.cs`, soweit sie exakt diesem Plan entsprechen.
- Änderungen am geschützten `src/pb_studio/audio/separator.py`, soweit sie ausschließlich der zentralen DirectML-Adapterbindung aus T345 dienen.
- Sichern, Hashen und rollback-sicheres Ändern lokaler LM-Studio- und LibreHardwareMonitor-Konfigurationen.
- Download der offiziell festgelegten LibreHardwareMonitor-Version und ihrer Release-Artefakte.
- Starten und Stoppen von PB Studio, Backend, LM Studio, Ollama und planbezogenen Hilfsprozessen.
- Ausführen von Diagnosebefehlen, Builds, Tests, Hardwareprüfungen, GUI-Smokes, FFmpeg-Exporten, Secret-Scans und Remote-Diffs.
- Zonenweise Git-Commits, normale Fast-Forward-Pushes und anschließende Remote-SHA-Verifikation.
- Verwendung bestehender Administratorrechte und nicht-interaktiver Befehle.

Der ausführende Agent fordert für diese bereits freigegebenen Aktionen keine Zwischenbestätigung, keine Befehlsfreigabe und keine erneute Planfreigabe an. Er arbeitet T340–T369 autonom und fortlaufend ab.

Nicht durch diese Freigabe aufgehoben:

- Keine neue Dependency, keine Paket- oder Lockfile-Änderung.
- Keine Produktionsdatenmigration.
- Kein Force-Push und kein automatisches Rebase.
- Keine Bereinigung oder Rücksetzung fremder Änderungen.
- Keine Umgehung der AMD-/DirectML-IRON-RULES.
- Keine Erfolgsmeldung ohne gespeicherten Testbeleg.
- Bei Remote-Divergenz, unvermeidbarer Dependency-Erweiterung, nicht reproduzierbarer Root Cause oder nicht kompatiblem offiziellen LHM-Bundle wird `BLOCKED` gemeldet. Der Agent nutzt vorher alle sicheren, planinternen Alternativen.
- Ein vom Betriebssystem erzwungener interaktiver UAC-Dialog darf nicht als bestanden simuliert werden. Kann er mit vorhandenen Rechten und nicht-interaktiven Mitteln nicht vermieden werden, wird der genaue Blocker protokolliert.

## 2. Ziel und Ausgangslage

Ziele:

- Sämtliche DirectML-Workloads verwenden nachweislich die RX 7800 XT statt der iGPU.
- GPU-Erkennung, VRAM-Budget und Monitoring beziehen sich auf denselben Adapter.
- LM Studio und Ollama werden bei jedem Start neu inventarisiert.
- Angezeigt werden nur installierte oder nachweislich verfügbare Modelle, jeweils eindeutig gekennzeichnet.
- Aufgabenauswahl und Modellwechsel verwenden tatsächlich den angezeigten Provider und das angezeigte Modell.
- Nullable Video-Szenenwerte verursachen keine UI-Analysefehler mehr.
- Alle Aussagen werden durch gespeicherte Diagnose-, Test- und Full-Length-Evidenz belegt.

Ausgangsstatus:

- **CONFIRMED:** DirectML-Index 0 ist die AMD-iGPU; die RX 7800 XT ist Index 1.
- **CONFIRMED:** RX-7800-XT-LUID ist `0x00000000_0x0001185b`.
- **CONFIRMED:** VRAM-Budget und tatsächlich verwendeter GPU-Adapter widersprechen sich.
- **CONFIRMED:** LibreHardwareMonitor ist wegen fehlendem Vertrauensmanifest deaktiviert.
- **CONFIRMED:** LM Studio besitzt lokale Modelle, stellt bei deaktiviertem JIT aber kein Modell über `/v1/models` bereit.
- **CONFIRMED:** Ollama wurde tatsächlich verwendet; LM Studio nicht.
- **CONFIRMED:** Das handgeschriebene C#-DTO behandelt `SceneInfo.confidence` fälschlich als nicht-nullbar.
- **DECIDED:** LM Studio JIT wird aktiviert.
- **DECIDED:** LibreHardwareMonitor wird frisch aus der offiziellen Version 0.9.6 aufgebaut.
- **DECIDED:** Frühere `.completed`-, `.qc-passed`- und Release-Ready-Aussagen werden bis zum neuen End-QC invalidiert.
- **OPEN:** Implementierung und gespeicherte QC-Evidenz.
- **BLOCKED:** Keiner zu Planbeginn.

Geschätzte aktive Arbeitszeit: **26–52 Stunden**, zuzüglich Full-Length-Exporte. Pro neuem Export sind abhängig von Encoder und Hardware weitere **3–8 Stunden** einzuplanen.

## 3. Architektur- und Vertragsentscheidungen

### 3.1 GPU und DirectML

- Neuer Standard: `hardware.directml_adapter_policy = "highest_vram_amd"`.
- Optionaler Override: `hardware.directml_device_id`.
- Das bisherige `ai.dml_device_id` bleibt lesbar, erhält aber eine Deprecation-Warnung und hat niedrigere Priorität.
- Der Resolver enumeriert DXGI-Hardwareadapter, schließt Softwareadapter aus, bevorzugt AMD und wählt den Adapter mit dem größten dedizierten VRAM.
- Der High-Performance-LUID wird auf den von ONNX Runtime erwarteten normalen DXGI-Index abgebildet.
- Auf dem gegenwärtigen Rechner muss das Ergebnis Index `1`, LUID `0x00000000_0x0001185b`, RX 7800 XT sein.
- Falls kein AMD-DirectML-Adapter existiert, wird geschlossen abgebrochen. Eine AMD-iGPU darf nur verwendet werden, wenn keine AMD-dGPU existiert.
- Alle DirectML-Sessions verwenden denselben zentral erzeugten Provider-Tupel einschließlich `device_id`.
- Alle DirectML-Sessions setzen `enable_mem_pattern=False` und `enable_cpu_mem_arena=False`.
- Kein CUDA, ROCm, NVENC oder stiller CPU-Fallback.
- VRAM-Arbiter, Monitoring und DirectML müssen auf denselben Adapter-LUID gebunden sein.
- Ein konfiguriertes VRAM-Limit darf den physischen VRAM des ausgewählten Adapters nur reduzieren, niemals erhöhen.

### 3.2 GPU-Statusvertrag

Bestehende Felder von `/gpu/status` bleiben kompatibel. Additiv kommen hinzu:

- `adapter_index`
- `adapter_luid`
- `adapter_name`
- `dedicated_vram_total_mb`
- `directml_active`
- `monitoring_status`
- `monitoring_error`

Kann das Monitoring den DirectML-Adapter nicht eindeutig zuordnen, wird `degraded` gemeldet. Werte einer anderen GPU dürfen nicht übernommen werden.

### 3.3 LibreHardwareMonitor

- Offizielle LibreHardwareMonitor-Version 0.9.6 verwenden.
- Vor Austausch bestehendes Bundle mit Zeitstempel sichern und alle Dateien hashen.
- Offizielles Release-Asset, Download-URL, Archivhash und DLL-Hashes in einem versionierten Runtime-Manifest festhalten.
- Die neue Version wird erst aktiviert, wenn der exakte Python-3.11/pythonnet-Ladecheck erfolgreich ist.
- Bei Inkompatibilität: `BLOCKED`; bestehendes unbestätigtes Bundle nicht als Fallback freigeben.
- WPF-Launcher übergibt Manifest- und DLL-Hash an den Backendprozess.
- Restore-Probe muss die Sicherung reproduzierbar wiederherstellen.
- Keine neue Python-, NuGet- oder Lockfile-Abhängigkeit.

### 3.4 Modellinventar und Auswahl

Providerstatus:

- `offline`
- `online_empty`
- `ready`
- `degraded`

Modellstatus enthält mindestens:

- `provider`
- `installed`
- `loaded`
- `downloadable`
- `usable`
- `capabilities`
- `verified_at`
- `status_reason`

Inventarquellen:

- LM Studio installiert: `/v1/models` bei nachweislich aktivem JIT.
- LM Studio geladen: `lms ps --json`.
- Ollama installiert: `/api/tags`.
- Ollama geladen: `/api/ps`.
- Private LM-Studio-Indexdateien und das hängende `lms ls --detailed` sind keine Laufzeitabhängigkeit.
- Stale Konfigurations-IDs erscheinen nur als Warnung, niemals als installierte Modellkarte.
- Ein herunterladbares Modell wird nur angezeigt, wenn ein providerseitiger Live-Katalog- oder Manifestcheck erfolgreich ist.
- Ist für LM Studio keine offiziell unterstützte Einzelmodellprüfung verfügbar, werden keine individuellen LM-Studio-Downloadkarten behauptet; stattdessen wird nur die allgemeine Discover-Aktion angeboten.
- Bei nicht erreichbarem Katalog werden Downloadmodelle ausgeblendet und der Katalogstatus als nicht verifiziert angezeigt.

Auswahlvertrag:

- Jede Auswahl erzeugt einen `ModelSelectionReceipt` mit Provider, Modell, Aufgabe, Modus, Fähigkeiten, Quelle, Begründung und Zeitstempel.
- Der anschließende HTTP-Aufruf muss exakt Provider und Modell dieses Receipts verwenden.
- Priorität:
  1. nutzbarer expliziter Override
  2. persistierte Aufgabenpräferenz
  3. fähigkeitsbasierte Empfehlung
  4. anderes geeignetes Live-Modell
- Falsche Fähigkeiten, insbesondere Textmodell statt Visionmodell, sind kein zulässiger Fallback.
- Gleichstand: bereits geladenes Modell, danach Providerpräferenz, danach stabile Provider-/Namenssortierung.
- Bei Providerfehler: genau eine Inventaraktualisierung und höchstens drei unterschiedliche Kandidaten.
- Persistenz bleibt rückwärtskompatibel:
  - `task_overrides[task]` enthält weiterhin die Modell-ID.
  - Optional ergänzt `task_provider_overrides[task]` den Provider.
- Aktualisierung erfolgt beim Backendstart, beim Öffnen oder Aktualisieren der Modellansicht, nach einer Override-Änderung und einmalig nach einem Providerfehler.

### 3.5 Videovertrag

- Backend- und OpenAPI-Vertrag bleiben bei `SceneInfo.confidence: Optional[float]`.
- Das handgeschriebene C#-DTO wird auf `double? Confidence` korrigiert.
- Es wird kein künstlicher Confidence-Wert erfunden.
- OpenAPI, generierter Client und handgeschriebene DTOs erhalten eine automatische Nullability-Paritätsprüfung.

## 4. Ausführung T340–T369

### Phase 1 – Wahrheits- und Root-Cause-Gate

- **T340 – Evidenz einfrieren:** Manuelles Laufzeitlog in die versionierte Evidence-Struktur kopieren, Original und Kopie hashen, Git-/Runtime-/Konfigurationsinventar sichern und bisherige Release-Marker invalidieren.
- **T341 – Governance registrieren:** OBJ-71, FR-326–FR-336, TR-336–TR-345, OR-332–OR-334 und T340–T369 in Spec, Tasks und Fortschrittsledger aufnehmen.
- **T342 – Unabhängige Ursachenprüfung:** GPU-Zuordnung, LHM-Vertrauenskette, Providerinventar und DTO-Nullability jeweils reproduzieren und durch eine zweite unabhängige Messmethode falsifizieren lassen.
- **T343 – Verträge einfrieren:** Adapter-, Provider-, Auswahl-, DTO-, Fehler- und Restore-Verträge dokumentieren. Keine Implementierung, solange ein Root Cause nicht `CONFIRMED` ist.

Verbindliche Skills: `caveman`, `pb-master`, `gpu-expertise`, `model-registry-expertise`, `config-expertise`.

Vor T361 sind ausschließlich Diagnostik, Syntax-/XML-Prüfung, Truncation-Schutz sowie statische Referenz- und Vertragsprüfungen erlaubt.

### Phase 2 – GPU- und Runtime-Reparatur

- **T344 – Adapterresolver:** Zentralen DXGI-/LUID-Resolver und Konfigurationspräzedenz implementieren.
- **T345 – DirectML-Konsumenten:** ModelLoader, RAFT, Moondream, SigLIP, CLAP und Audio-Separator an denselben Providervertrag anbinden.
- **T346 – VRAM-Kohärenz:** VRAM-Arbiter, Budgetmanager und Systemmonitor an denselben Adapter binden und physische Obergrenzen erzwingen.
- **T347 – LHM-Vertrauenskette:** Offizielles 0.9.6-Bundle sichern, validieren, manifestieren, Launcher-Umgebung anbinden und Restore-Probe vorbereiten.
- **T348 – GPU-Wahrheit in API/UI:** Additive Statusfelder sowie eindeutige Aktiv-, Degraded- und Fehleranzeigen implementieren.

Shared Files, `backend/app_state.py`, `backend/main.py`, Config Manager, Model Registry und öffentliche DTOs werden ausschließlich sequenziell bearbeitet.

### Phase 3 – Provider- und Modellreparatur

- **T349 – LM-Studio-JIT:** Konfiguration sichern und hashen, JIT über den unterstützten Mechanismus aktivieren, Neustart- und Restore-Ablauf dokumentieren.
- **T350 – Inventarservice:** Providerzustände und installierte, geladene, nutzbare sowie verifizierbar herunterladbare Modelle zentral erfassen.
- **T351 – Startaktualisierung:** Einmalige Startinventarisierung, Cacheinvalidierung und gebündelte Providerabfragen ohne Request-Sturm implementieren.
- **T352 – Selection Receipt:** Fähigkeitsbasierte Provider-/Modellauswahl mit nachvollziehbarer Begründung und begrenztem Failover implementieren.
- **T353 – Modellwechsel:** Persistenten Provider-/Modellwechsel pro Aufgabe rückwärtskompatibel implementieren.
- **T354 – Modelloberfläche:** Installiert, geladen, herunterladbar, nicht verfügbar und Providerstatus wahrheitsgemäß darstellen; Geistermodelle entfernen.

### Phase 4 – DTO, Verträge und vorbereitete Prüfungen

- **T355 – SceneInfo reparieren:** C#-Confidence nullable machen und wiederholte Batchfehler im Videoanalysepfad verhindern.
- **T356 – Vertragsabgleich:** Konfiguration, DTOs, OpenAPI-Artefakte und generierte Clients synchronisieren.
- **T357 – Tests schreiben:** Unit-, Vertrags-, Integrations-, Hardware- und GUI-Prüfungen anlegen, aber noch nicht ausführen.
- **T358 – Security Review:** Sämtliche T340–T357-Diffs auf Pfad-, Prozess-, Download-, Hash-, Provider- und Konfigurationsrisiken prüfen.
- **T359 – Vollständigkeit:** Alle DirectML-Session-Erzeugungen, Provideraufrufe, DTO-Kopien und UI-Bindings statisch durchsuchen.
- **T360 – Implementierungsgate:** Erst bei vollständiger Evidenz, sauberem Syntax-/XML-Sweep und geschlossenem Review `.completed` neu erzeugen.

### Phase 5 – QC

- **T361 – Gezielte Regressionen:** Adapterresolver, Providerinventar, Selection Receipt, DTO-Nullability, Konfigurationsmigration und Restore-Verträge ausführen.
- **T362 – Gesamtsuite:** Python-Gesamtsuite, WPF-Release-Build, Security-, Fehler- und Wiederanlaufprüfungen ausführen.
- **T363 – Hardwarebeweis:** Bei aktiver RAFT-, SigLIP-, Moondream-, CLAP- und Audio-Last PID, Adapter-LUID, Engine-Auslastung und VRAM messen. RX 7800 XT muss aktiv sein; die iGPU darf für diese Prozesse keine DirectML-Last zeigen.
- **T364 – Modell-E2E:** LM-Studio-JIT, Ollama-Inventar, Startrefresh, Fähigkeiten, Modellwechsel, Persistenz, Offline-/Empty-Zustände und begrenztes Failover prüfen.
- **T365 – GUI-/Analyse-E2E:** Modellkennzeichnungen, GPU-Status und Videoanalyse mit `confidence=null` prüfen. Keine JSON-Ausnahme und kein Retry-Sturm zulässig.
- **T366 – Full-Length H.264:** Vollständiger Export und vollständige Prüfung über `6335,027` Sekunden.
- **T367 – Full-Length HEVC:** Vollständiger Export und vollständige Prüfung über `6335,027` Sekunden.

Jeder FFmpeg-Langläufer wird mindestens alle 15 Minuten anhand von PID, Logwachstum, Outputgröße und `out_time` protokolliert. Jede neue Exportdatei wird vollständig analysiert; Kurzprüfungen gelten nicht als Ersatz.

### Phase 6 – Wahrheit und Veröffentlichung

- **T368 – Abschlusswahrheit:** QC-Bericht, CHANGELOG, ADRs, CLAUDE-Projektstatus, Tasks, Progress-Ledger und PB-Studio-Bereich des Brain-Vaults aktualisieren. `.qc-passed` nur bei 100 Prozent PASS aller Gates erzeugen.
- **T369 – Veröffentlichung:** Zonenweise committen, Secret-Scan und Remote-Diff durchführen, PB Studio und ausschließlich PB-Studio-Pfade des Brain-Repositories pushen und Remote-SHAs nach jedem Push verifizieren.

## 5. Test- und Abnahmekriterien

- Jede PB-Studio-DirectML-Session verwendet denselben RX-7800-XT-Index und -LUID.
- Beide DirectML-Speicherflags bleiben bei jeder Session deaktiviert.
- Kein stiller CPU-, CUDA-, ROCm- oder NVIDIA-Fallback.
- Angezeigter VRAM, Budget und Laufzeitmonitor gehören zum ausgewählten DirectML-Adapter.
- LHM startet nur mit freigegebenem Manifest und passenden Hashes.
- LM Studio stellt nach dem Start bei aktivem JIT seine tatsächlich verfügbaren lokalen Modelle bereit.
- Ollama- und LM-Studio-Modelle werden bei jedem PB-Studio-Start neu inventarisiert.
- Keine Modellkarte wird ohne installierten oder live verifizierten Downloadstatus angezeigt.
- Jede Analyse protokolliert einen Selection Receipt; der reale HTTP-Aufruf stimmt mit ihm überein.
- Aufgabenbezogener Modellwechsel bleibt nach Neustart erhalten und verwendet den gewählten Provider.
- Visionaufgaben erhalten niemals ein reines Textmodell.
- `confidence=null` lässt sich in WPF deserialisieren und löst keine wiederholten Videoanalysefehler aus.
- Python-Gesamtsuite und WPF-Release-Build bestehen vollständig.
- H.264 und HEVC bestehen jeweils den vollständigen Test über `6335,027` Sekunden.
- `.completed` existiert erst nach T360.
- `.qc-passed` existiert ausschließlich bei vollständig gespeichertem PASS aller End-QC-Gates.
- Alle lokalen und Remote-SHAs, Testlogs, Exporthashes und Prüfbelege sind im Progress-Ledger referenziert.
- Erst nach diesen Kriterien wird PB Studio als bereit für den nächsten realen Benutzertest gemeldet.

## 6. Fortschritt, Skills, Parallelität und Anti-Loop

`repair-progress.md` führt für jeden Task:

- Status: `CONFIRMED`, `OPEN`, `DECIDED` oder `BLOCKED`
- Start, ETA und Ist-Zeit
- Owner und Code-Zone
- Root-Cause- und Datenflussbeleg
- veränderte Dateien
- Prüfbeleg
- Commit und Remote-SHA

Verbindliche Ausführung:

- `caveman` und `pb-master` bleiben während jedes Tasks sowie bei jedem Subagenten aktiv.
- Weitere Fachskills werden entsprechend der betroffenen Zone ergänzt.
- Vor jeder Implementierung werden Root Cause, Datenfluss, Caller, Seiteneffekte und Architekturvertrag verifiziert.
- Parallelität ist nur für nachweislich disjunkte Code-Zonen zulässig.
- Shared Files, öffentliche Verträge, `backend/app_state.py`, `backend/main.py`, Config Manager und Model Registry bleiben sequenziell.
- Taskstart, Abschluss und Blocker werden im Ledger protokolliert; bei Langläufern spätestens alle 30 Minuten.

Anti-Loop:

- Gleicher fehlgeschlagener Befehl höchstens zweimal.
- Höchstens drei Fixzyklen pro identischer Fehlersignatur.
- Höchstens drei gleichzeitig offene Ursachenhypothesen.
- Nach 45 Minuten ohne neue Evidenz oder nach zweimaliger ETA: `BLOCKED`.
- Keine Tests vor T361.
- Keine neue Dependency oder Lockfile-Änderung.
- Keine Datenmigration.
- Keine fremden Änderungen bereinigen oder zurücksetzen.
- Kein Force-Push und kein automatisches Rebase.
- Bei Remote-Divergenz gemäß D07: `BLOCKED`.
- Erfolg darf ausschließlich mit gespeichertem Beleg behauptet werden.

## 7. Referenzverträge

- ONNX Runtime DirectML: `https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html`
- LM Studio JIT: `https://lmstudio.ai/docs/developer/core/headless`
- LM Studio Server Settings: `https://lmstudio.ai/docs/developer/core/server/settings`
- LibreHardwareMonitor Releases: `https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases`

