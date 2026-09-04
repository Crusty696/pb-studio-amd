# Tracker-Fundament — 2026-09-04

## Ergebnis

T001/T002 implementiert, isoliert getestet. Kein Router-Aufrufer, keine
Produktivverdrahtung, kein Release-/QC-PASS.

## Asset-Provenienz

Offizieller Resolve:
https://huggingface.co/musetric/beat-this-onnx/resolve/45ba973e6c1fbee08a8a75b485e1c5adf45d2bc4/beat_this.onnx

Download nach `scratch/beat_this_official_45ba973.onnx` ist byteidentisch zum
vorhandenen `models/beat_this/beat_this.onnx`: 83 177 894 Bytes,
SHA-256 `3472a3957f25f4c3a2d68b46ee4b784e065a8ebd46132796c1a6bdd817229253`.
Die Modellkarte meldete abweichende alte Werte; tatsächliche Resolve-Bytes
sind die Evidenz. Originalmodell unverändert.

## DirectML-Gate

- Dynamischer Source-Graph scheitert mit
  `session.disable_cpu_ep_fallback=1`.
- Profiling mit CPU zugelassen zeigt Form-/Positionsoperationen auf CPU,
  einschließlich zweier Einsum-Operationen für Positionsfrequenzen.
- Feste Eingabeform `[1,1500,128]` ermöglicht Konstantenfaltung:
  striktes Gate bestanden, 97 profilierte DML-Kernel, 0 CPU-Kernel.
- Random-Input-Gegenprobe, Seed 42: maximale Logit-Abweichung
  `3.0994415283203125e-06` / `3.6954879760742188e-06`.
- Implementierung transformiert nur in RAM. Kurze Fenster erhalten ihre
  tatsächliche Form; kein künstliches Auffüllen auf 1500 Frames.
- Physischer Adapter live: AMD Radeon RX 7800 XT, DXGI-Index 0,
  LUID `0x00000000_0x0000f8c0` (nur für diesen Boot gültig).

## Tests

`PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_beat_this_tracker.py -q --tb=short --basetemp=.pytest_tmp_beat_this_20260904a`

**14 passed**, Exitcode 0, 34,67 s. Zwei bestehende Dependency-Warnungen
(`pkg_resources`, Starlette/httpx). Zusätzlich `py_compile` bestanden.

## Echte Musik, read-only

Material: Khainz — Excuse Me (Extended Mix), vorhandene AIFF-Datei.
Keine unabhängige menschliche Annotation; daher keine behauptete musikalische
Taktanfang-Genauigkeit.

| Probe | Beats | Downbeats | Ergebnis |
|---|---:|---:|---|
| 120 s ab 60 s | 261 | 66 | zwei Läufe exakt gleich; exakt gleiche Zeitpunkte wie Referenz-Prototyp |
| 5 s ab 60 s | 11 | 6 | 263-Frame-Session; exakt gleiche Zeitpunkte wie Referenz-Prototyp |
| ganze Datei, 281,43 s | 593 | 155 | zwei Läufe exakt gleich; Downbeats Teilmenge der Beats |

Ganzdatei: Median-Taktabstand 4,0278 Beatperioden, 90,91 % der Abstände auf
Vierer-Vielfachen. Dies belegt Rasterkonsistenz, nicht hörbare Eins-Position.
Die hohe Downbeat-Zahl der 5-s-Probe ist ausdrücklich kein Qualitäts-PASS.

## Daten- und Abschlussgrenze

DB vor/nach Tests: 8 Projekte, 713 Medien, `PRAGMA integrity_check = ok`.
`RUNTIME_DIRTY` jeweils nicht vorhanden. Backend/WPF nicht gestartet.
Vollsuite und WPF-Build nicht ausgeführt; das neue Modul hat keinen
Produktionsaufrufer. `patch.py` und `function_inventory.json` unverändert.

## Nächster Schritt

T003/T004: gemessene neuronale Downbeats gegen bestehendes Beat-Raster prüfen.
Keine pauschale Nächster-Beat-Zuordnung bei inkompatiblen Rastern. GPU-Lock,
Cancellation und Beats-Checkpoint müssen die gesamte Ergänzung umfassen.
Danach Persistenz/Pacing `downbeat_only`, Snare-Härtefall, Langmix, Vollsuite,
Release-Build und Live-QC. Keine Abschlussmarker vor diesen Nachweisen.
