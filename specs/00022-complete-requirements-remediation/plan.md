# Plan: OBJ-77 Vollstaendige Anforderungsremediation

**Status:** ACTIVE  
**Spec:** `specs/00022-complete-requirements-remediation/spec.md`  
**Baseline:** `specs/00022-complete-requirements-remediation/evidence/baseline.json`

## Leitentscheidungen

- Der unveraenderte Audit-Hash und ein Ledger mit genau 80 qualifizierten
  Befundschluesseln bilden die Abnahmebasis.
- Jede Wave startet nur vom gruenen lokalen AMD-Merge-SHA der vorherigen Wave;
  die vier explizit deferred externen Release-Gates blockieren diese lokalen
  Wave-Uebergaenge nicht.
- Die Umsetzung folgt AMD-first: Zuerst werden alle nicht-externen Befunde und
  die vollstaendige lokale Produktkette auf der vorhandenen RX 7800 XT
  geschlossen. Intel/NVIDIA-DirectML, das LM-Studio-Wartungsfenster und der
  echte 4h-Lauf folgen erst als abschliessende externe Release-Abnahme.
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

**Gate:** Baseline und Ressourcenstatus sind commitgebunden dokumentiert;
Ground Truth ist hashgebunden registriert; kein Produktcode ist geaendert. Ein
ehrlicher Exit 1 des Reservierungsvalidators fuer Intel, NVIDIA,
LM-Studio-Wartungsfenster und 4h-Fenster ist als `deferred` dokumentiert und
blockiert weder den Wave-0-Merge noch die lokalen AMD-Waves. Er blockiert erst
die abschliessende externe Release-Abnahme. OR-363 bleibt unveraendert.

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
4. Tagging-, Degradations- und Restart/Resume-Vertraege lokal auf der
   vorhandenen AMD-Hardware implementieren und mit nicht-invasiven Tests
   absichern; das Hermes-Wartungsfenster bleibt bis zur Endabnahme deferred.
5. Canary-Vertrag und Bulk-Sperre implementieren; die wartungsfenstergebundene
   Live-Ausfuehrung folgt erst nach allen lokalen AMD-Gates.

**Lokales AMD-Gate:** Suche/Reload, 10k-Library, Scene-Ground-Truth sowie alle
nicht-invasiv lokal pruefbaren Video- und Resume-Vertraege sind gruen. T003 und
T019 bleiben bis zur abschliessenden LM-Studio-Abnahme offen; T019 besitzt
weiterhin ein eigenes Go.

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
5. DirectML und die vollstaendige KI-/UI-Kette auf der vorhandenen RX 7800 XT
   ausfuehren; Intel und NVIDIA werden erst in der Endabnahme geprueft.

**Lokales AMD-Gate:** keine verbotenen Fallbacks, korrekte lokale
Provider-/Modellreceipts, GUI-Matrix und RX-7800-XT-Nachweis gruen.
K-11-Dateiloeschung wartet auf separate Freigabe; K-16 bleibt bis zur
abschliessenden Intel-/NVIDIA-Matrix offen.

## Wave 6 - Resilienz, Governance und Release

1. Nicht-externe Resilienzvertraege auf der RX 7800 XT schliessen. Der echte
   4h-Worker samt Canary, Soak und Release-Lauf ist nicht Teil dieses lokalen
   Gates und beginnt erst in der externen Endabnahme.
2. Recovery-/Owner-Testkontamination beseitigen und Reihenfolgevarianten testen.
3. Additive compliance.json-Dateien mit historischen Hashes erzeugen und
   qualifizierte Requirement-IDs repo-weit validieren.
4. README-Smokes, Brain-Status, GUI-Help, QC-Digest, Secret-, Dependency- und
   Iron-Rule-Gates schliessen.
5. Vollsuite, native C#-Tests, WPF Release, OpenAPI, GUI, lokale KPIs und
   Store-Integritaet auf der vorhandenen AMD-Hardware ausfuehren.

**Lokales AMD-Gate:** alle nicht-externen Ledgerzeilen sind geschlossen; aktive
Workspaces sind fuer die externe Endabnahme valid, historische archive-valid;
lokale Tests, Reviews und der Produktpfad auf der RX 7800 XT sind gruen. Ein
Release bleibt bis zur nachfolgenden externen Endabnahme gesperrt.

## Abschliessende externe Release-Abnahme

Diese Phase startet erst, wenn alle Wave-1-bis-Wave-6-Gates fuer nicht-externe
Arbeit und die lokale RX-7800-XT-Produktkette gruen sind.

1. Den identischen Candidate-SHA auf realer AMD-, Intel- und
   NVIDIA-DirectML-Hardware pruefen.
2. Das autorisierte LM-Studio/Hermes-Wartungsfenster reversibel ausfuehren,
   T003 belegen und T019 erst nach seinem separaten Go starten.
3. Canary und Soak des versionierten 4096-MB-Stressworkers ausfuehren und
   danach den echten mindestens 14.400 Sekunden dauernden Lauf abschliessen.
4. Alle externen Receipts commit-, config-, asset-, medien- und
   hardwaregebunden validieren und im finalen Closure-Manifest einzeln listen.

**Finales Release-Gate:** Intel-/NVIDIA-Matrix, LM-Studio-Live-Nachweise,
Hermes-Restore und echter 4h-Stress sind gruen; OR-363 ist damit erfuellt; kein
Ledgerstatus ist offen; PR-Checks und Reviews sind gruen. Erst danach folgen
Merge, Remote-SHA, Release-Binary und erneute lokale Produktpfadpruefung.

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
