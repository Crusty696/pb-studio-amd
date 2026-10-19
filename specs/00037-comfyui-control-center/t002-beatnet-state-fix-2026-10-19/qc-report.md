# QC-Bericht: BeatNet-Dateizustand

## Ergebnis

Der Zustandsfehler bei wiederverwendeten BeatNet-Instanzen ist im freigegebenen PB-Dateipfad behoben. Vorher unterschieden sich zwei Analysen desselben 30-s-A01-Ausschnitts auf derselben Instanz an drei Beatzeitpunkten (bis 20 ms); Beleg: [pre-fix-reproduction.json](pre-fix-reproduction.json). Danach stimmen wiederverwendete Instanzen fuer alle A01–A03-Aufrufe exakt mit frischen Referenzinstanzen ueberein.

## Aenderung und Umfang

Ein gemeinsamer Wrapper in `src/pb_studio/audio/beatnet_compat.py` serialisiert jede Dateianalyse je Estimator. Er setzt LSTM hidden/cell vor und nach der Datei zurueck und stellt beim PF-Decoder dessen Anfangskopie wieder her, auch nach Fehlern. Online, offline und dateibasiertes realtime verwenden die Dateigrenze. Mikrofon-stream behaelt seine Historie. Weder NumPy-Zufallszustand noch installierte Pakete werden zurueckgesetzt/geaendert.

Alle drei BeatDetector-Dateipfade und AudioAnalyzer nutzen den Wrapper. Der Modellaufbau ist gegen gleichzeitige Erstinitialisierung geschuetzt und veroeffentlicht keinen teilweise initialisierten Estimator.

## Pruefung

- 63 gezielte Regressionstests bestanden, 15 Warnungen, Exit-Code 0; JUnit-Beleg: [pytest-results.xml](pytest-results.xml). Enthalten: DBN-Kompatibilitaet, Zustandsreset, A-B-A, Decoderfehler mit erfolgreichem Folgeaufruf, paralleler Zugriff, echter PF-Decoder-Klon samt RNG-Verhalten, Stream-Grenze und BeatNet-Aufrufer/Downbeat-Verbraucher.
- Echte CPU-Integration: vorhandene 30-s-Ausschnitte aus A01, A02, A03; kein GPU-Pfad. Eine gemeinsame offline/DBN-Instanz verarbeitet A01, A01, A02, A03, A01. Alle fuenf Beat- und Downbeat-Listen stimmen exakt mit der frischen Referenz der jeweiligen Quelle ueberein: A01 70/35, A02 70/35, A03 68/34.
- `get_downbeats` und `scan` liefern auf wiederholtem A01-Aufruf identische Resultate und stimmen mit der frischen Referenz ueberein. Derselbe AudioAnalyzer verarbeitet A01, A02, A03, danach nochmals A01; BPM/Beat-Ausgabe des wiederholten A01 ist identisch. A02/A03 durchlaufen ebenfalls dieselbe AudioAnalyzer-Instanz.
- Ein absichtlich ausgeloester Fehler direkt im Estimator hinterlaesst keinen Zustand: der folgende A01-Lauf entspricht exakt der frischen A01-Referenz. Fallback-Tripwires waren aktiv; kein Librosa-Fallback wurde verwendet.
- Original-SHA-256, die im Medienlauf erfassten Recovery-/Konfigurations-/Projekt-DB-/Installationsdateien und die drei lokalen Fixtures stimmen jeweils vor/nach ueberein. Vollstaendige Listen und Resultate: [real-media-state-reuse.json](real-media-state-reuse.json).
- `git diff --check` ohne Whitespacefehler. Unabhaengiger Gegenreview: [independent-review.md](independent-review.md).

## Abweichung bei einer fruehen Testausfuehrung

Eine erste, spaeter fehlgeschlagene fokussierte pytest-Ausfuehrung startete ohne eigenes `APPDATA`. Beim Teardown wurde deshalb das benutzerspezifische `%APPDATA%\PB_Studio\brain` geoeffnet; der BrainStore meldete beim Backup `database disk image is malformed`. Eine anschliessende rein lesende SQLite-Pruefung fand `weights.db` und `patterns.db` in Ordnung, `embedding_cache.db` jedoch fehlerhaft. Die Hauptdatei trug noch den Zeitstempel 03.10.2026; ein Vorher-Hash oder Vorher-Quick-Check war fuer diesen Pfad nicht erfasst. SQLite-SHM/WAL-Seitendateien trugen nach dem Test den Zeitstempel 19.10.2026. Damit kann ich keine Vorher/Nachher-Unveraendertheit dieses Brain-Caches belegen. Ich habe ihn nicht repariert, geloescht oder zurueckgespielt. Alle anschliessenden 29- und 63-Testlaeufe sowie die Medienmatrix liefen mit eigenem `APPDATA`, `LOCALAPPDATA` und Temp-Verzeichnis.

## Grenzen

Dies belegt den PB-Python-Quellpfad und isolierte CPU-Dateiverarbeitung. Es belegt weder das sichtbare Verhalten einer bereits laufenden WPF-Anwendung noch die musikalische Richtigkeit der Taktanfangslabels, Langdateien oder unabhaengigen Holdout-Qualitaet. Kein GUI-/Backendneustart, Build, Paketinstall, GPU-Lauf oder Generierung.

Die dateibezogenen Aufgaben T048/T049 sind abgeschlossen; Gesamt-T002 bleibt offen.
