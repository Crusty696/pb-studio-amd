# T002: Begrenzte PB-Studio-CPU-Prüfung (2026-10-13)

## Ergebnis

**9/9 ausgewählte Regressionstestmedien bestanden.** Die konkreten PB-Studio-Funktionen akzeptierten alle lokalen Dateipfade und erkannten die Medienmetadaten. Bei sechs Videos lieferten die PB-Funktionen jeweils drei Einzelbilder und vier Vorschaubilder in der erwarteten Auflösung. Bei drei Audiodateien lieferten sie jeweils einen 30-Sekunden-Ausschnitt ab Sekunde 60 als 44,1-kHz-Monosignal mit 1.323.000 endlichen Samples. PB-Metadaten für Videoauflösung, Codec, Bildrate und Dauer sowie für Audio-Samplerate, Kanäle und Dauer wurden gegen die zuvor direkt aus den Quellen erfassten FFprobe-Daten geprüft.

| Medien | Ergebnis | Einzelheit |
|---|---|---|
| V01–V06 | 6/6 bestanden | Software-FFmpeg-OpenCV, Hardwarebeschleunigung explizit `NONE`; je 3 Frames und 4 Vorschaubilder |
| A01–A03 | 3/3 bestanden | Je 30 Sekunden ab Sekunde 60; 1.323.000 Samples je Quelle |
| Originalschutz | 9/9 bestanden | Größe und Änderungszeit vor/nach Verarbeitung gleich; vollständige SHA-256-Hashes nach Verarbeitung entsprechen dem Referenzmanifest |

**Besonderheit A03:** SoundFile konnte die M4A-Datei nicht direkt lesen. Die in PB Studio vorhandene Librosa-Fallbackstrecke las den Abschnitt erfolgreich über `audioread`. Der Lauf meldete eine Deprecation-Warnung für diese Fallbackstrecke. Diese Warnung ist kein Fehler des aktuellen Tests, aber ein künftiges Kompatibilitätsrisiko.

## Nachweis und Grenze

Der Prüflauf führte die unveränderten Funktionskörper aus `backend/media_path_policy.py`, den Metadatenfunktionen der Audio-/Video-Router, `FrameGrabber` und `StreamingAudioAnalyzer._load_chunk` aus. Sie wurden isoliert per AST geladen, um Backend-Start, Router-Import und Seiteneffekte auf Projekt-/Recovery-Daten zu vermeiden. Die OpenCV-Videoöffnungen wurden auf FFmpeg mit `VIDEO_ACCELERATION_NONE` festgelegt und im Lauf geprüft. Die Audiofunktionen nutzten SoundFile beziehungsweise Librosa. Das belegt diese **begrenzte PB-CPU-Verarbeitung**, nicht den vollständigen PB-Studio-App-Import oder eine komplette Analysepipeline.

Es gab keine Generierung, keinen GPU-Lauf und keine Änderung an den Originalen. Nicht geprüft wurden: WPF-Oberfläche, API-Import und Projektkatalog, Beat-/Szenen-/Motion-/Embedding-/Caption-Analyse, Bild- und Tonqualität sowie unabhängige Holdout-Güte. Die ausgewählten Medien bleiben ausschließlich Regressionstestmedien; der unabhängige Holdout bleibt offen. Ein vollständiger Audioanalyse-Endpunkt wäre ohne zusätzliche Sicherung nicht CPU-begrenzt, weil seine Beaterkennung eine GPU-Strecke erreichen kann.

Maschinenlesbarer Beleg: [cpu-function-results.json](cpu-function-results.json). Reproduktionsskript: [verify_pb_cpu_functions.py](verify_pb_cpu_functions.py). Der Prüflauf benötigt `PYTHONPATH=src` und die bestehende Projekt-venv. Er schreibt den Beleg im T002-Verzeichnis und isolierte temporäre Laufzeitdaten; die Originalmedien werden nur gelesen. Die vorausgehende vollständige externe FFmpeg-Dekodierung ist im T002-Auswahlverzeichnis dokumentiert.
