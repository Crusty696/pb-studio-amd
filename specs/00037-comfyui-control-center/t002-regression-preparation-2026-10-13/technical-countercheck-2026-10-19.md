# T002 — Technische Gegenprüfung vom 19.10.2026

## Aktuell ausgeführt

- Der vorhandene isolierte PB-CPU-Prüfer lief erneut mit `PYTHONPATH=src`: 9/9 ausgewählte Quellen bestanden Pfad- und Metadatenprüfung, sechs Videos lieferten je drei Frames und vier Vorschaubilder, drei Audiodateien je 30 Sekunden mit 1.323.000 endlichen 44,1-kHz-Monosamples. Die vollständigen SHA-256-Hashes der neun Originale stimmten nach dem Lauf mit dem Referenzmanifest überein. OpenCV öffnete die Videos über FFmpeg mit `VIDEO_ACCELERATION_NONE`; kein PB-Backend- oder WPF-Start.
- V02 und die lokal vorhandene Datei `gemini_generated_video_741eaffa.mp4` haben weiterhin denselben vollständigen SHA-256-Hash.
- Die sechs **nur lokal gespeicherten** Referenz-PNGs V01–V06 sind vorhanden; ihre vollständigen Datei-Hashes stimmen mit `reference-frames.json` überein. Diese Bilder sind nicht im öffentlichen Git-Repository.
- A03 M4A wurde erneut nur über den Librosa/audioread-Fallback gelesen. Dessen Deprecation-Warnung besteht fort.

## Beleggrenzen

Der heutige Lauf wiederholt **keine** vollständige Video-Dekodierung, keine PTS-Reihe und keine 120-Sekunden-Audio-FFmpeg-Probe. R02–R04 besitzen dafür ältere Auswahlbelege vom 13.10.2026; die heutige PB-Prüfung ergänzt sie um begrenzte CPU-Funktionsverarbeitung. Die sechs Bild-Hashes beweisen Dateiintegrität, kein fachliches Bildlabel. Die Dublettenprüfung wurde aktuell für das V02-Paar wiederholt, nicht für alle acht Paare des Gesamtinventars.

R07 und R12 brauchen spätere Vertrags-/Integrationstests. R08 und R09 brauchen menschliche Bild- beziehungsweise Hörbewertungen. R10 und R11 brauchen einen gesondert begrenzten Native-Analyse-/Messlauf; dafür liegt keine neue Freigabe vor. T002, unabhängiger Holdout und allgemeine Qualitätsbehauptungen bleiben offen. Originale, Produktdaten und ComfyUI-Aufträge wurden nicht geändert; keine Generierung und kein GPU-Lauf.

## Nachweise

- `../t002-cpu-check-2026-10-13/cpu-function-results.json` — beim erneuten Lauf vom 19.10.2026 aktualisierter Maschinenbeleg; das JSON selbst enthält kein Laufdatum.
- `../reference-manifest.json` — neun gepinnte Original-Hashes und V02-Familienhinweis.
- `../t002-reference-preparation-2026-10-13/reference-frames.json` — sechs Bild-Hashes; PNG-Dateien nur lokal.
- `../t002-selection-2026-10-13/selected-verification.json` — vollständige Decode-/PTS-/Audio-Proben vom 13.10.2026.
