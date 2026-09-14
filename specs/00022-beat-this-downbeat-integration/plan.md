# Plan: Beat-This-Downbeats im Produktpfad

**Status:** ACTIVE — native Beatzeiten freigegeben; Verifikation läuft
**Spec:** `specs/00022-beat-this-downbeat-integration/spec.md`

## Technischer Ansatz

1. Separaten `config/beat-this-assets.json`-Vertrag mit Revision, Größe,
   SHA-256 und MIT-Lizenz ergänzen. Das bestehende freigegebene DirectML-Bundle
   bleibt unverändert, weil sein Archiv Beat This nicht enthält.
2. `src/pb_studio/audio/beat_this_tracker.py` aus validiertem Dev-Prototyp
   extrahieren: Hash-Gate, exaktes Log-Mel-Frontend, Referenz-Chunking,
   Minimal-Postprocessing, singletonfähige DirectML-Session.
3. Nach Nutzerfreigabe native neuronale Beats/Downbeats validieren und als
   gemeinsame Ausgabe übernehmen. BPM aus dem neuen Raster berechnen,
   Legacy-BPM/Beatanzahl und Modellrevision festhalten. Gemeinsamen GPU-Lock
   nutzen und erst nach vollständiger Ergänzung den Beats-Checkpoint schreiben.
4. Downbeats markieren native Beats; kein Snapping und kein Anhängen doppelter
   Beats. Strengths für verfügbare Audiosamples neu messen; hinter dem
   Streaming-Snapshot neutral und ausdrücklich als ungemessen kennzeichnen.
   Persistenz-/API-/Pacing-Verträge bleiben unverändert.
5. Mit Unit-/Wiring-Tests, echtem Medienlauf, `downbeat_only`, Vollsuite und
   WPF-Release-Build verifizieren. Danach SDD-QC und Brain aktualisieren.

## Datenfluss

`AudioLibraryViewModel → /audio/analyze → audio_router → BeatThisTracker →`
`beats/downbeat_provenance → AppState/SQLite → Audio DTO → PacingService →`
`AdvancedPacingEngine → downbeat_only`

## Seiteneffekte und Grenzen

- DirectML teilt GPU mit Video-/Embedding-Modellen; Beat-Session bleibt lazy und
  läuft nur innerhalb bestehender serieller Audioanalyse.
- Lange Mixe dürfen nicht vollständig geladen werden. Tracker dekodiert und
  verarbeitet begrenzte Fenster; Segmentgrenzen deduplizieren Zeitpunkte.
- Separates Fourier-Beatgrid bleibt unabhängig; Produkt-BPM folgt dem
  ausgelieferten Raster. Keine Oktavkorrektur oder Dateinamen-BPM als Wahrheit.
- Das frühere Mapping-Gate bleibt nur als Diagnosewerkzeug erhalten:
  maximal 70 ms bzw. 15 % Beatperiode, mindestens 90 % Zuordnung,
  höchstens 8 % Tempoabweichung. Die Echtproben widerlegten diesen Produktweg.
- Äußere DSP-Arbeit verwendet einen eigenen begrenzten Thread-Pool;
  GPU-Inferenz den vorhandenen Async-GPU-Owner. So kann das Warten auf
  neuronale Ergebnisse dessen Executor nicht blockieren.
- Session-Referenzen in abgewickelten Exception-Frames werden vor Budget-
  und Lock-Freigabe geräumt; Abbruch bleibt vor dem Beats-Checkpoint.
- Statische Eingabeform pro tatsächlicher Fensterlänge entfernt CPU-Knoten;
  kurze Fenster nicht auf 1500 Frames auffüllen (würde Aufmerksamkeit ändern).
- `separator.py`, DB-Schema, Requirements-Lock und C#-API-Kontrakt bleiben
  unverändert.

## Verifikation

- Fokustests: Tracker, Asset-Trust, Router-Wiring, Persistenz, Pacing.
- Realer DML-Lauf zweimal auf Track plus Snare-Härtefall; Zeitpunkte identisch.
- DB-Zählstände und `integrity_check` vor/nach Runtime- und Testläufen.
- Vollsuite mit einmaligem eigenem `--basetemp`.
- WPF: `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release`.
- Live-QC: Backend sauber starten/beenden; auf Entfernung von `RUNTIME_DIRTY`
  warten.

## IRON-RULE-Prüfung

- AMD DirectML, keine CUDA-/ROCm-Nutzung.
- Beide ORT-Speicherflags deaktiviert.
- Python 3.11 / NumPy 1.26.4 / `PYTHONPATH=src`.
- Keine neue Abhängigkeit, Migration, Secret- oder Encoderänderung.
