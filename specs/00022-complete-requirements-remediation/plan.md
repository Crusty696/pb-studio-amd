# Plan: OBJ-77 Vollstaendige Anforderungsremediation

**Status:** ACTIVE  
**Spec:** `specs/00022-complete-requirements-remediation/spec.md`  
**Baseline:** `specs/00022-complete-requirements-remediation/evidence/baseline.json`

## Leitentscheidungen

- Der unveraenderte Audit-Hash und ein Ledger mit genau 80 qualifizierten
  Befundschluesseln bilden die Abnahmebasis.
- Jede Wave startet nur vom gruenen Merge-SHA der vorherigen Wave.
- Externe Live-, Hardware- und Ground-Truth-Gates werden weder gemockt noch
  durch statische Tests ersetzt.
- Historische SDD-Artefakte werden nicht umgeschrieben. Compliance-Aufloesung
  erfolgt additiv und hashgebunden.
- Shared-Zones, zentrale API-Vertraege und Migrationen verbleiben beim Parent.
- Der dirty Ursprungsworktree bleibt unangetastet.

## Wave 0 - Foundation und Infrastruktur

1. OBJ-77-Workspace, Audit-Hash, Befundledger und qualifizierte IDs anlegen.
2. Hardware, LM Studio, reale Medien, Ground Truth und 4h-Fenster inventarisieren.
3. Python-, C#-, WPF-, OpenAPI-, GUI-, Daten- und Recovery-Baselines erfassen.
4. DirectML-Konstruktions- und Run-Pfade vollstaendig inventarisieren.
5. Historische SDD-Dateien hashen und vor stiller Aenderung schuetzen.

**Gate:** Baseline und Ressourcenstatus sind commitgebunden dokumentiert; kein
Produktcode ist geaendert. Fehlende Pflichtressourcen sperren die betroffene
Folgewave ehrlich.

## Wave 1 - Shared Contracts, Persistenz und Recovery

1. StageReceipt-V1 additiv in Pydantic, OpenAPI, Persistenz und C# abbilden.
2. Legacy-Receipts lesen und Status/Retry ausschliesslich aus angeforderten
   Stages ableiten.
3. Audio-/Video-Recovery, terminale Fehlerpersistenz und Partial-Reload
   atomar umsetzen.
4. FAISS und sqlite-vec mit gemeinsamem Owner-/Project-/Recovery-Vertrag
   produktiv verdrahten.
5. Migration zuerst auf Backupkopie dry-runnen, Crash injizieren, Restore und
   Rollback beweisen; Altdateien nicht loeschen.
6. Pending Timeline-Writes vor Save, Close, Wechsel und Exit awaiten.

**Gate:** fokussierte Tests, Migration, OpenAPI-/DTO-Paritaet, Restart/Resume
und WPF Release sind gruen. Eine Aenderung an `IApiClient.cs` wartet unmittelbar
vor dem Write auf die vorgeschriebene explizite Freigabe.

## Wave 2 - Audio

1. Downbeats, Takte, Mel/Depth, Sektionen, Key/Spectrum-Quellen, Hash-
   Invalidierung, Subtrack-Metadaten, Embeddings und Waveformwahrheit durch die
   vollstaendige Produktkette implementieren.
2. Atomare komprimierte Depth-Sidecars migrieren und Retry/Resume beweisen.
3. Dokumentationskonflikte nur mit aktuellem Code- und Testbeleg aufloesen.
4. Reale Long-Mix-, Alignment-, Depth- und Subtrack-KPIs mit Messreceipt
   ausfuehren.

**Gate:** Audio-Unit-, Router-, Persistenz-, WPF-, Hardkill- und Resume-Tests
sowie A-14..A-16 sind gruen. LOCKED Separator-Dateien bleiben unveraendert.

## Wave 3 - Video

1. FAISS-1152-Content-Suche und paginierte, recyclingfaehige Library mit
   Viewport-Thumbnail-Cancellation implementieren.
2. Extraktionsloops sequenziell dekodieren und RAFT-DirectML in den produktiven
   Scene-Pfad integrieren.
3. Stage-Nachforderung trotz frueherem IsAnalyzed erlauben.
4. Reales LM-Studio-Tagging, Degradation und Restart/Resume belegen.
5. Nach separatem Go den 10-Clip-Canary ausfuehren; vorher kein Bulk.

**Gate:** Suche/Reload, 10k-Library, Scene-Ground-Truth und T003 sind gruen;
T019 besitzt ein eigenes Go und 10/10 korrekte Receipts.

## Wave 4 - Pacing und Timeline

1. Auswahlprovenienz, Stem-Degradation und kanonisches min_cut_interval liefern.
2. Timeline-Collections und Ruler viewport-/pixelbasiert virtualisieren.
3. Drag/Trim/Snap/Preview/Persistenz/Reload vollstaendig abnehmen.
4. OBJ74-Rueckstaende Sensitivity, max/min interval, Hybridscore, reale Anker
   und Lifecycle in den konvergierten Tree uebernehmen.
5. Cut-Accuracy, Sync-Drift und Reglerwirkung gegen reale Ground Truth messen.

**Gate:** 1.000 Items bei 60 fps, <100 ms Feedback, <1 s Aktionen, keine
Freezes, kein Persistenzverlust und P-10..P-12 bestanden.

## Wave 5 - KI, Modelle und UI-Wahrheit

1. Einen effektiven Mode-/Override-Resolver und debounced Live-Sync mit
   UI-Rollback implementieren.
2. Manifest-/Hashbindung, Live-Inventar, Modellreceipts, Brain-Deep-Hook,
   Feedback-, Chat- und Projector-Vertraege beweisen.
3. Toten PauseCommand sowie DPI-, Slider-, Binding- und Accessibility-Luecken
   schliessen.
4. 14 Views bei 100/150/200 Prozent, High Contrast, Keyboard, Fokus und UIA
   pruefen; P95-Latenz messen.
5. DirectML auf realer AMD-, Intel- und NVIDIA-Hardware ausfuehren.

**Gate:** keine verbotenen Fallbacks, korrekte Provider-/Modellreceipts,
GUI-Matrix und Hardwarematrix gruen. K-11-Dateiloeschung wartet auf separate
Freigabe.

## Wave 6 - Resilienz, Governance und Release

1. Versionierten fail-closed 4h-Worker mit erzwungenen 4096 MB bereitstellen.
2. Recovery-/Owner-Testkontamination beseitigen und Reihenfolgevarianten testen.
3. Additive compliance.json-Dateien mit historischen Hashes erzeugen und
   qualifizierte Requirement-IDs repo-weit validieren.
4. README-Smokes, Brain-Status, GUI-Help, QC-Digest, Secret-, Dependency- und
   Iron-Rule-Gates schliessen.
5. Vollsuite, native C#-Tests, WPF Release, OpenAPI, GUI, KPI, DirectML-Matrix,
   LM Studio, 4h-Stress und Store-Integritaet ausfuehren.

**Gate:** kein offener Ledgerstatus; aktive Workspaces release-valid,
historische archive-valid; PR-Checks und Reviews gruen. Merge, Remote-SHA,
Release-Binary und lokaler Produktpfad sind real verifiziert.

## Ausfuehrungs- und Evidence-Vertrag

- Jede Task referenziert eine Ledgerzeile. Kein Sammelabschluss ersetzt die
  einzelne Evidence.
- Jeder KPI-Receipt enthaelt Medien-, Git-, Config-, Asset- und Hardwarehash,
  Versionen, Cold/Warm-Zustand, Rohdaten, Formel, Median, P95, Min/Max und
  Zeit-/Fehlerjournal.
- Nach jeder Wave: Python-Compile-Sweep, XML/XAML-Pruefung, fokussierte Tests,
  Domain-E2E, WPF Release bei C#-Aenderung, `git diff --check`, Dirty-/
  Truncation-Pruefung und Review.
- Test-Cleanup entfernt ausschliesslich manifestierte Testobjekte.
- `.completed` und `.qc-passed` bleiben gesperrt, solange eine Ledgerzeile oder
  ein vorgeschriebenes Release-Gate offen ist.
