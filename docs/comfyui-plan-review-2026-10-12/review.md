# Consulting Team Review

> Auftrag: Kritische Prüfung des eingebrachten PB-Studio/ComfyUI-Umbauauftrags, einschließlich bestehender Produktionsketten, Zielverträge, Risiken und Implementierungsreihenfolge.
> Stand: 2026-10-12, Europe/Zurich. PB-HEAD `e51e798cc05cd6ec4f42a9e69ee3e9284dc5bcdb`; vorhandener Arbeitsbaum ist verändert. Kein Umbau durchgeführt.
> Reversibilität: Additive Bridge mit Feature-Flag ist eine two-way door. Datenmigration, Austausch von Embedding-Räumen und Entfernung nativer Provider sind gesonderte, schwer rückgängig zu machende Entscheidungen.

## Executive Summary

**GO-mit-Modifikation für die Richtung; keine Implementierungsfreigabe für den vorliegenden Text als fertigen Bauplan.** Die Trennung zwischen PB-Control-Plane und Comfy-Ausführung ist tragfähig, sofern PB zusätzlich dauerhafte Jobidentität, sichere Ergebnisübernahme und überprüfbare Provider-Verträge besitzt. Der Text ist ein umfangreicher Anforderungskatalog und Planungsauftrag; er enthält noch keine ausführbare Job-State-Machine, keine Transaktionsgrenzen und keine belastbare Garantie für GPU-Koordination bei gleichzeitig manuell nutzbarem ComfyUI. Die kritischsten Risiken liegen an Übergängen zwischen Prozessen, Projekten, Dateisystem, SQLite und Embeddings. Confidence: HIGH für belegte Vertragslücken; UNVERIFIZIERT für tatsächliche Generierungsqualität und Durchsatz auf der Zielmaschine.

## Prüfgrundlage und Beweisgrenzen

- **[ABSICHT]** bezeichnet Anforderungen aus dem eingebrachten Text oder vorgeschlagene Zielverträge. Diese sind nicht implementiert.
- **[BEOBACHTUNG]** bezeichnet gelesenen Quelltext oder Antworten auf lesende API-Anfragen. Eine sichtbare Funktion oder registrierter Node beweist keinen erfolgreichen Medienlauf.
- **[NACHWEIS]** bezeichnet tatsächlich ausgeführte Prüfungen: AST-Parsing und In-Memory-Kompilierung aller 148 Python-Dateien unter `src/pb_studio` und `backend`, insgesamt 64.583 Zeilen, ohne Parse-/Kompilierfehler; lesende Comfy-HTTP-Anfragen; Hash-Inventar der Quellen. Diese Prüfungen führen keine Appimporte aus und prüfen weder Typen noch fachliche Semantik.
- Inventar: 254 Quellen einschließlich 148 Python-Dateien sowie 106 C#/XAML/Projektdateien; C# nicht gebaut, XAML nicht live geprüft. `rg` und rekursives Inventar zählen wegen Ignore-Regeln unterschiedlich.
- Semantisch geprüft wurden kritische Produktionsketten durch drei unabhängige Fachagenten und den Hauptagenten. **Nicht jede Zeile des gesamten Quellcodes wurde fachlich vollständig verifiziert.** Dieser Bericht ist kein vollständiger Bug-, Security- oder Release-Audit.
- Kein neuer Workflow eingereiht; kein laufender Job angehalten; kein Modell entladen; kein Dienst gestartet oder beendet; keine DB geöffnet mit schreibendem Zugriff; keine Originalmedien bearbeitet; keine Installation/Migration.
- Bei der lesenden Queue-Aufnahme lief ein fremder Comfy-Job. Seine Inhalte wurden im gespeicherten Beleg nicht übernommen; nur IDs und Anzahlen.
- Quelleninventar und redigierte API-Aufnahme: `source-inventory.json`, `evidence.json`. Alle vorgeschlagenen Pfade in `architecture-and-delivery.md` sind ausdrücklich **geplant**.

### Aktueller Comfy-Kontext

**[BEOBACHTUNG]** `http://127.0.0.1:8188/system_stats` meldete ComfyUI **0.39.2**, Python **3.13.12**, PyTorch **2.12.0+rocm7.14.0**, RX 7800 XT, Gerätetyp `cuda` mit AMD-Gerätenamen. `cuda` in dieser ROCm-PyTorch-Antwort ist kein Beleg für NVIDIA-Hardware. Die laufende Prozesskommandozeile verweist auf die Umgebung unter `C:\Users\david\ComfyUI-Installs\ComfyUI\ComfyUI\.venv`.

Der dazu passende Quellordner `C:\Users\david\ComfyUI-Installs\ComfyUI\ComfyUI` enthält Version 0.39.2 und HEAD `3c1b7a17fdf239d35ce98cc777756f572d089795`. Der ältere Ordner `C:\ComfyUI` enthält dagegen Version 0.38.1 und HEAD `20ca544ee0436721d8eb5f544665e490609f72c8`. Quellenaufnahme und API-Version stimmen beim neuen Ordner überein; ein kryptographischer Nachweis sämtlicher im laufenden Prozess importierter Dateien wurde nicht geführt.

`/object_info` meldete **1.380 registrierte Nodes**, darunter `EmptyMiniMaxH3LatentAV`, `MiniMaxH3ImageToVideo`, `FL_MiniMaxH3BeatKSampler` und LTX/Wan-Nodes. **Ausführbarkeit, Modellvollständigkeit, Genauigkeit, Geschwindigkeit und Bildqualität bleiben UNVERIFIZIERT.** Aus dem Fehlen eines namensgleichen Beat- oder Demucs-Nodes wird keine generelle Nichtverfügbarkeit abgeleitet.

### Team und Methoden

Alle sieben Consulting-Rollen wurden verwendet: Engagement Manager, Senior Partner, Analyst, Domain Expert, Risk Officer, Devil's Advocate und Synthesizer. Drei echte Analyseagenten prüften Laufzeit/Architektur, Medien/Daten sowie die unabhängige Gegenposition. Devil's Advocate erhielt das Artefakt ohne Nutzerbegründung oder Ergebnisse anderer Rollen; später nur neue Umgebungsbeobachtungen zur korrekten Quellenwahl. MECE/SCQA strukturierten fünf Prüfbereiche: Produktgrenze, Integrationsverträge, Daten/Medien, Betrieb/Ressourcen und Nachweise/Migration. Pre-Mortem und Reversibility ergänzten die Fehleranalyse.

**Skill-Konflikte:** `consulting-team/personas/domain-expert.md` nennt einen abweichenden PySide6/ROCm/ChromaDB-Stack. `pb-master` beschreibt unter anderem CLAP auf AMD als nicht verfügbar; gelesener PB-Code verwendet registriertes ONNX/DirectML-CLAP. Diese Skill-Angaben wurden nicht als Fakten übernommen. Das in Regeln geforderte Brain-Verzeichnis `_wiki/decisions` fehlt aktuell; vorhandene Brain-Notizen und aktuelle Quellen wurden gelesen. Die Brain-Rückgabe enthält historische Statusangaben; sie ist kein aktueller Testbeleg.

## Findings

Severity bezieht sich auf das Risiko einer Umsetzung **ohne** den jeweiligen Gegenentwurf. Es wird kein eingetretener Schaden durch diesen noch nicht implementierten Umbau behauptet. Jeder Befund enthält ein falsifizierbares Prüfkriterium.

### 🔴 Critical

#### F01 — Unabhängige Comfy-Nutzung benötigt gemeinsamen Admissionvertrag

- **Rollen:** Domain Expert, Risk Officer, Devil's Advocate. **Plan:** §§3, 26, 79, 80.
- **Was:** PB-Prozesslocks verhindern keine Jobs aus Comfy-Browser, weiteren Clients oder anderen Modellservern. Getrennte Umgebungen teilen weiterhin GPU, VRAM, RAM und Dateisystem.
- **Beleg:** `backend/dependencies.py:20` verwendet einen lokalen Async-Lock; `src/pb_studio/core/gpu_lock.py` enthält einen lokalen Thread-Lock. `vram_budget_manager.py:349–425,630–691` führt Eigenbuchhaltung; Sensordifferenzen sind Warnungen und keine verbindliche Fremdprozessreservierung. Aktuell läuft ein Job aus einem anderen Client.
- **Warum kritisch:** Ein PB-Gate kann trotz zuvor leerer Queue gleichzeitig mit einer neu gestarteten Fremdausführung Modelle laden. Ein Polling-Snapshot schließt dieses Rennen nicht. **Critical gilt hier nur für ein Betriebsprofil, das trotz unkooperierender Clients harte Exklusivität zusagt; ohne diese Zusage ist es eine High-Designpflicht.** Der Auftrag verbietet einen gemeinsamen kooperativen Gate nicht; dieser Vertrag fehlt bisher.
- **Counter-Proposal:** Zwei explizite Betriebsmodi: `observed_shared` bietet Wartelogik und Warnungen, keine Exklusivgarantie; `managed_exclusive` benötigt einen kooperierenden Comfy-seitigen Admission-Gate für **alle** GPU-Aufträge derselben Maschine. Fremde LM-Studio/Hermes-Last bleibt gesondert zu koordinieren. Ohne Gate werden harte Garantien aus dem Plan gestrichen.
- **Prüfkriterium:** Manuellen Job zwischen PB-Probe und PB-Start starten; entweder serverseitig abweisen/warten oder ehrlich Shared-Modus melden. Keinen fremden Job abbrechen/entladen.

#### F02 — Verlust der Submit-Antwort kann doppelte Ausführung verursachen

- **Rollen:** Risk Officer, Domain Expert. **Plan:** §§22, 23, 46, 59.
- **Was:** `pending → queued` beschreibt nicht den Zustand „Server nahm Auftrag an, HTTP-Antwort ging verloren“. Blindes Retry ist dann kein sicherer Wiederanlauf.
- **Beleg:** Aktiver Comfy-Quelltext `server.py:1080–1144` validiert Prompt und fügt ihn in die Queue ein. Ein vom Client vorgegebener UUID-`prompt_id` ist zulässig; diese UUID allein ist keine nachgewiesene serverseitige Idempotenzgarantie. `execution.py:1286ff` hält Queue und History im Speicher.
- **Warum kritisch:** Nach Netzwerkfehler oder PB-Crash können dieselben Shots mehrfach generiert, Outputs überschrieben und bei Cloud-Nodes mehrfach berechnet werden.
- **Counter-Proposal:** Durable Submit-Outbox, Attempt-ID, Payloadhash, persistierter Status `submission_unknown`; vor Wiederholung Queue/History/Receipt/Outputmanifest abgleichen. Bei nicht entscheidbarem Zustand keine automatische kostenpflichtige Wiederholung. Genau-einmaliger Import ist mit Unique-Constraint erreichbar; genau-einmalige entfernte Ausführung benötigt zusätzlichen Serververtrag.
- **Prüfkriterium:** Verbindung nach serverseitigem Accept gezielt verlieren; PB-Neustart darf keinen zweiten Submit und keinen zweiten Medienimport auslösen.

#### F03 — Fertigmeldung ohne Importtransaktion gefährdet Katalog und Medienreferenzen

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§17, 22, 23, 34, 35, 45, 48.
- **Was:** „Generation fertig“ ist nicht gleich „Datei dauerhaft übernommen, QC bestanden, Analysen gespeichert, FAISS erreichbar“. Datei, SQLite und FAISS bilden keine gemeinsame atomare Transaktion.
- **Beleg:** `data/vector_operation_outbox.py` enthält bereits eine Outbox für crashkonsistente Vektorlöschungen. `storage/recovery_adapters.py:29–40,328–357,717–732` inventarisiert bestimmte Eigentümer/Projektdateien; Medien können bloß externe, optional verfügbare Referenzen sein.
- **Warum kritisch:** Crash zwischen Dateischreiben, Katalogcommit und Vektoreinfügung kann einen als abgeschlossen markierten Job mit fehlendem Clip oder falschem Vektormapping zurücklassen.
- **Counter-Proposal:** Eindeutige Staging-Datei pro Attempt, vollständige QC, Contenthash, atomare Veröffentlichung auf demselben Volume, DB-Ingest-Receipt und reparierbare Vektoroperation. Neue Dateien/Manifeste in bestehende Recovery-Owner-Inventare aufnehmen. `ready` erst nach den für diesen Workflow verbindlichen Stufen.
- **Prüfkriterium:** Crash an jeder Commitgrenze; nach Restart genau ein gültiger Clip oder klarer reparierbarer/quarantänisierter Zustand. Keine dangling Timeline-ID.

#### F04 — Austauschbare Embeddings sind ohne gemeinsamen semantischen Raum nicht austauschbar

- **Rollen:** Domain Expert, Analyst. **Plan:** §§9, 15, 32, 35, 71.
- **Was:** Auch gleich lange Vektoren verschiedener Encoder dürfen nicht blind im selben Suchraum gemischt werden.
- **Beleg:** `backend/routers/pacing_router.py:334–339` verlangt 1152 Dimensionen. `data/vector_store.py:409–426` prüft Dimensionen; das beweist keinen Modellraum. `data/database_core.py:72–78` verwendet `faiss_id` als Primärschlüssel ohne Raum-/Indexidentität. `brain/post_processor.py:88–101` bindet CLAP/SigLIP-Modellversionen und trainierten Projektor.
- **Warum kritisch:** Retrieval und Brain können mathematisch gültige, fachlich bedeutungslose Similarities liefern. Gleiche Dimension behebt dieses Problem nicht.
- **Counter-Proposal:** Phase 1 übernimmt nur den bestehenden registrierten SigLIP-Raum einschließlich Processor-/Normalisierungsidentität. Andere Encoder zunächst Benchmarks/Quarantäne. Spätere Raumwechsel brauchen getrennte Namespaces und Mappingmigration oder vollständig validiertes Re-Embedding; kein Padding/Truncation als Reparatur.
- **Prüfkriterium:** Zwei verschiedene Encoder gleicher Dimension müssen abgewiesen oder getrennt geroutet werden; bestehende Suche bleibt unverändert.

### 🟠 High

#### F05 — ROCm-Bereichsentscheidung fehlte bei Erstprüfung; inzwischen geklärt

- **Rollen:** Engagement Manager, Domain Expert. **Plan:** §27 gegenüber Projektregeln.
- **Was:** Plan lässt ComfyUI eigene AMD-Lösung zu; aktuelle `CLAUDE.md:41–42` erlaubt DirectML und eine eng umrissene LM-Studio-Vulkan-Ausnahme, verbietet ROCm. Aktiver Comfy-Server meldet ROCm.
- **Warum kritisch:** Ohne klaren Geltungsbereich lässt sich kein regelkonformer Ausführungspfad freigeben. Separater Python-Prozess entscheidet diese Governance-Frage nicht.
- **Counter-Proposal:** ADR: „PB-intern ONNX/DirectML; ComfyUI als externe Anwendung darf eigene ausdrücklich freigegebene AMD-Laufzeit nutzen“ oder ROCm global ausschließen und reale Alternative testen. Keine heimliche Providerumstellung.
- **Prüfkriterium:** Deployment-Check klassifiziert jede Laufzeit nach explizitem Policy-Scope; ungeklärte Ausführung bleibt gesperrt.
- **Auflösung durch Nutzer, 2026-10-12:** ComfyUI-Ausnahme erlaubt; PB-interne ONNX-Pfade bleiben DirectML. [D01 in decisions.md](decisions.md). Governance-Konflikt geklärt; technische Ausführungs-/Hardwaregates bleiben offen. Keine Runtime-/Konfigurationsänderung vorgenommen.

#### F06 — Falsche Comfy-Installation kann Discovery und Quellenprüfung entwerten

- **Rollen:** Analyst, Domain Expert. **Plan:** §§5, 28–30, 56–57, 76.
- **Was:** Automatische Erkennung braucht eindeutige Server-/Installationsidentität. Auf dieser Maschine existieren mindestens zwei gelesene Comfy-Quellstände.
- **Beleg:** Laufzeit 0.39.2/neuer Ordner gegenüber `C:\ComfyUI` 0.38.1; siehe `evidence.json`.
- **Counter-Proposal:** Persistierte `server_id`, Endpoint, Transportmodus, aktive Version, Discovery-Fingerprint, optionale lokale Source-Zuordnung. Bei mehreren Kandidaten Auswahl statt Port-Hopping. Sourcepfad niemals aus alter Notiz übernehmen.
- **Prüfkriterium:** Zwei lokale Server mit unterschiedlichen Nodes/Modellen; ausgewählter Workflow darf nur gegen den gebundenen Server validiert und ausgeführt werden.

#### F07 — Abbruch, Queue-Clear und Speicherfreigabe haben unterschiedliche Reichweite

- **Rollen:** Risk Officer, Domain Expert. **Plan:** §§5, 24, 26, 46.
- **Beleg:** Aktive Quelle `server.py:979–995` bietet zielgerichteten Job-Cancel. `server.py:1168–1198` kennt `prompt_id`-Interrupt und globalen Fallback; `1154–1166` kennt globales Queue-Clear. `/free` setzt serverweite Flags; tatsächliches Entladen erfolgt später im Worker (`main.py:396ff`).
- **Warum kritisch:** Pauschales „Cancel“ oder `/free` kann fremde Arbeit treffen. HTTP 200 bei Cancel/Free ist kein Beleg für terminalen Zustand oder freies VRAM. Die zielgerichtete `/interrupt`-Prüfung und anschließende Unterbrechung ist zudem getrennt; der atomare Job-Cancel ist vorzuziehen.
- **Counter-Proposal:** Nur eigene IDs mit bevorzugtem `/api/jobs/{id}/cancel`; fallback nur versiongeprüft und ownership-sicher. Kein Queue-Clear, History-Clear oder globaler Interrupt durch PB. `/free` ausschließlich nach ausdrücklichem Instanz-/Ressourcenvertrag; Abschluss und Telemetrie abwarten.
- **Prüfkriterium:** Fremder Job läuft, PB-Job wartet: PB-Cancel entfernt ausschließlich PB-Job. Cancel gegen inzwischen abgeschlossene ID trifft keinen Nachfolgejob.

#### F08 — Pause/Resume benötigt präzise operative Semantik

- **Rollen:** Risk Officer, Devil's Advocate. **Plan:** §§23, 24, 79.
- **Was:** §23 beschreibt bereits sinnvoll Wiederaufnahme an Shotgrenzen. §24 lässt die operative Wirkung von Pause auf einen laufenden Shot offen. Serienproduktion nach abgeschlossenen Shots fortsetzen ist realistisch; Sampler mitten im Schritt nach Prozessneustart weiterlaufen zu lassen wäre ein eigener Checkpointvertrag, den der Auftrag nicht ausdrücklich verlangt.
- **Beleg:** Gelesene Comfy-PromptQueue ist im Speicher; kein allgemeiner dauerhafter Sampler-Checkpointvertrag wurde für alle Workflows nachgewiesen.
- **Counter-Proposal:** `pause` stoppt zunächst neue Dispatches; laufender Shot darf fertig werden. Nach Restart validierte Outputs übernehmen, ungeklärte Attempts abgleichen. Echte Mid-Workflow-Resume nur capability-spezifisch mit Checkpointhash/Versionsbindung.
- **Prüfkriterium:** Bei 342 fertigen Shots und fehlendem Shot 17 nicht blind bei Index 343 beginnen; alle offenen Abhängigkeiten/Receipts prüfen. Bereits veröffentlichte Outputs nicht regenerieren.

#### F09 — Projektwechsel kann verspätete Ergebnisse in falsches Projekt schreiben

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§17, 22, 23, 48.
- **Beleg:** `backend/app_state.py` definiert `ProjectOperationContext`, Kontextprüfung, registrierte Operationen und Drain/Cancel beim Projektwechsel (`129,220,312,332,383`). WPF `ProjectService` verwendet eigene Generationen.
- **Counter-Proposal:** Dauerhafte Jobbindung an Projekt-UUID/Root, Sourcehash, Shotplanrevision; niemals beim Callback erneut `current_project` als Eigentümer verwenden. In-memory Epoch nicht als nach Restart gültige Identität persistieren. Ergebnis nach Wechsel sicher stagen und erst im gültigen Projektkontext committen.
- **Prüfkriterium:** Auftrag in A, Wechsel nach B, Output für A: B-Katalog/Timeline bleiben unverändert; A-Auftrag bleibt erreichbar.

#### F10 — Bestehende RenderQueue ist Vorlage, kein fertiger externer Jobmanager

- **Rollen:** Domain Expert. **Plan:** §§4, 22, 24.
- **Beleg:** `rendering/render_queue.py` besitzt SQLite-Persistenz, Dedupe und CAS-Statuswechsel. `core/task_queue.py:22` verwendet In-Memory-PriorityQueue. `core/thread_pool.py` ist ein Qt-Worker-Pattern; kein produktiver Backend-Aufrufer wurde in der Agentensuche belegt.
- **Counter-Proposal:** CAS-/Repository-/Dedupe-Patterns wiederverwenden; Render-Fachmodell unverändert lassen. Eigene typisierte externe Attempts mit `submission_unknown`, Remote-Receipt und Importsaga ergänzen. Gemeinsame Queue-Ansicht darf mehrere Fachqueues aggregieren.
- **Prüfkriterium:** Interrupted-Comfy-Attempt wird nicht wie ein sicher neu startbarer lokaler FFmpeg-Job blind wiederholt.

#### F11 — Recovery-Inventar und Zombie-Watcher fehlen im Integrationsplan

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§23, 48, 61.
- **Beleg:** `backend/main.py:346–378` beurteilt Idle anhand SSE-Clients, GPU-Lock und Renderaktivität. `backend/recovery_runtime.py:44–97` erstellt generationsgebundene Snapshots mit Owner-Inventaren und Quiesce-Callbacks. `recovery_adapters.py:119–226` kennt bestehende Tabellen/Referenzen.
- **Counter-Proposal:** Aktive externe Arbeit und dauerhafte pending commits in Lifespan/Owner-Lease/Idle-Policy berücksichtigen. Snapshot darf nicht auf fremde Netzwerkjobs warten; lokale Commits unter Recovery-Barrier, externe Zustände dauerhaft als reconciliable speichern. Neue Quarantäne-/Jobdateien inventarisieren.
- **Prüfkriterium:** WPF schließen, Comfy-Job läuft: PB verhält sich entsprechend dokumentierter Detach-/Drain-Policy; Restart stellt keine abgeschlossene neue Generation unbemerkt auf alte Jobzustände zurück.

#### F12 — Resultschema braucht Einheiten, Zeitbasis und Herkunft pro Feld/Stufe

- **Rollen:** Domain Expert, Analyst. **Plan:** §§13–15, 32, 33.
- **Was:** `beats: []`, `motion: {}` und `status: completed` definieren weder Sekunden/Frames noch missing/empty, Confidence, Latenzkorrektur oder räumliche Normierung.
- **Beleg:** Bestehende Stagemodelle, Downbeat-Provenance, Beatgrid-Segmente und Kurvenmetadaten werden in PB verwendet. `pacing/clip_selector.py:823,837` skaliert Bewegung durch 30; fremde Motionwerte sind nicht automatisch gleich skaliert.
- **Counter-Proposal:** ProviderResult-Envelope plus typisierte Stagepayloads, rationale Zeitbasis, Offset, Sample-/Hoprate, Mess-/Ableitungsstatus, Sourcehash, Adapter-/Model-/Workflowidentität. Validierung von Reihenfolge, Dauergrenzen, finiten Zahlen und Einheiten vor Persistenz.
- **Prüfkriterium:** Millisekunden als Sekunden, lokale Chunkzeit als globale Zeit, NaN-Motion und zu lange Kurven müssen klar abgewiesen werden; leere valide Beatliste bleibt von „unavailable“ unterscheidbar.

#### F13 — Workflow-JSON ist nicht gleich ausführbarer API-Prompt

- **Rollen:** Domain Expert, Analyst. **Plan:** §§7, 8, 38, 70.
- **Beleg:** Offizielle API-Beispiele und `/prompt` arbeiten mit Node-Dictionaries, `class_type`, `inputs` und Referenzen `[node_id, output_index]`. UI-Graph enthält Layout/Widgets/Links. Beides erscheint aktuell auch im laufenden Queue-Artefakt, erfüllt aber verschiedene Aufgaben.
- **Counter-Proposal:** API-Prompt als kanonisches Ausführungsartefakt; UI-Graph optional zum Bearbeiten. Semantisches Mapping außerhalb des Graphs auf konkrete Node-ID/Inputslot der **gepinnten** Revision. Node-IDs dürfen technische Adressen sein, aber keine globale Bedeutung besitzen. Kein Mapping über übersetzbare Titel.
- **Prüfkriterium:** UI-Graph darf nicht versehentlich als API-Prompt eingereiht werden; geänderte IDs oder Widgetlayouts invalidieren betroffene Mappings verständlich.

#### F14 — Discovery beweist weder Modellhash noch Custom-Node-Version noch erfolgreiche Ausführung

- **Rollen:** Analyst, Domain Expert. **Plan:** §§5–7, 28–30, 50, 53.
- **Beleg:** `/object_info` beschreibt registrierte Nodes; `/models/{folder}` nennt Dateien; `/extensions` betrifft Web-Erweiterungen, nicht vollständige Node-Paketinventare. Lokale H3-Nodes existieren. Nicht jede Versions-/Hashinformation ist über den Standardserververtrag belegbar.
- **Counter-Proposal:** Vier getrennte Zustände: entdeckt, statisch kompatibel, Smoke bestanden, für Profil qualifiziert. Paket-/Modellmanifest lokal oder über optionalen Inspector; bei unbekanntem Hash `identity_unverified`. Modellrolle plus gesamter Bundlehash statt einzelner Modellname. Fehlerbehebung zeigt echten Loader-/Inputbedarf.
- **Prüfkriterium:** Zwei Modelle gleichen Dateinamens mit anderem Inhalt; Provider darf nicht selben Provenance-/Cachekey erhalten. Node vorhanden, Modell defekt: Status ist nicht „BEREIT“.

#### F15 — Beliebige zukünftige Nodes brauchen adapterfähige Outputverträge

- **Rollen:** Senior Partner, Domain Expert. **Plan:** §§4, 7, 32, 70–71.
- **Was:** Austauschbare Workflows sind möglich innerhalb bekannter Ergebnisfamilien. Beliebige neue Nodes können neue Payloadtypen, Downloads, Referenzen oder Cloudzustände einführen.
- **Counter-Proposal:** Versionierter ResultAdapter-Katalog für `analysis`, `media_file`, `embedding`, `stems`, `checkpoint`. Manifest wählt registrierten Adapter; Metadaten führen keinen beliebigen Python-/Shellcode aus. Neue Semantik benötigt neuen Adapter und Tests, keinen Director-Neubau.
- **Prüfkriterium:** Unbekannte Outputstruktur wird `unsupported_output_contract`, nicht automatisch „completed“ oder blind importiert.

#### F16 — Longform erfordert begrenzte Arbeitsmengen auch innerhalb einzelner Nodes

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§13, 21, 42, 58.
- **Beleg:** Gelesener FL-Reshot-Code verwendet vollständiges Source-Decoding (`FL_MiniMaxH3TemporalReshot.py:676,715ff`); allgemeine Nodeverfügbarkeit garantiert kein Streaming. PB besitzt spezifische Streaming-/Segmentierungsverfahren.
- **Counter-Proposal:** Clip-/Chunkgrenzen, Overlap, Offset, Dedup, Peak-RAM-/VRAM-Limits, Download-/Decoded-Bytebudgets pro Workflow. Reshot erhält begrenzten Source-Ausschnitt mit Handles. Drei Stunden Mastervideo niemals ungeprüft an Full-Decode-Node übergeben.
- **Prüfkriterium:** Gleicher Workflow auf kurzen und langen Quellen; Peak-Speicher muss gemäß gebundenem Arbeitsfenster statt linear mit gesamter Dauer wachsen.

#### F17 — Generierungs-Shot und Timeline-Cut sind unterschiedliche Einheiten

- **Rollen:** Senior Partner, Domain Expert, Devil's Advocate. **Plan:** §§19–21, 40, 64.
- **Was:** Ein Video kann viele kurze beatgebundene Cuts aus weniger längeren generierten Assets verwenden. Ein Job je Cut erzeugt unnötige Arbeit und schwächere Kontinuität.
- **Counter-Proposal:** Unveränderlicher Shot-/Assetplan mit Seedstrategie, Referenzabhängigkeiten, Style/Character-Bindung und Handles; Timeline-Cuts referenzieren Teilbereiche dieser Assets. Abhängigkeits-DAG für First/Last-Frame-/Continuations; parallele Ausführung nur bei erfüllten Abhängigkeiten.
- **Prüfkriterium:** Umordnung/Retry ändert weder bereitgestellte Seeds noch bereits bestätigte Assetzuordnung. Nach Planänderung werden betroffene Jobs `obsolete`, nicht still auf neue Cuts angewendet.

#### F18 — AUTO besitzt ohne qualifizierten Benchmark keine objektive Qualitätsordnung

- **Rollen:** Senior Partner, Analyst. **Plan:** §§10–12, 64.
- **Was:** „Nicht schlechter wählen“ ist ohne Datenbereich, Metriken und Präferenzgewichtung nicht entscheidbar. Eine Qualitätsrangfolge gilt nicht pauschal für jedes Genre und jede Dauer.
- **Beleg:** Im Auftrag sind keine belastbaren Baselines/Grenzwerte enthalten. BPM-Beispiel bewertet keine Beatphase oder Downbeats. Aktuelle `ai/llm_provider.py:60–65` behandelt Legacy-`auto` als LM Studio; dieses LLM-AUTO ist kein Analyse-AUTO.
- **Counter-Proposal:** Native Baseline und Holdout vor Providerablösung; feste Quality-/Cost-/Memory-Gates, danach deterministische Auswahl mit SelectionReceipt und sichtbarem Fallbackgrund. Unqualifizierte Provider nur manuell/experimentell. Stochastic Generationcache nur mit explizitem Reuseziel.
- **Prüfkriterium:** Besserer validierter Provider fällt aus: kein stiller minderwertiger Ersatz; `waiting_for_provider` oder ausdrücklich genehmigtes Degrade mit Receipt.

#### F19 — Benchmark nach Analyseintegration kommt zu spät

- **Rollen:** Analyst, Senior Partner. **Plan:** §64 Phase 4/5.
- **Was:** Durchsatzmessung kann parallel wachsen; Referenzkorpus, Baseline und Non-Inferiority-Gates müssen vor Ergebnisänderungen existieren.
- **Counter-Proposal:** Phase 0 definiert Referenzen/Grundmetriken; Phase 1 erstellt Mini-Smoke; jede Providerphase vergleicht Native/Comfy auf identischen Quellen/Versionen. Holdouts nicht zur Parameteroptimierung verwenden; Ergebnisqualität und Betriebssicherheit getrennt bewerten.
- **Prüfkriterium:** Fachliche Regression in einer schwierigen Kohorte darf nicht durch Gesamtdurchschnitt oder schnelleres Laufzeitergebnis verdeckt werden.

#### F20 — Dateiübernahme braucht Transportvertrag, Volumegrenzen und Vertrauensprüfung

- **Rollen:** Risk Officer, Domain Expert. **Plan:** §§17, 31, 51, 59–61.
- **Beleg:** Comfy verwendet konfigurierte Input-/Output-Wurzeln; lokal aktuell auf anderen E:-Verzeichnissen. `/upload/image` und `/view` sind vorhandene Routen, aber daraus folgt kein universeller Audio-/Video-Uploadvertrag für jeden Loader. `/features` meldet aktuell 100 MiB Uploadlimit.
- **Counter-Proposal:** Local-reference nur mit expliziter Rootfreigabe und kompatiblem Loader; Remote-stream nur über verifizierten Media-Transportadapter. Pfadcontainment nach Resolve, Reparse-/Junction-/UNC-Prüfung, Größen-/Format-/Decodebudget, Hashprüfung, quarantänisierter Download, stabile Destination. Cross-Volume-Move ist nicht atomar: erst zur Destination stagen, dann veröffentlichen. Originale bleiben read-only.
- **Prüfkriterium:** Path traversal, Junction-Ausbruch, unvollständige Datei, fremde URL, riesiger Decoderinput, Output auf E: nach Import verschwunden: kein beschädigter veröffentlichter Clip.

#### F21 — Sicherheitsgrenze endet nicht bei erlaubten Workflow-Metadaten

- **Rollen:** Risk Officer, Devil's Advocate. **Plan:** §§7, 51, 70.
- **Was:** Ein Custom Node ist serverseitiger Code mit Prozessrechten. Getrennte Python-Umgebungen bieten keine Betriebssystem-Sandbox oder DB-Zugriffssperre.
- **Counter-Proposal:** Vertrauenswürdige/gepinnte Workflow- und Node-Pakete, lokale/remote Endpointallowlist, keine Umleitungen auf ungeprüfte Hosts, Cloud-/Netzwerkdeklaration, eingeschränkte Rootrechte/Prozessidentität soweit erforderlich. „Comfy erhält keine DB-Schreibberechtigung“ entweder als technische ACL-/Account-Grenze implementieren oder ehrlich nur als Integrationsvertrag formulieren.
- **Prüfkriterium:** Workflow mit ungenehmigtem Cloud-/Download-/Commandnode wird vor Submit gesperrt; Logging redigiert verschachtelte Secrets und Payloads.

#### F22 — Cloudkosten und lokale Ausführung dürfen nicht nach Modellnamen entschieden werden

- **Rollen:** Risk Officer, Analyst. **Plan:** §§16, 40, 46, 51.
- **Beleg:** Aktive Registry enthält sowohl lokale H3/LTX/Wan-Nodes als auch Partner-/Cloud-Nodes. Offizielle Partner-Node-Dokumentation beschreibt getrennte API-Ausführung. Modellname allein identifiziert keinen Ausführungsort.
- **Counter-Proposal:** Manifest `execution_location`, Netzwerk-/Kosten-/Datenschutzbedarf und Credentialreference. Default Local-only. Cloud opt-in pro Projekt/Workflow, Budgetreservation pro Attempt, harte Batch-/Retrylimits. Keine Secrets in Promptmanifest oder Queue-Logs.
- **Prüfkriterium:** 180 fehlende Shots können nicht ungeprüft 180 Cloudaufträge plus Retries auslösen; Restbudget unter Auftragspreis blockiert Dispatch.
- **Scope durch Nutzer bestätigt, 2026-10-12:** Lokal zuerst; Cloud nur separat freigegeben. [D02 in decisions.md](decisions.md). Damit keine automatische Cloudauswahl, Cloudfallbacks oder kostenpflichtigen Retries ohne diese spätere Freigabe; Umsetzung der Workflow-/Budgetprüfung bleibt erforderlich.

#### F23 — Seed und Prompt garantieren keine bitidentische Wiederholung

- **Rollen:** Analyst, Domain Expert. **Plan:** §§18, 41, 59, 79.
- **Counter-Proposal:** Reproducibility-Level: `traceable`, `rerunnable`, `deterministic_verified`. Provenance bindet gerenderten Promptgraph, aufgelöste Zufallsseeds, alle Modell-/LoRA-/Processorhashes, Node-/Server-/Adapterrevisionen, Samplerparameter, Hardware-/Runtimeprofil, Input- und Outputhashes. Gewollte Variante erhält neuen Intent; Retry bleibt eigener Attempt mit dokumentierter Seedpolicy.
- **Prüfkriterium:** Gleicher Seed bei geänderter Modellrevision darf nicht als gleiche Generation oder byteidentischer Nachweis gelten. Reproduzierbarkeit nur nach Wiederholung auf gepinntem Profil behaupten.

#### F24 — QC ist erforderlich, aber technische QC allein qualifiziert keinen Director-Clip

- **Rollen:** Analyst, Domain Expert. **Plan:** §§17, 20, 45, 47.
- **Was:** Vollständig decodierbar, richtige FPS und keine schwarzen Frames beweisen keine Prompttreue, Character-Konsistenz oder Beatwirkung. Absichtlich dunkle/statische Shots dürfen nicht pauschal aussortiert werden.
- **Counter-Proposal:** Technische harte Gates, profilabhängige visuelle Signale und menschliche Freigabe für Golden-Set getrennt. `eligible_for_director` hängt an dokumentierter Mindestdaten-/Qualitätsregel; Partial Results bleiben sichtbar. Ungenügende generierte Clips nicht automatisch als Trainingswahrheit nutzen.
- **Prüfkriterium:** Technisch korrekter, semantisch falscher Clip bleibt in Bibliothek sichtbar, aber je Profil ungeeignet; bewusst schwarzer Übergang folgt expliziter Ausnahme statt Fake-„Artefakt“.

#### F37 — Fehlende Semantik ist kein Beweis fehlender Libraryabdeckung

- **Rollen:** Domain Expert, Analyst. **Plan:** §§20, 40.
- **Beleg:** `clip_selector.py:1150–1168,1173–1234` besitzt Motionfallback und relative Kandidatenrangfolge; im geprüften Auswahlpfad wurde kein absolut kalibrierter „ausreichend passend“-Schwellwert gefunden.
- **Warum kritisch:** Aus niedrigem Score, fehlender Query oder unavailable Embedding direkt Generation abzuleiten kann trotz vorhandener guter Clips unnötige Jobs erzeugen.
- **Counter-Proposal:** Eigene `CoverageDecision` mit `sufficient / insufficient / unknown`, Eignungsgründen und kalibriertem Profil; Unknown zuerst analysieren oder Nutzerentscheidung. Dauer/Handles/Loop/Retiming/Style/Kontinuität separat prüfen.
- **Prüfkriterium:** Gute Library mit fehlenden Embeddings löst keine ungeprüfte 180-Shot-Generation aus; klare Unterdeckung auf gelabeltem Holdout dagegen schon innerhalb Budget.

#### F38 — Pfadidentität und Generierungsidentität dürfen nicht zusammenfallen

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§17–18, 41, 59–61.
- **Beleg:** `media_repository.py:236–273` identifiziert Medien anhand Projekt und normalisiertem Pfad; gleicher Pfad kann einen vorhandenen Eintrag aktualisieren, geänderter Hash invalidiert Analysedaten.
- **Warum kritisch:** Wiederverwendung eines Outputnamens für Retry/Variante kann Herkunft und akzeptierte Analyse ersetzen. Contenthash identifiziert Bytes, nicht Auftrag, Projekt oder Outputslot.
- **Counter-Proposal:** Immutable jobspezifische Outputnamen; Artifact-/Attempt-/Slotidentität und zusätzlicher Unique-Importclaim. Identische Bytes dürfen durch getrennte Provenancebeziehungen mehreren Intents zugeordnet werden; keine Hashglobalisierung ohne Produktregel.
- **Prüfkriterium:** Zwei Varianten gleicher Outputbasename erzeugen getrennte unveränderte Artefakte; doppelter Callback desselben Attempts importiert genau einmal.

### 🟡 Medium

#### F25 — Neuer Output darf keine bereits akzeptierte Analyse still überschreiben

- **Rollen:** Domain Expert. **Plan:** §§9, 11, 12, 33, 66.
- **Was:** Vergleichsmodus braucht getrennte Resultrevisionen und einen bewussten aktiven Resultpointer. Ein zweiter Provider darf Native-Ergebnisse nicht als Nebenwirkung ersetzen.
- **Counter-Proposal:** Immutable Resultrecords; aktive Stageauswahl mit Versions-/Kontextprüfung; Degrade/Partial schreibt nur definierte Stages. Rollback wechselt Pointer, verliert keine neue Provenance.
- **Prüfkriterium:** Benchmark mit schlechterem Ergebnis ändert weder produktives Pacing noch Cache des aktiven Providers.

#### F26 — Cacheidentität ist größer als Datei/Modell/Workflowname

- **Rollen:** Analyst, Domain Expert. **Plan:** §§14, 59, 60.
- **Counter-Proposal:** Hash aus Sourceinhalt, Sourcebereich, Decoder-/Resampling-/Processorversion, API-Prompt + Manifest + ResultAdapter, vollständigem Modellbundle, aufgelösten Parametern/Seed und Resultschemaversion. Generation-Reuse und Analyse-Dedupe sind getrennte Regeln. Cacheentry erst nach Hash-/QCprüfung veröffentlicht.
- **Prüfkriterium:** Verändertes Hopsize-/Chunkoverlap-/LoRA-Profil invalidiert Cache; umbenanntes identisches Medium kann korrekt dedupliziert werden.

#### F27 — Framerate, Dauer und Schnittpunkte benötigen rationale Zeitrechnung

- **Rollen:** Domain Expert. **Plan:** §§8, 18, 21, 43–44, 62.
- **Counter-Proposal:** `fps_num/fps_den`, exakte Frames/PTS und Source-/Timelinezeit trennen; Endpunktkonvention definieren. Workflowconstraints wie Länge `n*k+c` validieren; generierten Überhang mit Handles trimmen. Kein Float-Runden pro Shot, das über Stunden driftet. Masteraudio explizit einzige Exportaudioquelle; generiertes Shot-Audio standardmäßig deaktiviert.
- **Prüfkriterium:** 29.97/23.976-FPS-Quellen über lange Timeline behalten A/V-Sync innerhalb freigegebener Grenze; Cut-Wunsch darf nicht unbemerkt Modellframelimit verletzen.

#### F28 — UI-Fortschritt darf weder Ausführung noch Importabschluss vortäuschen

- **Rollen:** Domain Expert. **Plan:** §§6, 25, 37, 53–55.
- **Beleg:** `backend/dependencies.py:385ff` besitzt begrenztes RAM-Eventjournal. `events_router.py:171–185` filtert Progress-Events; `PBStudio.UI/Services/SSEClient.cs:440ff` verwendet bekannte Typen und Abschlusslogik.
- **Counter-Proposal:** SSE für Anzeige, Jobstore für Wahrheit. Phasenstatus getrennt: queued/running/QC/import/analyse/ready. Unbekannter Fortschritt bleibt indeterminate. Nach Reconnect Jobliste abrufen; UI filtern nach Projekt und Jobrevision. Keine zusätzliche WPF-WebSocket-Wahrheit.
- **Prüfkriterium:** Sampling 100 % bei laufendem Decode/Import zeigt keinen „bereit“-Clip. Eventverlust wird durch Snapshot korrigiert.

#### F29 — „Rollback ohne DB-Migration“ ist kein allgemeiner Schemarollback

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§34, 66.
- **Beleg:** `data/schemas/media_json_schema.py:67–79` normalisiert auf aktuelle Schemafassung. Vorwärtskompatibilität beliebiger zukünftiger Blobfelder oder alter Binaries wurde nicht nachgewiesen.
- **Counter-Proposal:** Providerumschalten ohne weitere Migration ermöglichen; davon getrennt neue persistente Jobs/Provenance additiv migrieren. Unterstützte Reader-/Writer-Versionen, fehlende Felddefaults und Umgang mit unbekannten Feldern dokumentieren. Alte Appversion darf neue Provenance nicht still verwerfen. Restore nur konsistente Generation, niemals DB allein zurückspielen.
- **Prüfkriterium:** Neuer DB-Stand mit älterem unterstütztem Reader bewahrt neue Records oder wird verständlich fail-closed abgewiesen.

#### F30 — Settings und Fähigkeiten benötigen eindeutige Eigentümer und Refreshpolicy

- **Rollen:** Domain Expert. **Plan:** §§5, 50, 55.
- **Beleg:** Backend `ConfigManager` und WPF `SettingsService/PbSettings` besitzen getrennte Kontexte. Bestehende LLM-Registry akzeptiert LM Studio/Ollama; Analyseprovider sind eigener Fachbereich.
- **Counter-Proposal:** Backend autoritativ für Endpoint/Workflow-/Providerpolicy; WPF speichert Darstellung. Discovery TTL, invalidierbare Generation und Revalidate vor Submit. Kein `comfyui` in vorhandenes `ai.provider` einschmuggeln.
- **Prüfkriterium:** Endpointwechsel während Job A läuft ändert nicht A-Serverbindung; nächste Jobs verwenden neue Konfiguration. Offline-Provider blockiert keinen Appstart.

#### F31 — Feedbacklernen kann Selbstbestätigung statt Qualität lernen

- **Rollen:** Analyst, Senior Partner. **Plan:** §47.
- **Counter-Proposal:** Menschliche Bewertungen von automatischer QC trennen; Impressionen, Auswahlgrund und Exposurebias speichern. Holdoutbewertungen nicht als Training wiederverwenden. Workflow-/Promptversionen und Stilkontext mitführen; keine vermeintlich „guten Seeds“ global generalisieren.
- **Prüfkriterium:** Anbieter, der mehr Clips erzeugt, steigt nicht allein wegen höherer absoluten Positivzahl im Ranking.

#### F32 — Langform braucht Budget, Admission Control und Aufbewahrungsregeln

- **Rollen:** Senior Partner, Risk Officer. **Plan:** §§21, 40, 46, 58, 59.
- **Counter-Proposal:** Projektbudget für GPUzeit, RAM, Disk, Batchjobs, Varianten und Retries; nur begrenztes Dispatchfenster. Diskreserven vor Outputdecode/-download. Pin verwendeter Assets, Retention temporärer Latents/Stems/Diagnosen, keine Löschung verwendeter Varianten. ETA aus gemessenen vergleichbaren Profilen, ohne erfundene Stundenangaben.
- **Prüfkriterium:** Disk voll oder Budget erreicht stoppt neue Dispatches sauber; akzeptierte Timeline bleibt nutzbar.

#### F33 — Revisionsänderungen und Abhängigkeiten brauchen Invalidierung statt stiller Mutation

- **Rollen:** Domain Expert, Risk Officer. **Plan:** §§7, 18, 41–44, 50.
- **Counter-Proposal:** Jobs frieren Workflow-/Manifest-/Referenz-/Shotplanrevision ein. Update erstellt neue Revision, alte Jobs bleiben reproduzierbar. Retake/Upscale verändert nie Elternasset; Timelineänderung separat bestätigen. Dependency-Ausfall blockiert Nachfolger.
- **Prüfkriterium:** Workflowedit während 720-Shot-Batch bewirkt keinen Mix mehrerer unmarkierter Versionen; alte Ergebnisse sind über eigene Provenance auffindbar.

#### F34 — Abnahmeanforderungen und SDD-Artefakte fehlen für tatsächliche Implementierung

- **Rollen:** Engagement Manager, Synthesizer. **Plan:** §§64, 67–75, 79.
- **Was:** Der Text fordert spätere Arbeitspakete, besitzt selbst aber keine implementierbaren Requirement-IDs, Gates, konkreten Phasen-Specs oder vollständige task-Dateien.
- **Counter-Proposal:** Dieser Review bleibt Audit. Vor Lieferung Featureworkspace mit `spec.md → clarify → plan.md → tasks.md`; jedes Paket erhält Abhängigkeiten, Dateien, Tests, Akzeptanz und Rollback. `.completed`/`.qc-passed` nur nach tatsächlicher Implementierung/QC. Der angehängte Entwurf ist Vorschlag, kein künstlich passender Marker.
- **Prüfkriterium:** Kein Codingagent beginnt eine Implementierungsphase ohne freigegebenen Scope und bestehende Pflichtartefakte.

#### F39 — Whole-clip und Segmentvektoren benötigen verschiedene Identitäten

- **Rollen:** Domain Expert. **Plan:** §§15, 35, 42.
- **Beleg:** `video_router.py:2338–2342,2375–2377` poolt repräsentative Frames eines Clips; Publishing/Dedupe ist medienbezogen. Ein Whole-clip-Vektor beschreibt nicht automatisch jede kurze Teilstelle.
- **Counter-Proposal:** Granularität `asset / scene / window` plus Sourcebereich im Resultvertrag. Segmentindex erst mit passenden Mapping-/Dedupe-/Query-/Tombstoneänderungen, damit mehrere Segmentvektoren derselben Media-ID nicht als Dubletten entfernt werden.
- **Prüfkriterium:** Zwei Szenen eines Clips behalten getrennte passende Treffer und werden weder bei Import noch Reanalyse zusammengeworfen.

#### F40 — Cache-, Adapter- und Pacingvalidierung brauchen dieselbe fachliche Strenge

- **Rollen:** Domain Expert, Analyst. **Plan:** §§32–33, 59.
- **Beleg:** `audio_router.py:1086–1115` bewertet positive BPM und nichtleere Beats für Reuse; `pacing_router.py:300–316` prüft im gelesenen Preflight Typen/Listen. Stage-Reuse `audio_router.py:1131–1145` enthält keinen vollständigen externen Providerfingerprint.
- **Counter-Proposal:** Gemeinsamer semantischer Validator und immutable Analyse-Run-Identitäten; Stageabhängigkeiten auf konkrete Resultrevision binden. Ein Comfyadapter darf keine native Cacheidentität vortäuschen.
- **Prüfkriterium:** Negative BPM, inkonsistente Chunkzeiten oder falsche Sourcehashes dürfen über keinen der drei Übergabepfade als gültige Providerresultate in Pacing gelangen. Konkrete bestehende Fehlfreigabe wurde hier nicht ausgeführt.

### 🟢 Low

#### F35 — Begriff „Render Queue“ vermischt Generierung und finalen Export

- **Rollen:** Engagement Manager, Domain Expert. **Plan:** §§22, 24, 62.
- **Counter-Proposal:** Gemeinsame Produktionsjobansicht mit Typfiltern, separaten Fachzuständen und eindeutiger „Finalexport“-Aktion. Queueposition des Servers nicht als garantierte ETA darstellen.
- **Prüfkriterium:** Nutzer erkennt, ob „completed“ einen generierten Clip, eine Analyse oder finalen Export bezeichnet.

#### F36 — Statuszahlen im Plan sind Illustrationen, keine Baseline

- **Rollen:** Analyst. **Plan:** §§6, 12, 23, 40.
- **Counter-Proposal:** Zahlen wie 842 Nodes, 600 Shots, 342/720 und 139.70 BPM ausdrücklich als Beispiele belassen. Reale Werte aus Jobstore/Discovery und autorisierten Referenzen anzeigen.
- **Prüfkriterium:** Diagnoseexport enthält Messzeit, Serverbindung und Beweisniveau; kein illustrative Zahl wird als getestete Produktfähigkeit übernommen.

## Steel-Man Gegenposition

Die stärkste Alternative ist eine deutlich kleinere additive Generation-Bridge: PB analysiert, plant, sucht und rendert weiterhin nativ; ComfyUI liefert zunächst nur einzelne nachweislich brauchbare Videoassets. Damit wird die neue Fähigkeit nutzbar, ohne gleichzeitig die gesamte Analyseproviderarchitektur, Vektorräume und native Qualitätsbasis zu verändern. Die breite Vision bleibt ein späterer Ausbaupfad. Der Gegenentwurf gewinnt für den ersten Release, solange kein reproduzierbarer Qualitäts-/Betriebsvorteil einzelner ausgelagerter Analysen vorliegt.

Die stärkste Verteidigung des eingebrachten Plans lautet: Er fordert bereits getrennte Umgebungen, Native-Erhalt, Benchmarks, Provenance und schrittweise Migration und erteilt gerade keine Big-Bang-Implementierung. Viele Findings sind deshalb **zu schließende Designpflichten**, nicht Belege einer falschen Produktvision. Der Umfang wird erst problematisch, wenn der Anforderungskatalog als fertiger Implementierungsplan behandelt wird.

## Open Questions

Bereits bestätigt: externe ComfyUI-AMD-/ROCm-Ausnahme bei PB-internem DirectML; lokaler erster Scope, Cloud nur separat freigegeben. Siehe [Entscheidungsprotokoll](decisions.md).

1. Ist garantiert exklusiver GPUbetrieb gefordert, einschließlich manuell gestarteter Comfy- und LM-Studio/Hermes-Jobs, oder reicht beobachteter Shared-Modus? — Entscheidet über kooperativen Gate und Betriebsvertrag.
2. Bedeutet Pause zunächst Stop neuer Shots oder echter Samplercheckpoint nach Prozessneustart? — Zweiteres muss pro Workflow konkret belegt werden.
3. Welche vom Nutzer autorisierten Medien und menschlichen Qualitätsreferenzen bilden Golden Set und Holdout? — Ohne diese Daten keine Qualitätsrangliste, Providerablösung oder vollständige Medienabnahme.

## Recommendation

**GO-mit-Modifikation.**

- **Confidence:** HIGH für Quell-/Vertragsbefunde; lokale Generierungsqualifikation und zukünftige Providerqualität UNVERIFIZIERT.
- **Reversibilität:** Bridge additiv/two-way; persistente Schema-/Embeddingänderungen eigener Gate; keine Entfernung nativer Komponenten empfohlen.
- **Begründung:** Zuerst enges Generation-MVP mit dauerhaftem Job-/Importvertrag und sicherer Betriebsgrenze. Analyseauslagerung folgt erst nach unabhängigen Benchmarks.

Verbindliche Änderungen am Auftrag: Phasen 0/1 um Idempotenz/Recovery/Security/Benchmarkbasis erweitern; Job- und Importfundament vor automatischer Generierung; Shared-/Managed-GPU-Vertrag explizit; ein gepinntes Generationprofil zuerst; kein Analyse-AUTO ohne Qualifikation; keine beliebigen Embeddings im bestehenden Index.

Technischer Entwurf mit A–O, Lebenszyklus, Interfaces, Schemas und Arbeitspaketen: [architecture-and-delivery.md](architecture-and-delivery.md). Abschnittsweise Zuordnung des vollständigen Auftrags: [plan-coverage.md](plan-coverage.md).

### Primärquellen, abgerufen 2026-10-12

- [ComfyUI Server Routes](https://docs.comfy.org/development/comfyui-server/comms_routes): offizieller Routenüberblick; lokale installierte Quelle entscheidet über konkrete Version.
- [ComfyUI Server Messages](https://docs.comfy.org/development/comfyui-server/comms_messages): Progress-/Execution-Eventsemantik, insbesondere Nodeabschluss versus Workflowstatus.
- [Offizielles WebSocket-API-Beispiel](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example.py): API-Prompt und client-/promptbezogene Kommunikation.
- [Gepinnter Serverquelltext](https://github.com/Comfy-Org/ComfyUI/blob/3c1b7a17fdf239d35ce98cc777756f572d089795/server.py): lokal gelesene Revision und Cancel-/Queue-/Freememory-Routen.
- [Offizielle H3-Ankündigung](https://blog.comfy.org/p/minimax-h3-day-0-support-in-comfyui): H3 besitzt lokale Open-Weights-Unterstützung. Bericht nennt 42.5 GB Gesamtmodell-/Speicherfußabdruck der kleinsten optimierten Varianten mit Offloading; das ist weder eine reine VRAM-Anforderung noch ein RX-7800-XT-Produktnachweis.

### Änderungen dieser Prüfung

Im Repository nur neue Review-/Evidence-Dateien in diesem Verzeichnis. Auditwissen zusätzlich nach vorgegebenem Hirnprotokoll gespeichert; neue Vault-Learningnotiz, kein geänderter Produktstatus. Keine Statusmarker, Code-, Konfigurations-, Binär-, Projekt- oder Produktdatenänderungen. Kein Build und keine pytest-Vollsuite, weil die Integration nicht implementiert wurde. Notwendige spätere Real-Media-, GPU-, Recovery- und GUI-Gates sind im Delivery-Entwurf beschrieben.
