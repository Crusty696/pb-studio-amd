# T002 — ausführbare Reihenfolge für die Regressionvorbereitung

Stand2026-10-13. Nutzerentscheid: Herkunft/Vornutzung nicht mehr genau erinnerlich; vorhandene Clips als Regressionstestmedien nutzen, unabhängigen Holdout offenlassen. Keine erneute Herkunftsfreigabe als Voraussetzung dieser Vorbereitung verlangen. Keine Generierung/GPUläufe. Dieses Paket definiert Testfälle und Nachweise, implementiert keinen Produktrunner.

## Festgelegter Bestand

Neun ausgewählte Quellen bleiben Development/Regression: V01–V06, A01–A03. Technische Originalpfade/Hashes/Streamdaten im reference-manifest.json. Drei Ausführungsgruppen, **keine unabhängigen Splits**:

1. Basis: V01ForestRave, V02Gemini-Ruinenclip, A01SummerDream, A02Klangkraft, A03Podcast04.
2. Varianten: V03Waterfall und V04Flame.
3. Stressfälle: V05Storm und V06Reflections.

Die15zusätzlich gefundenen unterschiedlichen Dateien sind jetzt Regressionreserve. Nicht automatisch zum aktiven Testumfang hinzufügen. Die historisch benannte Datei holdout-reservations.json bleibt erhalten, kennzeichnet aber ausdrücklich die neue Regressionreserve. Qualified Holdout0, unabhängige Validation0. Fehlende Erinnerung wird als unknown erhalten, nicht durch neue Befragung oder eine Scheinsicherheit ersetzt.

## Geplanter Ablauf

### A. Technischen Ausgangsstand festhalten

R01–R06 übernehmen ausschließlich die bereits ausgeführten Quell-/Decode-/Zeitbasis-/Referenzbindungsnachweise als historischen Ausgangsstand. Kein erneutes Abspielen und kein neuer PASS nur durch dieses Dokument. Vor einem späteren Vergleich Quellhash und relevante Software-/Konfigurationsidentität erneut kontrollieren. Geänderte Quelle ist neuer Testfall, kein stilles Update der Referenz.

R07 schützt unbekannte Farbmetadaten. Beobachtetes Fehlen ist bereits dokumentiert; zukünftige Validatorreaktion ist **noch nicht ausgeführt**. H.264/yuv420p und erfolgreiche Decodierung beweisen keine korrekte Farbinterpretation.

### B. Referenzen bewerten

Für R08 den Kontaktbogen ../t002-reference-preparation-2026-10-13/reference-sheet.jpg und sechs Einzelbilder verwenden. video-review.csv enthält vorbereitete sichtbare Fakten. Menschlicher Reviewer bewertet correct/incorrect/uncertain, korrigiert und ergänzt Name/Datum. Unsicheres nicht positiv zählen. Erst bestätigte Angaben als Referenzrevision einfrieren. Der vorhandene KI-Entwurf zählt nicht als menschliches Qualitätsurteil.

Für R09 die Originaldateien A01–A03 zunächst im Bereich01:00–01:30 anhören. audio-events.csv nimmt ausschließlich tatsächlich markierte Ereignisse auf. Zeitangaben immer ab Originaldateibeginn, nicht ab Wiedergabefenster; Trackdominanz nicht mit Crossfade-Mitte gleichsetzen. Fehlende Markierungen bleiben leer. Noch keine Hörabnahme ausgeführt. Ohne unabhängige musikalische Referenzen technische Prüfungen fortsetzen, aber Beat-/Downbeat-/Strukturqualität NOT EVALUATED lassen.

### C. Spätere Nativebaseline vorbereiten

R10/R11 benötigen eigenständigen begrenzten Laufauftrag, sofern Produkt-Appstart/Analyse/GPU berührt wird. Vorläufiges Profil in quality-profile-draft.json bindet Quellen und offene Metriken. Keine festgelegten Tempo-/F1-/VRAM-Prozentwerte erfinden. Schutzbudgets vor jedem späteren Lauf konkret festlegen; fachliche Grenzen nach Nativebasismessung, vor Kandidatentuning, versionieren und bestätigen.

Native/Rohprovider und Director/Brain getrennt messen. Kalt/warm/Ergebniscache getrennt halten, fehlende Beobachtbarkeit notieren. Laufzeit bis verwendbarem Ergebnis nach Stufen berichten; noch nicht implementierte Stufen nicht mit0 auffüllen. Erfolgreicher kleiner Lauf beweist weder maximale Medienlänge noch Ressourcenobergrenze.

R12: nur separate Evaluationsdateien verwenden, kein produktives Brainfeedback/Training. Testprojekt allein isoliert Brainzustände nicht. Der spätere Nachweis muss eventuelle unerwünschte Writes tatsächlich prüfen; bisher nur Vertrag vorbereitet.

### D. Bewertung der Regression

Technische Regressionsfälle prüfen identische Inputs und klar definierte Verträge. Vorher/Nachher mit unveränderten Quellen, Profilen und Cachemodus vergleichen. Neue fachliche Ausgabe kann richtig oder falsch sein; reine Gleichheit ist bei nichtdeterministischen Komponenten kein pauschales Qualitätskriterium. Bei stochastischen Outputs Seed/Modell/Runtime binden und erlaubte Unterschiede vorab definieren.

Ohne unabhängigen Holdout dürfen Ergebnisse „Regression auf bekanntem Bestand“ heißen, nicht allgemeine Verbesserung, Anbieterqualifikation oder Ablösungsfreigabe. Ein bestandener Regressionstest ersetzt weder menschliche Qualitätslabels noch G1 oder Gesamtproduktabnahme. T007 bleibt gesondert freizugebender Pilot mit offenen Runtime-/Policy-/Effective-Identitygates aus WelleB.

## Abbruch- und Ergebnisregeln

- Quellhashabweichung, falsche Stream-/Zeitbindung oder fehlender Pflichtbeleg: betroffenen Fall stoppen und Befund sichern.
- Unerwartete produktive Writes, Originaländerung, Netzwerk-/Generierungs-/GPUaktion: Lauf stoppen; keine automatische Reparatur, kein Retry.
- Fremde ComfyUI-Arbeit nicht stoppen/entladen. Dieser Vorbereitungsschritt benötigt keinen ComfyUI-Aufruf.
- Sensorunknown, fehlende Labels oder nicht ausgeführter Consumer: UNKNOWN/NOT EVALUATED/NOT RUN, niemals0 oder PASS.
- Numerische Qualitäts-/Ressourcengrenzen bleiben null, bis begründet festgelegt. Kein Grenzwert aus alten unabhängigen Spezifikationen übernehmen.

## Dateien und aktueller Nachweis

Bewertungsdurchgang vorbereitet am 19.10.2026: [einfache Bild-/Musikanleitung](../t002-human-review-2026-10-19/BEWERTUNG.md), sechs leere Bildzeilen und drei leere Musikzeilen. Erst eigene Beobachtung, danach Vergleich mit KI-Ausgaben; grobe Musikzeitpunkte sind noch keine präzisen Beatlabels. Alle neuen Bewertungszeilen stehen auf UNBEWERTET.

regression-cases.json:12konkrete Fälle mit Quellen, Erwartungen, Ausführungsklasse und Status. quality-profile-draft.json: offene Metrik-/Grenzwertfelder. result-template.json: leere Ergebnisvorlage, status NOT_RUN. Kein Testresultat simuliert. Der aktuelle Schritt verändert nur Plan-/Referenzdokumente; keine Originalmedien erneut decodiert, kein Test-/Produkt-App-/GPU-/Generierungslauf.

T002 bleibt insgesamt offen. Die unbekannte Clipvergangenheit blockiert die Regressionvorbereitung nicht mehr. Unabhängiger Holdout bewusst zurückgestellt; fachliche Referenzbestätigung, Nativebasismessung und Qualitätsgrenzen bleiben echte spätere Nachweise.

## Nachtrag 2026-10-13: begrenzte CPU-Funktionsprüfung

Nach dem obigen Vorbereitungsstand bestanden alle neun ausgewählten Quellen die isolierte Pfad-, Metadaten-, Frame- beziehungsweise Audiochunk-Prüfung mit PB-Studio-Funktionskörpern. Alle Original-SHA-256 blieben gleich. A03 M4A nutzte einen Librosa/audioread-Fallback mit Deprecation-Warnung. [Prüfbericht](../t002-cpu-check-2026-10-13/cpu-check-report.md). Die zwölf hier definierten Regressionsfälle wurden dadurch nicht als vollständige Produkt-/Qualitätsfälle ausgeführt; ihre Ergebnisvorlage bleibt `NOT_RUN`.

**Gegenprüfung 19.10.2026:** Der begrenzte PB-CPU-Lauf wurde für alle neun Quellen erneut erfolgreich ausgeführt. V02-Dublette und sechs lokale Referenzbild-Hashes wurden erneut bestätigt. Vollständiger Decode/PTS bleibt Beleg vom 13.10.2026; fachliche Fälle und Nativebaseline bleiben offen. [Technischer Gegenprüfbericht](technical-countercheck-2026-10-19.md).


## Menschliche Bildbewertungen erfasst (19.10.2026)

Sechs direkte Nutzerbeschreibungen V01–V06 in ../t002-human-review-2026-10-19/bildbewertungen.json mit Quell-/Bildhash, Zeitpunkt und unveränderten Beschreibungswortlauten gespeichert; bilder.csv enthält die normalisierte Erfassung. Geführte Bewertung bei sichtbarem vorherigem KI-Kontext, keine blinde Referenz und keine unabhängige Holdoutqualifikation. Bewegung und vermutete Szene/Identität bleiben Interpretationen; V06-Figurenzahl unsicher (6 oder 7). Keine automatische Bewertung der früheren KI-Entwürfe als correct/incorrect. R08: Einzelbildbeschreibungen erfasst, Modellvergleich offen. R09: Musikbewertung offen.


## Erste Hörbewertungen vollständig erfasst (19.10.2026)

A01–A03 im Originalfenster 60–90 s: regelmäßiger Beat gut mitklopfbar, keine Störungen gehört. A01/A03 kein deutlicher Wechsel; A02 ungefähr 70–80 s Stimmen, weniger Bass und leisere Stellen, genaue Wechselart und Grenzen unsicher. Originalantworten: ../t002-human-review-2026-10-19/musikbewertungen.json. R09 damit teilweise vorbereitet: keine präzisen Beat-/Downbeat-/Tonartlabels, keine Whole-File-Abnahme. Nächster fachlicher Schritt: kurzes Referenzfenster mit unabhängig markierten Schlägen und Unsicherheit vorbereiten, A02-Wechsel gezielt eingrenzen; dann begrenzten Native-Vergleich mit geprüfter Isolation und expliziten Analysestufen binden. T002 bleibt offen.


## GPU-Teilprüfung 2026-10-19

19.10.2026: T002 GPU-Teilprüfung freigegeben und ausgeführt: A01–A03 je 30 s zweimal über native Beat-This-Audioroute; V01–V06 je ein Bildpaar zweimal mit RAFT/DirectML. 18 Läufe, identische Wiederholungen; Original-SHA-256, Recovery-Marker, Konfiguration und DB/WAL/SHM unverändert. BeatNet-Fehler und auffällige Downbeat-Anzahlen A01/A03 offen. Keine Generierung, kein Produktstart, keine Migration. T002/Qualitätsbaseline/GUI-Abnahme offen. Beleg: specs/00037-comfyui-control-center/t002-gpu-check-2026-10-19/gpu-check-report.md. Lokal dokumentiert, nicht committed.
Die frühere GPU-Sperre dieser Vorbereitung wurde durch den ausdrücklichen Nutzerauftrag für diesen begrenzten Lauf aufgehoben. Generierung bleibt ausgeschlossen.


## Ursachenanalyse Audio 2026-10-19

19.10.2026: T002 Ursachenanalyse mit drei Spezialagenten. BeatNet offline/DBN-Abbruch in madmom ragged np.asarray reproduziert; isolierte Score-Auswahl-Gegenprobe erfolgreich (A03 68 Beats/34 Downbeats, Zweiermetrum). Beat-This-Rohlogits liefern bereits viele Downbeat-Spitzen; 90-s-Kontext beseitigt A01/A03-Auffälligkeit nicht. Frontend/80 Postprocess-Fälle/18 Chunklängen referenzkonform; Verbraucher prüfen keine musikalische Taktgüte. Produktcode/Pakete unverändert, Original-/Recovery-/DB-Hashes gleich. Beleg: specs/00037-comfyui-control-center/t002-audio-investigation-2026-10-19/investigation.md. T002/Qualitätsabnahme offen; lokal, nicht committed.


## BeatNet-Kompatibilitaetsfix 2026-10-19

19.10.2026: BeatNet-DBN-NumPy-Kompatibilitaetsfix in beiden Python-Aufrufern umgesetzt (lokaler Adapter, keine Packageaenderung). Nach Stromausfall/Neustart 18:54:22 erneut 54 Tests bestanden; A01–A03 je drei echte CPU-Analysen ohne Fallback, frische Wiederholungen identisch. Originale/Recovery/DB/Config/Library-Hashes gleich. Unabhaengiges Review mit16 Decodervergleichen ohne Blocker. Separater LSTM-Zustandsbefund bei Instanzwiederverwendung bleibt offen, ebenso musikalische Taktqualitaet/T002/WPF-Abnahme. T046/T047 abgeschlossen. Beleg: specs/00037-comfyui-control-center/t002-beatnet-fix-2026-10-19/qc-report.md. Quellen frisch ausgefuehrt; kein Produktneustart/EXE-Build, keine Generierung. Lokal, noch nicht committed.
