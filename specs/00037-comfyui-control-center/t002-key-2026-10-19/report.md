# T002 CPU-Tonart-Teilprobe — 2026-10-20

## Änderung

Begrenzte, isolierte und lesende Probe gemäß `run-contract.md` ausgeführt. `probe.py` decodierte A01–A03 jeweils Originalsekunden 60–90 per FFmpeg nach RAM, mono 22050 Hz. Pro Quelle zwei `KeyDetector.detect_key`-Aufrufe und ein `detect_key_from_chroma` aus demselben aggregierten CQT-Chroma. Kein Produktcode, Backend, GUI, ComfyUI, GPU oder Modell wurde gestartet/geändert.

## Prüfung

Technischer Status PASS laut `results.json`: alle drei Quellen exakt 661500 Samples, durchgehend endlich. A01/A02/A03 lieferten je zweimal und im Chroma-Pfad `F# minor`; Laufzeiten der Analyse A01 14,49 s (Kaltstart), A02 0,33 s, A03 0,32 s. Keine Modulwarnung. Manifest-Hashes vor der Analyse bestätigt. Originaldateien, Config, vorhandene Katalog-/Brain-DB-Dateien und Recovery-Marker nachher hashgleich beziehungsweise weiterhin fehlend. `probe.py` per `py_compile` geprüft. Das Ergebnis ist ein Modul-/Wiederholbarkeitsnachweis, keine Tonart- oder Volltrack-Qualitätsabnahme.

## Offen

Unabhängige Tonartlabels fehlen; drei gleiche Ausgaben können korrekt oder systematisch falsch sein. T002 braucht weiterhin Beat-/Downbeat-Referenzen, Holdout, QualityProfile-Grenzen, Volltrack-/Stem-/Ressourcen- und API/GUI-Abnahme. T002 bleibt offen.
