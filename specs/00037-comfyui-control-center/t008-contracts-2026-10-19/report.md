# T008: isolierter Vertragsabschluss 2026-10-20

## Umsetzung

ComfyUI-Lauf T007 auf Nutzerwunsch uebersprungen. T008 besitzt jetzt ein additives, noch nicht produktiv verdrahtetes `providers/contracts.py`: ResultEnvelope/AnalysisRun/StageResult/EmbeddingPayload und pure `validate_result`/`validate_embedding`-Funktionen. Native-DSP kann ohne erfundenen Remoteauftrag/Modell laufen; Comfy braucht Attempt, Prompt, Workflow und effektive Promptidentitaet. Analyse braucht Sourcehash/-range; T2V darf ohne Quelle laufen. Origin-Generation bleibt separate Herkunft. Teilcaption bewahrt Nutzdaten, Grund und Coverage; fehlgeschlagene und valide leere Stage sind unterscheidbar. Absolute Sourcezeiten, Chunkoffsets, monotone/finite Reihen, Coverage und Motionkalibrierung werden geprueft. Embeddingraum und Prozessor-/Modell-/Vektoridentitaeten werden gebunden; gleiche Dimension genuegt nicht.

## Nachweis

Test zuerst: Import des fehlenden `providers`-Moduls schlug fehl. Spaeter zeigten zwei neue Gegenfaelle fehlende Teilabdeckung und fehlende Modellidentitaet; vor Fix 2 Fehler, nach Fix 11 gruen. Erweiterte Tests fuer Pflicht-Stages/Zeitidentitaet: Import von QualityProfile fehlte, nach Implementierung 13 gruen. Abschliessend 81 Tests und 27 Subtests aus Result-, Workflowbundle-, Policy- und Capabilityvertraegen bestanden; `py_compile` und `git diff --check` (mit CRLF-Hinweis) erfolgreich. Lauf mit isoliertem APPDATA/LOCALAPPDATA und `--noconftest`; kein Backendstart, kein Runtime-/Medienzugriff.

## Grenzen

`QualityProfile` haelt hier nur strukturelle Pflicht-Stages. Fachliche Grenzwerte, unabhängige Labels und Qualifikation aus T002 fehlen. Keine Persistenz, WPF-/API-/Pacingdurchleitung, echte Native-/Comfy-Analyse oder Endabnahme FP07. T008 ist fuer seinen isolierten Vertrag abgeschlossen; Produktdurchleitung/FP07-Endabnahme liegen in T031. T007/G1 bleiben offen. Keine Binaries, Startscripts oder produktive Runtime aktualisiert; neues Modul hat noch keinen Produktconsumer.

## Fortsetzung 2026-10-20

Plan-E-Felder schema_version, InputArtifact mit rationaler Zeitbasis, Output-IDs und Pflichtzeitstempel ergaenzt. Fehlerhafte Coverage und Stage-Abhaengigkeiten liefern ValidationIssues statt Absturz. Mehrdeutige Chunk-/Sourcezeitachsen werden abgewiesen. Aggregate-Status unterscheidet Pflicht- und optionale Stages; bekannte Native-Vision-Capabilities koennen ihre Modellpflicht nicht als DSP umgehen. Jeweils RED vor Fix, danach gezielter GREEN-Lauf. Abschliessende isolierte Regression: 86 Tests und 27 Subtests bestanden; `py_compile` und `git diff --check` bestanden (CRLF-Hinweis ohne Diff-Fehler). Keine echte ComfyUI-/Backend-/GUI-Abnahme.
