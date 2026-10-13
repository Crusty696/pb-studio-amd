# T002 — Referenzmarken und Holdout-Vorbereitung

2026-10-13. Vorbereitung ausgeführt, keine Generierung/GPU-/Produktläufe. Originale unverändert. T002 bleibt offen.

## Geliefert

1. Vollständiger Textabgleich aller424inventarisierten Medien gegen durchsuchbare Repositoryquellen in docs/specs/scripts/Tests/src/backend. Spec00037 ausgeschlossen, damit neue Auswahlakten sich nicht selbst als historische Nutzung belegen. Endgültig mit --no-ignore und --hidden; initiale Standardsuche hatte ignorierte alte Nachweise ausgelassen und wurde verworfen. Positivkontrolle V01 findet früheren Indexeintrag. Kein Zugriff auf produktive DB, private Nutzungsprotokolle oder externe Trainingshistorien.
2.397/416Videonamen oder Hashes haben historische Texthinweise. Ein Treffer ist nicht automatisch ein Ausführungsbeleg; die bereits vertieft geprüften fünf ausgewählten Clips haben konkrete Import-/Analyse-/Captionnachweise.19Videopfade ohne Treffer entsprechen16verschiedenen SHA256. Nach Ausschluss der bereits verwendeten V02-Dublettfamilie verbleiben17Pfade/15verschiedene Kandidaten. Diese sind **reserviert, nicht als unbelastet qualifiziert**. Beziehungen zur Gemini-Entwicklungsdatei und anderen früher verwendeten Clips derselben Sammlung bleiben ungeklärt. Keine automatische Splitfreigabe.
3. Sechs exakte Referenzframes: V01/V03–V06 Frame150 bei5s, V02 Frame360 bei15s. CPUextraktion per nullbasiertem Frameindex; Zeitzuordnung durch zuvor vollständig geprüfte regelmäßige PTS. Sourcehash, Streameintrag und Framebildhash gebunden. Kontaktbogen reference-sheet.jpg; individuelle PNGs daneben. **Publikationsgrenze 2026-10-13:** JPG/PNG-Bildbelege bleiben auf ausdrücklichen Nutzerwunsch lokal; das öffentliche GitHub-Repository enthält nur Metadaten und Hashbelege, keine Bildausschnitte.
4. Sechs Inhaltsentwürfe nach unmittelbarer visueller Betrachtung, unabhängig von aktueller PB-Ausgabe erstellt: sichtbare Figuren/Szene/Lichtobjekte; Unsicherheiten ausdrücklich ausgewiesen. **AI-Vorannotation, keine menschlich bestätigte Groundtruth**, keine Blindbewertung garantiert, kein Urteil über den gesamten Clip oder dessen Bewegungsqualität. Reviewformular video-review.csv bleibt unbewertet.
5. Audioarbeitsblatt für A01–A03 vorbereitet, jeweils zuerst **01:00–01:30 ab Originaldateibeginn**, innerhalb des geprüften01:00–03:00-Bereichs. Zweck: überschaubare erste manuelle Beat-/Taktannotation. Keine behaupteten Drops oder Trackwechsel. audio-events.csv enthält nur Spaltenköpfe; keine erfundenen Ereignisse. Beat, erster Taktschlag, Abschnittswechsel, Überblendungsintervall und Zeitpunkt der Trackdominanz sind getrennte Labelarten.

## Keine übernommene Scheinreferenz

Der Fachprüfer fand für A01–A03 in den geprüften historischen Mess-/Spec00035-Quellen keine ausgefüllten menschlichen Beat-/Downbeat-/Abschnittsmarken. t003-referenz-vorlage.boundaries.txt enthält Kommentare/Beispiele. Alte Phasenkontraste sind algorithmisch. Externe rekordbox-Werte waren ausdrücklich nicht menschlich geprüft und betreffen andere konstruierte Referenzmixe. Deren Crossfade-Mitte ist nicht dieselbe Definition wie der Zeitpunkt, ab dem ein neuer Track führt. Labels deshalb nicht vermischen oder auf ausgewählte Quellen übertragen. Es wurde keine neue Audiohöranalyse durchgeführt.

## So wird aus dem Entwurf eine Referenz

- Bilder: In video-review.csv je Frame correct/incorrect/uncertain, Korrektur, Reviewer und Datum erfassen. Die Originalzeit und der Hash bleiben gebunden. Erst bestätigte Fakten in akzeptierte Labels übernehmen; unklare Inhalte nicht erzwingen. Ein Einzelbild deckt keine zeitliche Qualität ab.
- Audio: Originaldatei an den genannten Quellzeiten anhören, Beats/Taktanfänge unabhängig markieren und Unsicherheiten notieren. Keine PB-Vorhersagen vorlegen. Fensterrelative Zeiten nur mit ausdrücklichem Offset in Quellsekunden umrechnen. Übergänge erst in tatsächlich gefundenen unabhängigen Referenzbereichen markieren; ein30s-Fenster muss keinen Übergang enthalten.
- Holdout: Offene Nutzerfrage betrifft frühere PB-/Prompt-/Modellbewertung und gemeinsame Ausgangsfigur/Bildreferenz/Serie der Gemini-Clips. Fehlende Texthinweise allein reichen nicht. Bei gemeinsamer Familie mit Development alle betroffenen Varianten dort belassen; für echte unabhängige Abnahme andere belegbar unbelastete Familien suchen. Aktuell keinerlei qualifizierter Audio-Holdout. Keine erneute Frage nach bereits gespeicherten Medienwurzeln.

## Schutz und Nachweis

Effektive Splits unverändert: neun Development-/Regressionquellen, Validation/Holdout leer.15reservierte Kandidaten nicht für Training/Tuning/Kandidatengenerierung verwenden. Vorherige technische Sichtung ist dokumentierte Auswahlprüfung, kein Qualitäts-PASS. Keine produktiven Brainfeedback-/Trainingswrites.

Sechs diesmal gelesene Originalvideos erneut vollständig gehasht: identisch zu inventarisierten Hashes. Größe/mtime aller424Medien unverändert. Alle JSONs, Source-/Framebindungen, eindeutige Kandidaten und Nullbestand akzeptierter Labels geprüft; validation.json. Unabhängiger Read-only-Reviewer bestätigte Zählungen, Audiozeitbasis und Beweisgrenzen; keine verbleibende konkrete Korrektur. Seine Gegenprüfung war keine erneute Bildbewertung. Keine neue GPU-/Nativebaseline oder Gesamtproduktabnahme.

Ältere selection-validation.json bindet die damalige Referenzmanifestrevision. Das Referenzmanifest wurde jetzt ausschließlich um reference_preparation-Verweise erweitert; aktueller Dokumentstand wird durch evidence-manifest.json in diesem Ordner gebunden.

## Nutzerergänzung zur Herkunft

2026-10-13: „das sind von mir generierte video mit gemini  sora und civitai“. Damit als Nutzerauskunft bestätigt: selbst erzeugte Videos, die drei Angebote kollektiv benannt. Keine dateiweise Modell-/Generatorzuordnung und keine Aussage zur bisherigen PB-Nutzung, Promptoptimierung oder gemeinsamen Bild-/Figuren-/Serienvorlage. Holdout bleibt unqualifiziert; keine neue Generierungsfreigabe.

## Überholte Rückfrage / aktueller Entscheid

Nutzer kennt Vorbenutzung/Familien nicht mehr genau und erlaubt Regression mit bestehenden Clips. Die oben dokumentierte Herkunftsrückfrage ist damit erledigt, kein weiterer Klärungszwang für Regression.15Kandidaten als Regressionreserve umklassifiziert; Holdout bewusst offen. Fortsetzung: ../t002-regression-preparation-2026-10-13/regression-protocol.md.
