# Spezifikation: Beat-This-Downbeats im Produktpfad

**Status:** VERIFIED — technische QC bestanden; menschliche Hörprüfung separat
**Feature-Workspace:** `specs/00022-beat-this-downbeat-integration`
**Task-Bereich:** T001-T008

## Problem

PB Studio erzeugt Beats und ein BPM-Beatgrid, besitzt aber keine verlässlichen
Downbeats. Die frühere Akzentableitung wurde an echtem Material widerlegt.
`beat_trigger_mode="downbeat_only"` bleibt deshalb ohne nutzbare Produktdaten.

Der bestehende Dev-Prototyp für Beat This! `final0` läuft als ONNX auf
DirectML. An 35 realen Tracks stimmte sein Tempo in 34 Fällen mit einem
unabhängigen Fourier-Schiedsrichter überein; bei 29 Tracks bildeten die
Downbeats ein konsistentes 4/4-Raster. Der Prototyp ist nicht in Audioanalyse,
Persistenz oder Pacing verdrahtet.

## Objective

**OBJ-79:** PB Studio soll Beat- und Downbeat-Zeitpunkte aus einem
hashgebundenen Beat-This-ONNX-Asset berechnen, ehrlich persistieren und dem
Pacing-Modus `downbeat_only` bereitstellen.

## Scope

### Enthalten

- produktives Beat-This-Modul unter `src/pb_studio/audio/`
- separater SHA-256-, Revisions- und Lizenzvertrag der drei Modellartefakte
- DirectML-Session mit beiden vorgeschriebenen Speicherflags
- ein Fenster pro Inferenz zur Begrenzung des Attention-Speichers
- Audioanalyse-Verdrahtung für Non-Streaming- und Streaming-Dateien
- ehrliche Provenance und bestehende DB/API/UI-Persistenzkette
- Pacing-Gegenprobe für `downbeat_only`
- fokussierte Unit-, Wiring-, Asset- und echte Medien-Live-Tests

### Ausgeschlossen

- neue Python- oder NuGet-Abhängigkeiten
- CUDA, ROCm oder stiller CPU-ML-Fallback
- Änderung von `src/pb_studio/audio/separator.py`
- automatische Neuordnung bestehender Projekte oder Bestandsnachanalyse
- automatische Änderung gespeicherter Bestandsanalysen
- Ersatz des separaten Fourier-Beatgrids durch neuronale Daten
- Änderung des freigegebenen 3,28-GB-DirectML-Release-Bundles

## Functional Requirements

- **FR-402:** Ein Beat-This-Tracker lädt nur Modell, Konfiguration und
  Mel-Filterbank, wenn alle SHA-256-Werte dem versionierten Manifest entsprechen.
- **FR-403:** Der Tracker reproduziert den veröffentlichten Frontend-,
  Chunking- und Minimal-Postprocessing-Vertrag und liefert sortierte Beats und
  Downbeats in Sekunden.
- **FR-404:** Die Audioanalyse markiert erkannte Downbeats in `beats` mit
  `beat_type="downbeat"`, ohne Beat-Zeitpunkte doppelt zu zählen. Nach Freigabe
  vom 2026-09-04 ersetzt gültige Beat-This-Ausgabe das Legacy-Beat-Raster;
  BPM folgt weiterhin `60/median(diff(beats))`. Legacy-BPM, Legacy-Beatanzahl
  und Modellrevision werden als Provenance gespeichert.
- **FR-405:** `downbeat_provenance` unterscheidet `measured`, `unavailable` und
  `failed`; nur echte Beat-This-Ausgabe darf `measured` sein.
- **FR-406:** Streaming-Dateien werden fensterweise verarbeitet; das Modul lädt
  keine lange Datei vollständig in RAM.
- **FR-407:** Pacing übernimmt gemessene Downbeats und liefert bei
  `downbeat_only` eine nicht leere Triggerfolge, sofern Downbeats vorhanden sind.

## Operational Requirements

- **OR-361:** Originalmedien, Rekordbox-Daten, Datenbanken und Cache-Dateien
  bleiben unverändert, außer der ausdrücklich gestartete Live-Analyselauf
  schreibt sein normales Ergebnis in das aktive Testprojekt.
- **OR-362:** Fehlende oder hashfalsche Assets deaktivieren Beat This sichtbar;
  der bestehende librosa-Beatpfad bleibt nutzbar, Downbeats bleiben unavailable.
- **OR-363:** Modellinferenz nutzt `DmlExecutionProvider`; beide Session-Flags
  `enable_mem_pattern=False` und `enable_cpu_mem_arena=False` sind Pflicht.

## Test Requirements

- **TR-384:** Unit-Tests prüfen Hash-Gate, Frontend-Formen, Chunk-Grenzen,
  Peak-Deduplizierung, Sortierung und Fail-Closed-Verhalten.
- **TR-385:** Wiring-Tests prüfen Router → AppState → API → Pacing ohne
  synthetische Downbeat-Behauptung.
- **TR-386:** Ein echter Track und ein Snare-Härtefall werden deterministisch
  zweimal analysiert; Downbeat-Abstand und `downbeat_only`-Ergebnis werden
  dokumentiert.
- **TR-387:** Vollsuite und WPF-Release-Build laufen nach Implementierung.

## Success Criteria

- **SC-109:** Hashgebundenes Modell läuft auf DirectML und liefert bei echtem
  4/4-Material Downbeats mit Median-Abstand nahe vier Beatperioden.
- **SC-110:** Kein Downbeat wird aus bloßem Beatindex oder Akzentmuster erfunden.
- **SC-111:** Fehlendes/falsches Asset führt zu ehrlichem `unavailable`, nicht
  zu Analyseabbruch oder CPU-ML-Fallback.
- **SC-112:** Pacing-Modus `downbeat_only` ist mit gemessenen Daten nicht leer.

## Verifizierte Ausgangsdaten

Am 2026-09-04 ausdrücklich freigegeben: "Ja, Beatzeiten mit
nachvollziehbarer Provenance ersetzen". Drei reale 120-s-Fenster zeigten
nur 41-55 % Zuordnung der neuronalen Downbeats zum Legacy-Raster. Der
Produktpfad übernimmt deshalb gültige native Zeiten ohne Snapping. Fehler
oder unbrauchbare Ausgabe bewahren Legacy-Beats/BPM ohne Downbeat-Behauptung.

- offizieller Host: `musetric/beat-this-onnx`
- Revision: `45ba973e6c1fbee08a8a75b485e1c5adf45d2bc4`
- `beat_this.onnx`: `3472a3957f25f4c3a2d68b46ee4b784e065a8ebd46132796c1a6bdd817229253`
- `config.json`: `56cc961ddc588c57787c20c01ec6ab483b23af1049e65bd33d599a81803acd69`
- `mel-filterbank.bin`: `1ee975d96f44ccf2c3bfe37825c1c1f0b089f5703c7a12a84b1f0a3bce004533`
- Lizenz: MIT, übernommen von `CPJKU/beat_this`
