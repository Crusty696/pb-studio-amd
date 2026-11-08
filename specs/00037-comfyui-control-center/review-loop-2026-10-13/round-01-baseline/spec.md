# Specification: PB-Studio Control Center

Status: PLANUNG, 2026-10-13. Autorisiert ist die vollständige Masterplanerstellung, keine Implementierung. Neue Zielverträge sind [ABSICHT]; Quellenbelege im Review sind datierte [BEOBACHTUNG], keine Produktabnahme.

## Objective

**OBJ-1:** PB besitzt Projekte, Medien, Director, Timeline, DB/FAISS, QC und Finalexport; externe ComfyUI führt austauschbare Workflows aus. Additive Einführung, zuerst lokale manuelle Generation, später qualifizierte Analyseprovider und Longform-Automation.

## User Stories

### US1 — Lokale Generation (P1)
Nutzer verbindet getrennt installiertes ComfyUI, registriert einen geprüften Workflow und erzeugt einen Clip. Ausgabe wird geprüft und normal in PB importiert, analysiert und nutzbar. Fehlende Nodes/Modelle bleiben verständlich; PB funktioniert ohne Comfy.

### US2 — Sichere Produktion (P1)
Nutzer sieht Jobs, pausiert neue Dispatches, bricht ausschließlich eigene Jobs ab und setzt nach Neustart fort. Projektwechsel, Antwortverlust und Importcrash erzeugen keinen unbemerkten Doppelimport oder fremden Projektcommit.

### US3 — Erweiterbare Produktion (P2)
Nutzer nutzt Varianten/Postprocessing, vergleicht Native/Comfy pro Analysefunktion und verwendet qualifiziertes AUTO. Director trennt vorhandene geeignete Clips, echte Unterdeckung und unbekannte Abdeckung. Langform bleibt begrenzt und wiederaufnehmbar.

### US4 — Optionale Erweiterungen (P3)
Mehrere Embeddingräume, Generatorfeedback, Setupwizard, echte Samplercheckpoints sind getrennte Ausbaupakete mit eigenen Gates; sie sind keine Voraussetzung für lokalen P1-MVP.

## Confirmed Decisions

- **D01:** ComfyUI darf eigene externe AMD-/ROCm-Laufzeit nutzen. PB-interne ONNX-/GPU-Pfade bleiben DirectML; keine Umgebungsvermischung.
- **D02:** PB-Scope lokal. Cloud gehört ausschließlich zur separaten ComfyUI-Konfiguration; keine PB-Cloudfunktionen oder Ausbau-/Freigabegates.
- D01/D02 benötigen keine erneute Grundsatzbestätigung. Sie erlauben keine Installation, Migration oder Ausführung in dieser Planungsaufgabe.

## Functional Requirements

- **FR-001:** PB und Comfy sind unabhängig startfähige Anwendungen mit getrennten Umgebungen, Modellen, Dependencies und Updates.
- **FR-002:** Endpointbindung, automatische lokale Erkennung, manuelle URL, versionierte Discovery und verständliche Missing-/Unknownzustände.
- **FR-003:** Registry mit immutable API-Prompt/Manifestrevisionen, typed Parameter-/Outputmapping, Enable/Disable und optionalem UI-Graph; Editing in Comfy.
- **FR-004:** Capabilityprovider pro Funktion; explizite Wahl und qualifiziertes AUTO mit sichtbarem SelectionReceipt/Degradegrund.
- **FR-005:** Bestehende native Audio-/Video-/Longmixverfahren erhalten; Alternativen nur nach unabhängigen Qualitäts-/Betriebsbenchmarks.
- **FR-006:** Audio: Timing/Beats/Downbeats/Grid/Onsets/Drums/Energie/Loudness/Struktur/Key/Wechsel und langfristige Mixsegmente mit vollständiger Zeit-/Chunkherkunft.
- **FR-007:** Stems mindestens Drums/Bass/Other/Vocals, variable zusätzliche Rollen, Sample-/Kanal-/Delayvertrag und fingerprintgebundene Wiederverwendung.
- **FR-008:** Video: technische Daten/Szenen/Motion/Caption/Tags/Personen/Objekte/Style/Mood/Qualität/Embeddings; echte fehlende Fähigkeiten melden.
- **FR-009:** Generationfamilien T2V/I2V/V2V/Reference-to-Video unabhängig vom Modellnamen; ein lokales qualifiziertes Profil zuerst.
- **FR-010:** Generierte Assets werden normale Librarymedien mit Artifact-/Importreceipt, QC, Analyse, kompatiblen Embeddings und expliziter Director-Eignung.
- **FR-011:** Provenance aller Inputs/Outputs, effective Graph, Seeds, Modell-/Node-/Runtimeprofile; Regenerate und immutable verknüpfte Varianten.
- **FR-012:** Upscale/Interpolation/Reshot eigene Workflows/Derivate; Elternmedium bleibt erhalten, Zeitbasis und Kontext begrenzt.
- **FR-013:** Persistente Jobs/Attempts; Pause/Resume/Own-Cancel/Retry/Details/Priorität/Reorder für noch nicht dispatchte Arbeit.
- **FR-014:** Director Coverage sufficient/insufficient/unknown; revisionierter Asset-/Abhängigkeitsplan statt automatischem Job pro Timelinecut.
- **FR-015:** Longform mit bounded Dispatch, Budget und vorhandenen Shots; vollständiger PB-Export mit Originalmasteraudio und ohne ungewolltes Generationsaudio.
- **FR-016:** WPF-Status/Workflowlibrary/Jobs/Herkunftsfilter, redigierte Diagnose, Installationshilfe; optional Wizard und gesondertes Generatorfeedback.

## Technical Requirements

- **TR-001:** D01/D02 gelten; PB Python 3.11.x, NumPy 1.26.4, ONNX DirectML mit enable_mem_pattern=False und enable_cpu_mem_arena=False; PYTHONPATH=src; Tests/; FFmpeg AMF, LHM statt NVIDIAtools. Keine neue Dependency ungeprüft.
- **TR-002:** Comfytransport REST/WS/dateibasiert, im PB-Backend; WPF ausschließlich PB REST/SSE. APIprofil an tatsächlich gebundene Installation/Revision pinnen. Kommunikationsvertrag/Gwire: [communication-contract.md](communication-contract.md).
- **TR-003:** API-Prompt von UI-Graph unterscheiden; Graphreferenzen/Slots/Constraints validieren; keine globale Node-ID-Semantik, Titelmapping oder frei ausführbare Metadaten.
- **TR-004:** Discover → static compatible → smoke passed → qualified getrennt; Node-/Modellnamen kein Hash-/Ausführungsnachweis.
- **TR-005:** ResultEnvelope plus typisierte Stages mit Einheiten/Zeitbasis/Range/Coverage/Measured-Derived-Synthetic; gemeinsamer Validator für Cache/Adapter/Pacing.
- **TR-006:** Embeddingraum bindet Modell/Processor/Pooling/Norm/Dimension/Granularität; Native-Raum zuerst. Andere Räume niemals unter Native-Identität speichern.
- **TR-007:** Immutable Analyse-Runs und aktive Stagepointer; vollständiger Cachefingerprint, Vergleich verändert keine produktive Analyse.
- **TR-008:** Job, Attempt, Artifact, Media-ID, Importreceipt getrennt; dauerhafte Projektidentität additiv binden, aktuelle Root/Epoch vor Commit prüfen.
- **TR-009:** CAS-Transitions, Submit-Outbox, eigene UUID und submission_unknown; keine exactly-once Remotegarantie aus UUID, kein blindes Resubmit.
- **TR-010:** Idempotenter Import und separate ADD/UPDATE-Vektorsaga; Datei/SQLite/FAISS nicht als gemeinsame atomare Transaktion behandeln.
- **TR-011:** Lokales/Remote-Dateitransportprofil, Root-/Reparse-/Format-/Bytegrenzen, Hash-/Decodeprüfung, Zielstaging und atomare Veröffentlichung auf Zielvolume.
- **TR-012:** Rationale FPS/Frames/PTS/Samples und [start,end)-Bereiche; Modellframeconstraints/Handles/Trims, kein kumulativer Floatdrift.

## Operational Requirements

- **OR-001:** Externe GPUkoordination ausdrücklich observed_shared/managed_exclusive/remote_independent. Harte Exklusivität nur für vollständig kooperierenden Scope.
- **OR-002:** Eigene Jobs gezielt canceln; kein globales Queue-/Historyclear oder Interrupt. Free ist serverweit/asynchron und nur nach Ressourcenvertrag.
- **OR-003:** RAM/VRAM/Disk/GPUzeit/Batch-/Retrybudgets, Fairness und Backpressure; Unknownsensor/Leaseexpiry ist kein Freibeweis.
- **OR-004:** Getrennte Zustandsautomaten Job/Attempt/Import; Remote-Reconciliation und lokale Recoveryowner/-barriere/Lifecycle, kein Netzwerkjob im Snapshot warten.
- **OR-005:** Gepinnte vertrauenswürdige Pakete, Egress-/Credentialpolicy, URL-/Redirectprüfung. Deklaration ist keine technische Sperre; wirksame Graphidentität oder geprüftes frozen Profil vor Qualifikation. venv keine OS-Sandbox.
- **OR-006:** SSE Anzeige, Jobstore Wahrheit; Reconnectsnapshot, state_revision, projektgebundene UI; Sampling100% ist nicht Library-ready.
- **OR-007:** Technische QC, visuelle Qualität und menschliche Referenzen getrennt; bewusst dunkle/statische Clips mit profilgebundener Regel.
- **OR-008:** Retention/Archive/GC schützen referenzierte/aktive/Recoveryartefakte; Diagnose redigiert; Löschungen nur gesondert freigegeben.

## Recovery and Regression Requirements

- **RR-001:** Additive Migration auf isolierter Kopie; Binär-/Schemarollback getrennt von Providerfallback; konsistente Generation statt DB-only-Restore.
- **RR-002:** Responseverlust/Cancelrace/Projekt-/Endpoint-/Timelinewechsel und Crash an jeder Importgrenze müssen getestet werden.
- **RR-003:** Golden Set/Holdout und Qualityprofile vor Providerablösung/AUTO; fresh/warm/cache getrennt, keine erfundenen Referenzen/Prozentgrenzen.
- **RR-004:** Früh qualifizierter Hardware-/Medien-Smoke vor großem DB-/WPFausbau; integrierter native Userflow später separat.
- **RR-005:** Jeder Phase eigene Gates und Evidence; Tests/Build/GUI/Hardware/Real-Mediaqualität klar getrennt. Keine bestehenden Tests löschen, um Grün zu erzeugen.
- **RR-006:** SDD spec→clarify→plan→tasks→implement→QC; [ ]→[X] nur nach Nachweis; keine .completed/.qc-passed in dieser Planungsaufgabe.

## Clarification Gates

O01–O04 am 2026-10-13 bestätigt: observed_shared zuerst; Pause stoppt neue Dispatches, laufender Shot endet; PB-Schließen sichert Zustand, separate ComfyUI läuft weiter, danach Reconciliation. Abbruch-/obsolete Outputs gesichert, nicht automatisch verwendet.
O03: reale autorisierte Referenzen, Native-Baseline, getrennter Holdout; konkrete Medienfreigaben/Messwerte offen. O04: additive Erweiterung im bestehenden Katalog; konkrete SQL-/API- und Migrationsfreigaben offen. Details: [clarifications.md](clarifications.md). Keine Implementierungsfreigabe.

## Out of Scope

Jetzt: jede Produktimplementierung, App-/Workflowstart, Modell-/Nodeinstallation, DBmigration, Medienänderung oder Providerablösung. P1: kein Grapheditor, kein Analyse-AUTO, kein Multi-Embedding-Raum, kein Generatortraining, kein pauschaler Samplercheckpoint.

## Acceptance and Traceability

Planlieferung: alle 40 Findings und 82 Originalabschnitte auf Requirements/Tasks/Tests abgebildet; Dependencies azyklisch; alle Tasks offen; bestätigte Entscheidungen korrekt. Produktabnahme erst nach tatsächlicher Umsetzung und Gates in plan.md. tasks.md definiert Arbeitspakete; traceability.md ordnet F01–F40 und Originalabschnitte zu.
