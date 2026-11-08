# T002: CPU-Spektral- und Strukturpruefung

## Ausgefuehrter Umfang

A01-A03, Originalsekunden 60-90; vorhandenes FFmpeg decodiert mono 44100 Hz in RAM, Strukturpfad resampled auf 22050 Hz. Zwei Aufrufe je Quelle mit Produktmodulen SpectralAnalyzer und StructureAnalyzer. Module separat geladen, keine Audio-Package-Initialisierung, kein Router/Backend, kein Modell, keine GPU, keine Generierung. Eigene APPDATA/LOCALAPPDATA/TEMP/Numba-Cache-Verzeichnisse; produktiver Brainzustand nicht geoeffnet.

## Ergebnis

| Quelle | Lauf 1 / 2 (s) | Struktursegmente | Wiederholung |
|---|---|---|---|
| A01 | 2.202 / 0.884 | 2 | exakt identisch |
| A02 | 0.992 / 0.859 | 2 | exakt identisch |
| A03 | 0.813 / 0.837 | 1 | exakt identisch |

Alle acht Frequenzbaender enthalten endliche Werte; Zeitachsen monoton; Strukturintervalle zusammenhaengend und auf 30 s begrenzt. Keine protokollierten Modulwarnungen/-fehler, kein Struktur-/Spektralfallback beobachtet. Original-SHA-256 stimmen mit dem Manifest ueberein und vor/nach dem Lauf; erfasste Config-/Projekt-DB-/Brain-DB-/Recoverydateien hashgleich.

## A02: Vergleich mit der Nutzerbeobachtung

| Originalbereich | RMS | Bass-Magnitudenmittel 60-250 Hz |
|---|---|---|
| 60-70 s | 0.1508 | 233.41 |
| 70-80 s | 0.0497 | 17.88 |
| 80-90 s | 0.2892 | 325.01 |

70-80 s ist in diesen aggregierten Messwerten leiser und bassaermer als beide Nachbarfenster. Das stuetzt die Nutzerbeobachtung dieses Ausschnitts. Stimmen, eine exakte Wechselgrenze oder eine Drop-/Breakdown-Klassifikation sind nicht bestaetigt.

## Grenzen und weitere Befunde

A01 meldet trotz Nutzerbeobachtung "kein deutlicher Wechsel" eine Strukturgrenze bei Originalsekunde 73.05; A02 eine Grenze bei 72.59. A03 bleibt ein Segment. Das sind Algorithmusausgaben, keine bestaetigten musikalischen Grenzen. Labels wie intro am Ausschnittanfang beschreiben keine nachgewiesene Volltrackposition. confidence=0.7 ist im Produkt fest vorgegeben und kein gemessener Guetenachweis. Keine Grenzwertanpassung oder Produktaenderung aus diesen drei Ausschnitten.

Zeitwerte umfassen beide Module, ohne Decode/Resampling/Hashing; erste und zweite Messung sind keine qualifizierten cold/warm-Kohorten. RSS ist ein 100-ms-Stichprobenmaximum des Prozesses waehrend Analyse, kein garantierter Peak. Router/GUI/Persistenz, Volltracks, Tonart, Stems und Beat-/Downbeatgenauigkeit bleiben ungeprueft. T051 technisch abgeschlossen, Gesamt-T002 offen.

## Reproduktion und Belege

probe.py fuehrt denselben begrenzten Lauf mit neuer privater scratch-Wurzel aus; results.json bindet Produktcode-/Quellhashes, Rohresultathashes, Messwerte und Schutzdateien. Rohkurven bleiben im dort angegebenen scratch-Verzeichnis.
