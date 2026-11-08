# T054 — Caption-Prompt und Tagfilter, 2026-10-19

## Ergebnis

Belegte Filterfehler behoben und Prompt gezielt verbessert. 101 gezielte Tests bestanden; zusaetzlich 84 echte Bildinferenz-Aufrufe einschliesslich verworfener Varianten und zwei abschliessender Wiederholungsmatrizen. Die letzten zwoelf Aufrufe verwenden den endgueltigen Produktcode, dessen Hash in validation.json mit final-results.json abgeglichen ist. Keine allgemeine Bildqualitaetsfreigabe: V03-Wasserfall und Personenzahl sowie V02-Orts-/Torform bleiben fehlerhaft.

## Durchgefuehrte Aenderungen

1. Gemeinsames Budget CAPTION_TAG_LIMIT=12 in dependency-freiem pb_studio/caption_contract.py. Parser, Clip-Merge und alternativer all_tags-Zweig verwenden dasselbe Budget. Explizite kleinere Limits bleiben erhalten. Schema, C#-Records, Persistenz und ItemsSource akzeptieren bereits variable Taglisten; keine API-Schemaaenderung.
2. Verworfene Hautfarbenbeschreibungen werden nicht durch den abschliessenden Wort-Fallback wieder eingefuehrt. Bei Prosa werden betroffene komma-getrennte Klauseln vor der Wortzerlegung verworfen. Konservativer Preis: andere Informationen in derselben verworfenen Klausel koennen mit entfallen; saubere andere Klauseln bleiben erhalten. Nichtfarbliche Beschreibungen wie taetowierte Haut bleiben erlaubt.
3. Zahlen vor Personen bleiben bis zur Normalisierung erhalten. Sowohl `5 menschen` als auch die real beobachtete Antwort `Menschen (5)` werden zu `gruppe von menschen`. Kleine Personenzahlen und Objektzahlen werden nicht pauschal ersetzt. Das verhindert unzulaessig praezise grosse Kopfzahlen; es beweist keine korrekte Personenerkennung.
4. Nummerierungsvarianten ohne Abstand bleiben lesbar; lange Prosa mit Tags-Praefix behaelt den bisherigen Keyword-Pfad. Beide Regressionen wurden im Gegenreview entdeckt und vor dem Abschluss behoben.
5. Neuer Prompt: keine Mindestanzahl aufzufuellender Tags, Personen nicht voraussetzen, konkrete Objekte/Umgebung/Licht priorisieren, keine Handlung aus einer Pose behaupten. Keine bildspezifischen erwarteten Antworten im Prompt. Verwendet den exakt getesteten Kandidaten 2 (ab2-prompt.txt).

## Promptvergleich und Gegenpruefung

Sechs identische private Referenzbilder; Hashes stimmen mit Nutzerbewertungen ueberein. Gemma 4 E4B, Kontext4096, Temperatur0.2, vorgeladenes Modell am lokalen LM-Studio-Endpunkt. PB-Tagcache vor jedem Vergleich geleert; genau ein echter Clientaufruf pro Datensatz. Keine Chat-Historie angehaengt. Erst zwei A/B-Runden mit je zwei Aufrufen pro Arm/Bild, Reihenfolge pro Bild alternierend ABBA/BAAB. Dritter Kandidat separat zweimal je Bild getestet. Anschliessend zweimal je Bild auf Produktstand und nach Reviewkorrektur erneut zweimal je Bild. Entwicklungsreferenzen, kein Holdout; Variantenwahl ist explorativ und keine statistische Genauigkeitsmessung.

| Runde | Aufrufe | Entscheidung |
|---|---:|---|
| ab1-results.json | 24 | Kandidat1 verworfen: weniger falsche Gruppen, aber sichtbare Figuren/Mehrzahl teilweise ausgelassen. |
| ab2-results.json | 24 | Kandidat2 begrenzt uebernommen: V02/V05 vier falsche Gruppenangaben des Vergleichsarms entfernt; V04 Figur/Feuer und V05 Blitz erhalten. |
| candidate3-results.json | 12 | Kandidat3 verworfen: Personen-zuerst-Variante bringt falsche Gruppen V02/V05 zurueck. |
| first-postfix-results.json | 12 | Erster echter Lauf mit Parser/Promptfix, inklusive nativer Mergefunktion. |
| final-results.json | 12 | Endgueltiger Code nach Review: technische Antworten und Merge fuer alle Bilder, Schutzdateien gleich, Modell entladen. |

Tradeoffs von Kandidat2 ausdruecklich: V03 statt zweimal zwei Frauen nur einmal explizite Zweizahl; andere Antwort Frau/Frau dedupliziert zu Frau. Doppelte Woerter werden nicht als gezahlte Personen interpretiert. V02 im A/B-Paar zweimal Innenraum, waehrend das zugehoerige Baselinepaar diese falsche Angabe nicht enthielt. Die Verringerung erfundener Gruppen und unbelegter Handlungen rechtfertigt die begrenzte Verbesserung; diese anderen Fehler sind nicht behoben.

## Endgueltige Bildresultate

| Bild | Nachgewiesene Verbesserung / verbleibende Grenze |
|---|---|
| V01 | Figur, Wald, Baeume und Leuchten; kein Tanzen als sichere Handlung. Geometrische Formen weiterhin ungenau, Stimmung trotz Prompt teilweise vorhanden. |
| V02 | Keine erfundene Personengruppe. Architektur/Eingang/Stein und Leuchten vorhanden. Torbogen statt rechteckigem Tor bleibt falsch; Ranken fehlen. |
| V03 | Wasser/Nebel/Frauen, aber Zweizahl nur in einem von zwei Schlusslaeufen. Wasserfall fehlt; Baeume/Himmel weiterhin unbelegt. |
| V04 | Person, Steinmauer/Bodenplatten, einmal Flammen; anderer Lauf ungenaues Kerzenlicht. Keine sichere vollstaendige Fackelerkennung. |
| V05 | Beide Schlusslaeufe nennen Blitz und Mensch, keine erfundene Gruppe. |
| V06 | Gruppe, Mond/Wasser und Reflexion; keine praezise grosse Zahl nach Filter. Farbdetails variieren. |

## Tests, Reviews und Schutz

- 31 neue Regressionstests; gesamter relevanter Cluster 101 PASS, sechs bekannte Abhaengigkeits-Deprecation-Warnungen. Wrapper, Merge, Status, Provider, Pipeline und Fortschritt abgedeckt. Erst rote Reproduktionen, danach identische Faelle gruen; Logs im Ordner pytest-*.txt.
- Alle zwoelf T053-Rohantworten erneut durch Parser und Merge: sechs zuvor verlorene elfte Tags nun erhalten, einschliesslich Blitzschlag. Beleg t053-raw-replay.json. Erhalten bedeutet nicht visuell wahr: etwa Innenraum bleibt eine falsche Modellbehauptung.
- Parallele unabhaengige Rollen: Filter-/Calleranalyse, Testautor, visuelle Qualitaetsgegenpruefung. Alle sechs Bilder tatsaechlich durch Qualitaetsreview angesehen. Finale Codegegenpruefung ohne weitere belegte Fehler. Kein GPU-Parallelbetrieb der Tests.
- Saemtliche fuenf Medienlaufserien bestaetigen Original-/Config-/erfasste DB-/Recoveryhashes unveraendert. Tests mit eigenem APPDATA/LOCALAPPDATA/TEMP/PBSTUDIO_PROJECT_DIR, kein Produkt-Lifespan. Eigene Analysemodelle jeweils entladen; abschliessendes API-Inventar not-loaded. Keine Generierung, Installation, Migration oder Aenderung laufender ComfyUI-Auftraege.
- Promptcache war bereits promptabhaengig; kein Cachefix behauptet. Keine globale Modell-/Providerkonfiguration geaendert. Qwen-Override bleibt im aktuellen Inventar nicht verfuegbar; dieses Ergebnis betrifft Gemma.

## Deployment und offene Abnahme

Python-Produktdateien im vorhandenen Checkout aktualisiert und in frischem Prozess mit echten Bildern ausgefuehrt. Kein laufender PB-Backendprozess am Standardport8765 gefunden; keiner beendet/neugestartet. Keine C#-/Schemaaenderung, keine neuen Binaries oder Installation erforderlich. Kein GUI-Start und keine WPF-/API-/Persistenz-Gesamtabnahme behauptet. Private Bilder bleiben lokal; Pruefordner enthaelt Text-/JSON-Belege.

T054 als begrenzte Reparatur/Pruefung abgeschlossen. T002/G1/Gesamt-T045 offen. Naechster gezielter Nachweis: V03-Hintergrund und Personenanzahl sowie V02-Ortsangaben gesondert untersuchen, danach weitere Zeitpunkte/Clip-Aggregation und SigLIP. Keine pauschale Retagging-Aktion vorhandener Projekte.
