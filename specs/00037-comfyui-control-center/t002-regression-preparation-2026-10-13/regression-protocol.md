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

regression-cases.json:12konkrete Fälle mit Quellen, Erwartungen, Ausführungsklasse und Status. quality-profile-draft.json: offene Metrik-/Grenzwertfelder. result-template.json: leere Ergebnisvorlage, status NOT_RUN. Kein Testresultat simuliert. Der aktuelle Schritt verändert nur Plan-/Referenzdokumente; keine Originalmedien erneut decodiert, kein Test-/Produkt-App-/GPU-/Generierungslauf.

T002 bleibt insgesamt offen. Die unbekannte Clipvergangenheit blockiert die Regressionvorbereitung nicht mehr. Unabhängiger Holdout bewusst zurückgestellt; fachliche Referenzbestätigung, Nativebasismessung und Qualitätsgrenzen bleiben echte spätere Nachweise.

## Nachtrag 2026-10-13: begrenzte CPU-Funktionsprüfung

Nach dem obigen Vorbereitungsstand bestanden alle neun ausgewählten Quellen die isolierte Pfad-, Metadaten-, Frame- beziehungsweise Audiochunk-Prüfung mit PB-Studio-Funktionskörpern. Alle Original-SHA-256 blieben gleich. A03 M4A nutzte einen Librosa/audioread-Fallback mit Deprecation-Warnung. [Prüfbericht](../t002-cpu-check-2026-10-13/cpu-check-report.md). Die zwölf hier definierten Regressionsfälle wurden dadurch nicht als vollständige Produkt-/Qualitätsfälle ausgeführt; ihre Ergebnisvorlage bleibt `NOT_RUN`.
