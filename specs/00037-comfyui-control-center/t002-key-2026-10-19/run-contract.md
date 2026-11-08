# T002 CPU-Tonart: begrenzter Laufvertrag

Status: 2026-10-20 als begrenzte CPU-Teilprobe ausgefuehrt, nachdem der Nutzer die autonome Umsetzung aller offenen Arbeiten ausser ComfyUI-Laeufen verlangte. Messbeleg: `results.json`; fachliche Tonartqualitaet bleibt offen.

## Frage
Liefert der vorhandene KeyDetector auf A01-A03 (Originalsekunden 60-90) reproduzierbare, gueltige Ergebnisse? Stimmen Arraypfad und derselbe aggregierte CQT-Chroma-Eingang ueberein?

## Umfang und Schutz
Vorhandene Originale nur lesen; FFmpeg nach RAM, mono 22050 Hz, 30 Sekunden. Zwei Arrayaufrufe und ein Chromaaufruf je Quelle. Direkter Modulimport ohne Packageinitialisierung, Backend oder BrainStore. Eigene APPDATA/LOCALAPPDATA/TEMP/Numba-Verzeichnisse. Keine GPU, Generierung, Installation oder Produktcodeaenderung. Original-/Config-/DB-/Recoveryhashes vorher/nachher vergleichen.

## Abbruch und Auswertung
Decode-Timeout 90 Sekunden; gesamte Probe maximal 300 Sekunden. Abbruch bei Manifestabweichung, unvollstaendigem/nichtendlichem Audio, Modulwarnung, Unknown, ungleichen Wiederholungen/Pfadergebnissen oder Schutzdateiaenderung. Messzeit nur Tonartanalyse; keine garantierten Ressourcenpeaks. Ohne unabhaengige Tonartlabels keine musikalische Genauigkeit behaupten. Keine Volltrack-/Streaming-/GUI-Abnahme. T002 bleibt offen.
