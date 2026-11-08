# T055/T056 — Bildinhalt, Transport und SigLIP

## Auftrag und Nachweisgrenze

V02/V03-Erkennungsfehler untersuchen und belegte Ursachen beheben; sechs Referenzvideos technisch gegenpruefen. Originale, bestehende Projekte und laufende Auftraege schuetzen. Keine Generierung, Installation, Migration oder pauschales Retagging. Ergebnisse gelten fuer Entwicklungs-/Regressionsmedien, nicht fuer einen unabhaengigen Holdout. T002 und Produktabnahme bleiben offen.

## Caption-Befunde

T053/T054 verwendeten private 480x270-Vorschaubilder. Sie belegen den nativen Wrapper, aber nicht dessen Eingang mit Originalaufloesung. Der Produktclient begrenzt ndarray-Eingaben auf maximal768 Pixel Kantenlaenge und JPEG85; die produktive Bilduebergabe muss deshalb getrennt von der Vorschau geprueft werden. Kein RGB/BGR-Vertauschungsfehler belegt. V02 Original1280x720 wird768x432, V03 Original854x480 wird768x431. V01 hat nativ720x480; seine480x270-Vorschau besitzt ein anderes Seitenverhaeltnis.

| Gegenpruefung | Echte Caption-Aufrufe | Ergebnis |
|---|---:|---|
| Vorschau/nativ mal JPEG/PNG, V02/V03 jeweils zweimal | 16 | Native Aufloesung verbessert die Zweizahl in V03. PNG beseitigt den fehlenden Wasserfall nicht. V02 Architektur-/Ortsfehler variieren weiterhin. |
| Natives JPEG, reasoning_effort=none gegen weggelassen, V02/V03 zweimal | 8 | Mehr Rechenzeit ohne belastbare Beseitigung des Fehlers; eine Antwort verliert Personen. Keine globale Reasoning-Umstellung gerechtfertigt. |
| Sechs Originalclips, je drei Zeitpunkte bei25/50/75Prozent, Standard-JPEG-Pfad | 18 | 18 echte Antworten. V03 erkennt am spaeten Zeitpunkt Wasserfall; native Clip-Mergefunktion erhaelt dieses Tag. Der mittlere Einzelbildfehler bleibt bestehen. |

Belege: transport-results.json, reasoning-results.json, native-multipoint-results.json samt gleichnamigen Probe-Skripten. results.json/probe.py enthalten denselben urspruenglichen Transportversuch, keine zusaetzlichen16 Aufrufe. Gesamt42 neue Caption-Aufrufe, getrennt von den84 T054-Aufrufen.

Modell: vorhandenes Gemma4 E4B, lokale LM-Studio-Vulkan-Runtime. Konfiguriertes Qwen ist nicht installiert; kein Download oder Providerwechsel. Die Fehlbegriffe stehen bereits in Rohantworten; kein neuer Parserverlust und keine abgeschnittene Antwort als Ursache belegt. Transport-/Reasoning-Varianten werden deshalb nicht global ins Produkt uebernommen. Der neutrale T054-Prompt bleibt bestehen.

V03-Clipmerge enthaelt unter anderem zwei Frauen, Wasser, Nebel und Wasserfall, aber auch unbelegten Wald. V02-Clipmerge enthaelt Eingang, Portal, Steinstruktur und Pflanze, daneben fragliche Hand/Statue/Kreatur. Nur mittlere Zeitpunkte besitzen Nutzerreferenzen; spaete/fruehe Details sind keine nachtraeglich erfundenen Groundtruth-Labels. Weder Torform noch Hintergrundvollstaendigkeit sind allgemein geloest. Die drei Testzeitpunkte sind kein Nachweis einer vollstaendigen nativen Router-Samplingstrategie.

## Bestaetigter SigLIP-Codefehler

Die bisherige Vorverarbeitung nutzte CLIP-Mittelwerte/Standardabweichungen. Das versionierte lokale SigLIP-Processorartefakt models/siglip_tokenizer/preprocessor_config.json verlangt dagegen RGB,384x384 BICUBIC, Skalierung1/255 und mean/std je0.5. Der ONNX-Eingang fuehrt ohne interne Normalisierung in die Patch-Convolution. Der Modellhash entspricht dem registrierten Artefakt:

`863380e4e628cca0d61d4170bdb1401a66ce030080d7a956f90ebe42e040969e`

src/pb_studio/ai/siglip_wrapper.py korrigiert mean/std; der Batchpfad verwendet dieselbe Vorverarbeitung wie Einzelbilder. Sieben CPU-Tests vergleichen unabhaengig gegen den installierten Hugging-Face-PIL-Processor mit lokaler Konfiguration: Schwarz/Weiss, RGB-Muster, RGBA/Graustufen, Einzel-/Batchpfad. Alle sieben mit alten Konstanten rot, mit Korrektur gruen. Der PIL-Processor ist der passende Oracle fuer PBs PIL-Resize; der alternative Torchvision-Resize rundet einzelne Pixel anders und wurde nicht durch eine aufgeweichte Toleranz kaschiert.

SigLIP erstellt Bildvektoren; es ist nicht der Caption-Generator. Dieser Fix beweist keine Beseitigung des Gemma-Wasserfall-/Torfehlers.

## Vektorraum und Bestandsschutz

T056 fuehrt die korrigierte Identitaet siglip_vision/onnx-dml-v2 ein. Gleiche Dimension1152 bedeutet keine Kompatibilitaet mit v1. Produktions-/Cachemetadaten, Wiederverwendung, Persistenz/Reload, Such- und Backfillpfade muessen diese Grenze respektieren. Unbekannte oder alte Herkunft darf nicht als v2 neu etikettiert werden. Alte trainierte Projektorgewichte werden bei Identitaetskonflikt abgelehnt und nicht ueberschrieben.

Bestehende Vektoren/Projekte werden nicht migriert oder automatisch neu analysiert. Bei Altbestand koennen semantische Funktionen bis zu gesondert freigegebener Neuanalyse/Neutraining nicht verfuegbar sein; eine technische Versionssperre ist keine automatische Qualitaetsverbesserung der Bestandsprojekte.

## Echter DirectML-Nachweis

siglip-results.json dokumentiert18 native Bilder (dieselben sechs Clips/drei Zeitpunkte), je zwei korrigierte Inferenzlaeufe, plus sechs Mittelpunktsvergleiche mit alter Normalisierung:42 DirectML-Inferenzen. Alle korrigierten Vektoren endlich, Dimension1152, Norm nahe1; Wiederholungen bitidentisch. Native RGB-Hashes werden gegen die Caption-Mehrzeitpunktserie verglichen. Einzelbildinferenz ist belegt; ONNX-Batchinferenz wird aus den CPU-Batchtests nicht abgeleitet.

Aktiver Provider DmlExecutionProvider, enable_mem_pattern=false und enable_cpu_mem_arena=false. Sechs Clipmittelwerte technisch berechnet, nicht als semantisch richtige Rangfolge abgenommen. Textencoder fehlt/verifiziert nicht vertrauenswuerdig; daher keine SigLIP-Textsuche oder Text/Bild-Qualitaetsbehauptung. Norm-/Wiederholungspruefung ersetzt keine Inhaltsreferenz.

Ein VRAM-Buchhaltungs-/Sensordifferenzhinweis trat auf. Die Lastpruefung erlaubte den begrenzten Lauf; daraus folgt keine qualifizierte Speicherpeak-/Langzeitbaseline. Das eigene Modell wurde danach entladen.

## Schutz, Deployment und offene Abnahme

Alle vier Medienserien pruefen Original-/Config-/erfasste Datenbank-/Recoveryhashes vor/nachher. Isolierte APPDATA/LOCALAPPDATA/TEMP/PBSTUDIO_PROJECT_DIR, keine Produkt-Lifespan-Ausfuehrung, kein Eingriff in ComfyUI-Auftraege. Nur eigene Analysemodelle geladen/entladen. Keine privaten Vorschaubilder publiziert.

Python-Quellen im bestehenden Checkout; korrigierter SigLIP-Pfad in frischem echten DirectML-Prozess ausgefuehrt. Kein C#-/oeffentliches HTTP-Schema geaendert, kein Binarybuild erforderlich. Kein GUI-/vollstaendiger API-/Altprojekt-Abnahmenachweis; kein Produktneustart aus dieser Pruefung ableiten. Abschliessende Standardportpruefung fand keinen Listener8765; LM-Studio-Inventar zeigte alle Modelle not-loaded. Kein bestehender Prozess neu gestartet.

## Test- und Reviewabschluss

- 186 verschiedene gezielte Tests bestanden:108 Caption-/Preprocessing-/Pipelinefaelle und78 Identity-/Persistenz-/Vektor-/Brainfaelle. Je sechs Dependency-Deprecationwarnungen; kein Fehler im Schlusslauf. Logs pytest-caption-final.txt und pytest-identity-final.txt.
- 23 neue Testfaelle:7 Vorverarbeitung,16 Identitaet. Vorher/Nachher-Belege im Ordner; initialer Identity-Testaufbaufehler nicht als Produktfehler gezaehlt. Ein vorhandener Cooldown-Test wurde nach belegtem10ms-Timing-Flake mit lokaler Testuhr stabilisiert, Produktcode unveraendert; drei Einzelwiederholungen bestanden.
- Unabhaengiger Codegegenreview fand zwei Anschlussluecken (Queryherkunft, VideoSpecialist-Produktion/Kandidaten bei Custom-Indizes), beide repariert und regressionsgeprueft. Details review.md. Generische Nicht-Video-Indizes bleiben generisch; VideoSpecialist filtert selbst.
- final-validation.json:15 geaenderte Python-Dateien syntaktisch geprueft, genaue Quellhashes und186 Ergebnisse gebunden; erfasste Schutzdateien auch nach CPU-Tests unveraendert. media-validation.json bestaetigt18 identische RGB-Eingaenge zwischen Caption und SigLIP,18 bitidentische Wiederholungen und Entladen aller eigenen Modelle.

T055-Ursachenuntersuchung und T056-Reparatur im beschriebenen Scope abgeschlossen. T002/G1/Gesamt-T045, unabhaengiger Holdout, semantische Gesamtqualitaet und sichtbare Produktabnahme bleiben offen. Masterplan aktualisiert; KI-Hirn-Schreib-/exakter Ruecklesebeleg: ki-hirn-sync.json. Aenderungen lokal im Checkout; kein Commit/Push in diesem Schritt.
