# T002: vollstaendige CPU-Szenenpruefung V01-V06

## Ausgefuehrter Umfang

Sechs Originalclips je zweimal vollstaendig durch SceneDetector verarbeitet; separates ffprobe -count_frames als Framezahl-Gegencheck. OpenCV-Backend explizit gebunden, CAP_PROP_HW_ACCELERATION=VIDEO_ACCELERATION_NONE beobachtet; OpenCL deaktiviert. Keine Inferenzmodelle/GPU, kein Router/Backend/GUI, keine Generierung. APPDATA/LOCALAPPDATA/TEMP isoliert; alle geoeffneten Probe-Videohandles am Laufende explizit freigegeben.

## Ergebnis

| Quelle | Dauer (s) | Frames je Lauf | Szenen |
|---|---|---|---|
| V01 | 10.000 | 300 | 1 |
| V02 | 30.000 | 720 | 1 |
| V03 | 10.000 | 300 | 1 |
| V04 | 10.000 | 300 | 1 |
| V05 | 10.000 | 300 | 1 |
| V06 | 10.000 | 300 | 1 |

Alle zwoelf Laeufe decodierten die von ffprobe gezaehlten Frames; null vom Decoder gemeldete Decodefehler. Wiederholungen liefern exakt gleiche Zeitintervalle. Original-SHA-256 manifestkonform und vor/nach identisch; erfasste Config-/Projekt-DB-/Brain-DB-/Recoverydateien hashgleich.

## Beweisgrenzen

Bei allen sechs Clips fand der Detektor keine innere Schnittgrenze; der Produktpfad gab deshalb warnend den gesamten Clip als eine Szene zurueck. Dieser dokumentierte No-cut-Ersatzpfad ist kein Nachweis richtiger Szenenerkennung. Referenz-Schnittzeitpunkte fehlen; Praezision/Recall der Szenengrenzen NOT EVALUATED. Keine Aussage zu Figuren, Tanzen, Captionqualitaet, SigLIP, RAFT ueber den Gesamtclip oder sichtbarer Produktfunktion. Keine PTS-/Farbqualifikation allein aus Framezahlen ableiten. T052 technisch abgeschlossen; T002 bleibt offen.

## Belege

probe.py und results.json enthalten Laufvertrag, Code-/Quellhashes, Decodezaehler, Zeitintervalle und Schutzdateien. Die gemessenen Sekunden umfassen nur SceneDetector-Aufruf und Handlefreigabe, nicht Vorprobe und Hashing.
