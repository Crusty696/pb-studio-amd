# T002 — Referenzbestand und Messplan

Stand: 2026-10-13. Status PREPARED / NOT MEASURED. Nutzerauftrag: gründlich vorbereiten, keine Generierung oder GPU-Läufe. T002 bleibt offen. Keine Produktcodeänderung, kein Appstart, kein Workflowstart, keine Installation, Migration oder Originalmutation. Die folgenden Zahlen sind vorgeschlagene Stichprobenumfänge und Quellbereiche, keine gemessenen Leistungs-/Qualitätsgrenzen.

**Fortschreibung 2026-10-13:** Der folgende Ausgangsstand beschreibt die frühe reine Verzeichnisprüfung. Danach wurden Quellen ausgewählt, technisch mit FFmpeg geprüft und 9/9 mit begrenzten PB-Studio-CPU-Funktionen gelesen. [CPU-Prüfbericht](t002-cpu-check-2026-10-13/cpu-check-report.md). `NOT MEASURED` gilt weiterhin für Native-Qualitäts-/Leistungsbaseline und Grenzwerte; T002 und unabhängiger Holdout bleiben offen.

## 1. Verbindliche Quellen und aktueller Nachweis

Nutzer hat diese Quellen am 2026-10-13 benannt und ihre dauerhafte Erinnerung verlangt:

- Clips: `E:\03_Video_&_Medien\Eigene_Videos\Video\Clips`
- Audio: `E:\02_Musik_&_Audio\Audio_Clips\Psy-Set`

Beide Verzeichnisse existieren. Ausschließlich Verzeichniseinträge gelesen: Clipordner 416 Dateien mit Endung .mp4; Audioordner 10 Dateien (.wav:5, .mp3:1, .m4a:1, .mp4:1, .json:2). Endung ist kein Stream-, Decode-, Qualitäts- oder Unabhängigkeitsnachweis. Keine Medien geöffnet/decodiert/gehasht oder analysiert. Keine JSONdatei als Referenzlabel übernommen. Einzeldateien, Herkunftsfamilien und bestehende Nutzung als Trainings-/Tuningmaterial noch unbekannt. Keine erneute Anfrage nach diesen Wurzelpfaden erforderlich.

Originale bleiben am Ort unverändert. Auswahl über Pfad und Zeitbereich; keine vorab geschnittenen Kopien nötig. Spätere autorisierte Probe/Decode mit vorhandenen Werkzeugen, Softwaredecode ohne GPU; keine automatische Reparatur/Transcodierung. Ausgabe und Evaluation in einer noch konkret zu benennenden separaten Arbeitswurzel. Produkt-/Recovery-/Cachedateien bleiben außerhalb dieses Vorbereitungsauftrags.

## 2. Kleines Startpaket

| Medien | Vorschlag | Zweck und Auswahl |
|---|---|---|
| Reale Videoclips | 6 unabhängige Quellfamilien, je 2 Development/Validation/Holdout | Je Split typischer und schwieriger Fall. Insgesamt ruhige Szene, schnelle Bewegung, dunkles/kontrastarmes Motiv, feine Details und mindestens ein Szenenwechsel/Blende abdecken; Merkmale dürfen sich überschneiden. Für erste Sichtung 5–20 Sekunden pro Quelle vormerken, vollständige Originale erhalten. SDR zunächst bevorzugen; tatsächlichen Farb-/Streamvertrag erst prüfen. |
| Reale Musik | 3 unabhängige Titel/Quellfamilien, je 1 pro Split | Typisches Psy-Material, gut hörbarer Beat und wenigstens ein Breakdown/Übergang; zunächst je 2–5 Minuten Analysebereich vorschlagen. Sind vorhandene WAVs nur Ausschnitte desselben Sets, zählen sie zusammen als eine Familie. Fehlende unabhängige Familien melden, keinen Holdout vortäuschen. |
| T2V-Beschreibungen | 3 voneinander unabhängige Szenarien, je 1 pro Split | Einfaches gewünschtes Motiv, gewünschte Bewegung, Stil sowie unerwünschte Fehler vorab beschreiben. Eine einzelne Vorgabe reicht für späteren technischen Smoke; drei sind nur kleiner Qualitätsvorlauf. Keine Quelldatei für Text-zu-Video nötig. |
| Bildreferenzen | Jetzt nicht erforderlich | Nur wenn später Bild-zu-Video ausgewählt wird: eigene unabhängige Bilder je Split samt gewünschter Animation. Nicht ungefragt zusätzliche Familie öffnen. |

Zunächst reicht die Auswahl des Developmentpaares plus eines Musikbereichs; die übrigen unabhängigen Familien gleichzeitig reservieren. Sechs Clips/drei Titel sind keine statistisch ausreichende Anbieterqualifikation. Nach tatsächlichem Inventar und Fehlervariation Umfang je Kohorte erhöhen. Alle Merkmale, die in einem Split fehlen, als nicht geprüft ausweisen. Keine pauschale Qualitätsaussage über andere Genres/Formate/Modelle.

Für den ersten rein technischen T2V-Smoke keine vollständige Audiovergleichskampagne verlangen. Audio-/Videoreferenzen dienen Nativeanalyse, Musikschnitt und visueller Nutzbarkeit; Nativeanalyse ist keine gleichartige T2V-Generatorbaseline.

## 3. Noch benötigte Nutzerinformationen

Die Dateien müssen nicht hochgeladen oder verschoben werden. Aus den benannten Ordnern können Kandidaten ausgewählt werden. Noch benötigt:

1. Welche Dateien gehören zum selben Originalset, derselben Aufnahme/Serie oder sind Varianten? Welche wurden bereits fürs Tuning oder frühere Tests genutzt? Unbekannte Familien bleiben unzugeordnet; keine zufällige Dateiaufteilung als Unabhängigkeitsbeleg.
2. Was ist für dich ein brauchbarer erster Clip? Ein konkretes Motiv mit Bewegung/Stil und ein bis zwei nicht akzeptablen Fehlern. Falls keine Präferenz: erster Pilot kann als einfacher T2V-Funktionsnachweis geplant werden; Qualitätspräferenz bleibt offen.
3. Vorhandene unabhängige Beat-/Trackwechsel-/Tonart-/Szenenmarken, falls vorhanden. Nicht nachträglich aus PB-Ergebnissen als Wahrheit übernehmen. Fehlende Labels gemeinsam vor Ergebnisansicht erstellen; du musst keine FPS-/VRAMwerte erraten.

Keine zusätzliche Grundsatzfreigabe für O01–O04 verlangen. Pfadbenennung ist Auswahlvorbereitung, keine GPU-/Generierungsfreigabe. Konkreter Baselineauftrag und T007-Pilotauftrag werden erst mit benannten Dateien, Profilen, Lauf-/Ausgabegrenzen vorgelegt.

## 4. Unabhängige Referenzen und Splits

Vor Kandidatentuning Herkunftsfamilien festlegen: Volltrack/Ausschnitt/Remix/Transcodierung, Frames desselben Videos, Serien mit nahezu gleichem Inhalt und gegebenenfalls gemeinsame Mixquellen zusammenhalten. Identische Hashes erkennen nur identische Bytes, keine semantische Verwandtschaft. Vorbekannte Spec00035-Test-/Holdoutmedien nur als Development/Regression aufnehmen, sofern sie bereits betrachtet oder zur Anpassung verwendet wurden.

Development dient Basismessung und späterem Tuning. Validation prüft die eingefrorene Variante ohne direkte Anpassung an Einzelresultate. Holdout bleibt bis Endprüfung ohne Kandidateninferenz, Auswertung oder Tuning; rein technische Inventarisierung und unabhängige Referenzannotation sind erlaubt und protokolliert. Nach Holdout-getriebenen Änderungen gilt er als verbraucht; neuen unabhängigen Holdout reservieren. Kein Split allein durch Zufall über Dateinamen.

Referenzannotation bindet Sourcehash, exakten Bereich und Sourcezeitbasis:

- Audio: Beat-/Downbeatzeitpunkte in ausgewählten Fenstern, Tempoambiguität, beobachtete Breaks und Blendenintervalle; unsichere Tonart/Struktur ausdrücklich unknown. Dateiname/ID3/Software-BPM ist ungeprüfte Metadatenquelle, keine Groundtruth.
- Video: sichtbare Objekte/Aktionen, Szenengrenzen, Kamerabewegung, absichtlich dunkle/statische Stellen und bekannte Originalartefakte. Annotation ohne Kenntnis der späteren Systemausgabe; Quelle/Rater/Datum/Unsicherheit speichern.
- Generation: vorab verlangte Motive/Bewegung/Stil, verbotene Fehler, technische Sollform; spätere menschliche Bewertung möglichst ohne Providername und in zufälliger Reihenfolge. Technische Integrität und ästhetischer Nutzen getrennt.

Ratings ausschließlich in separatem Evaluationsspeicher; keine produktiven /brain/feedback- oder Trainingswrites. Ein Testprojekt isoliert den globalen Brainzustand nicht. Bei Brain-/Directorvergleich zusätzlich gefrorene Gewichte, Projektorgeneration und Lernpolicy binden. Rohprovidervergleich ohne Brain benötigt keinen künstlich erfundenen Trainingslauf.

## 5. Reihenfolge mit Freigabegrenzen

| Schritt | Tätigkeit und Ergebnis | Ausführung |
|---|---|---|
| 0 | Diese Vorbereitung, bekannte Quellen, leeres Manifest, Mess- und Labelvertrag | Hier erledigt; nur Dokumente/Verzeichniseinträge |
| 1 | Kandidaten aus bekannten Ordnern auswählen; Verwandtschaft/Vornutzung klären; Quellen und Bereiche registrieren | Als nächste Vorbereitung möglich; kein GPU-/Generierungsjob |
| 2 | Ausgewählte Dateien SHA-256, Größe, tatsächliche Streams/SR/Kanäle/Frames/rationale FPS/Timebase/Dauer/VFR/Farbe; anschließend begrenzter oder vollständiger Softwaredecode nach dokumentiertem Scope | Read-only Medienprüfung separat konkret durchführen; keine heutige Messung. Holdoutlabels unabhängig halten |
| 3 | Unabhängige Labels, Unsicherheiten, Splits, Ausgabe-/Evalwurzel und Messdefinitionen fixieren | Vor Kandidatentuning; fehlende Referenz bleibt offen |
| 4 | Isolations-/Recoverypreflight, Nativebaseline auf Developmentquellen | Eigener begrenzter Laufauftrag; jede GPUanalyse bleibt bis dahin verboten. Vor Produktstart ungeklärten Recoveryzustand prüfen |
| 5 | Baseline auswerten; Qualitäts-/Zeit-/Speichergrenzen und Nichtunterlegenheitsmargen je Kohorte festlegen, versionieren und bestätigen | Vor Kandidatentuning/Qualifikation. Keine frei erfundenen Erfolgsprozente |
| 6 | T007-Pilot konkret vorbereiten: vorhandener APIworkflow, Runtime/Nodes/Modelle, lokale Audit-/Effective-Identität, freie geeignete Betriebsphase, Output-/Laufbudget | Zusätzlich Bridge-/Profilgates aus Abschnitt 8; Medienverfügbarkeit allein reicht nicht |
| 7 | Separat freigegebener einzelner kleiner Development-Pilot; Output technisch und menschlich prüfen, Ressourcen messen | Später, nicht hier; erst danach begrenzte Wiederholungen/Variation |
| 8 | Gleiche Quellen/Bereiche: Native gegen Kandidat pro tatsächlich vergleichbarer Capability; anschließend Validation | Keine Vermischung verschiedener Cachezustände oder Vektorräume |
| 9 | Endgültige Konfiguration einfrieren und unangetasteten Holdout prüfen | Kein Nachbessern anhand Holdout mit anschließendem pauschalem PASS |
| 10 | Spätere echte PB-Benutzerkette: Import/Analyse/Zuordnung/Preview/AMFexport/Reopen | T024/T026/T038 und weitere Gates; kein T002-Vertragstest ersetzt GUI/Medienabnahme |

Vor GPUbaseline/Pilot konservative vorläufige Stopgrenzen aus technisch belegtem verfügbaren Budget festlegen. Die endgültige qualifizierte Grenze entsteht erst aus Messung; ohne Beobachtbarkeit/Budget kein unbegrenzter Versuch. Fremde ComfyUI-Jobs nicht stoppen, entladen oder beeinflussen. Bei Lastkonflikt eigene neue Starts aussetzen; observed_shared garantiert keine Exklusivität.

## 6. Was genau gemessen wird

### Technische Integrität

Quelle/Output separat: Hash, Streamauswahl, Breite/Höhe/SAR, rationale FPS/PTS, tatsächliche Frames/Dauer, Pixelformat/Farbraum, Audiostream/Samplezahl/Samplerate/Kanäle, Decodefehler und A/V-Synchronität. Soll-/Istvertrag vergleichen, unbekannte Farbe/VFR ausdrücklich behandeln. Pflichtoutputs vorhanden und dem richtigen Attempt zugeordnet; keine automatische Veröffentlichung bei unbekannter Herkunft oder fehlendem Nachweis. Full Decode beweist weder richtige Farbe noch schöne Bilder. T2V ohne gewünschtes Audio nicht wegen fehlender Audiospur ablehnen.

### Fachqualität

Beats: Zeitabweichungen und Drift, Beat-/Downbeat-Präzision/Recall/F1 mit vorab festgelegtem Matchingfenster; Half-/Doubletempo gesondert. Musikstruktur: Segment-/Blendenbereiche mit unsicherer Semantik, Tonart nur gegen geeignete Labels. Video: Szenengrenzfehler, richtige/falsche/fehlende Inhalte und Halluzinationen; Bewegung und absichtlich statische/dunkle Stellen getrennt. Generation: Prompttreue, Bewegungsfehler, Flackern, Form-/Identitätsstabilität und Verwendbarkeit im Musikvideo; menschliche Wertung separat von Decodierbarkeit. Fehlende Groundtruth = NOT EVALUATED, nicht 0 und nicht PASS.

### Laufzeit und Ressourcen

Monotone Zeitmessung: Auftragsannahme, Queuewartezeit, Laden, Berechnen, Schreiben/Transfer, Decode/QC, künftig Import/Analyse bis wirklich verwendbarer Clip. Bis zur Implementierung fehlende Stufen als NOT AVAILABLE ausweisen, reine Nodezeit nicht als E2E ausgeben.

CPU/RAM, freier RAM, Diskplatz vorher/nachher und temporäres Maximum soweit messbar; GPU beobachtetes Sensormaximum einschließlich Messzeitfenster/Quelle/Gerät/Abtastrate/Abdeckung/Ausfällen/Fremdlast. GPUgesamtverbrauch nicht unbewiesen Comfy zurechnen. Drei getrennte Werte: estimated_committed_mb, observed_sensor_max_mb, qualified_limit_mb. Bestehendes vram_peak_mb aus Start-/Endbuchhaltung ist kein Hardwarepeak. Sensorlücke/unerreichbarer Sensor = unknown; Stichprobenmaximum ist keine exakte Peakgarantie.

Läufe getrennt registrieren: fresh-cold (neue Analyse, relevanter Modellcache kalt), fresh-warm (neue Analyse bei warmem Modell), result-cache-reuse (Ergebnis übernommen). CPU-/OSdateicachezustand separat unknown, wenn nicht kontrolliert. Niemals produktive Caches löschen oder fremde Modelle entladen, um cold zu erzwingen. Comfy-Graphcache kann Neuberechnung verhindern; tatsächliche Cachehits/ausgeführte Nodes dokumentieren. Ein geänderter Seed allein beweist nicht vollständige Neuberechnung.

Nach separat freigegebenem Smoke als Startvorschlag drei Wiederholungen je verfügbaren Modus, nur innerhalb genehmigter Laufzahl. Einzelwerte/Spanne/Median und n berichten; bei kleinem n keine belastbare p95-/Ausfallwahrscheinlichkeit behaupten. Seed-/Promptvariationen als unterschiedliche Qualitätsfälle erfassen, nicht als identische Zeitwiederholungen. Fehler/Timeouts/abgebrochene Läufe bleiben im Nenner; keine automatische Retryschleife. Unbekannter Submitstatus niemals blind erneut senden.

## 7. Qualitätsprofil und Abschluss

Je Capability/Kohorte: Revision, Pflichtmetriken, technische Integritätsregeln, freigegebene Grenzwerte/Einheiten, unabhängige Referenzrevision, erlaubte Ausnahmen, Messmodus und Budget. Numerische Felder bis Baseline/Entscheid null; nicht 0, nicht automatisch aus alten Spezifikationen übernehmen. Vorläufige Schutzbudgets von nachgewiesenen Qualitäts-/Kapazitätsgrenzen unterscheiden.

T002 bleibt offen, bis autorisierte Einzelquellen gehasht, unabhängige Labels/geeignete Splits und die gewählten Native-Basismessungen sowie freigegebenen profilspezifischen Grenzwerte vorliegen. Spätere FP12-/FP16-Endabnahme nicht vorziehen. Vorbereitetes JSON ist nur Planartefakt, kein implementierter produktiver QualityProfile-DTO. Geplanten Tests/test_comfyui_benchmark_manifest.py erst bei eigenem Implementierungsschritt liefern; hier keine Testsuite/Produktimplementierung behaupten.

## 8. Bereits bekannte technische Gates vor T007

Welle-B-Nachweis: kein qualifiziertes Profil, execution_ready stets false. Enum-/dynamische Nodeschemata und literale Listen werden aktuell abgewiesen. Vor Pilot tatsächlichen APIworkflow prüfen; erforderliche unterstützte Erweiterung zuerst konkret implementieren/prüfen, keine Validatorsperre umgehen. Parametrisierte Effective-Graphs benötigen noch die gebundene aufgelöste/Submission-Auditidentität. Trusted-Verifier-Testfixture ist kein realer Runtime-/Egressbeleg. Profilprüfung/Freigabe muss gegebenenfalls in einem gesonderten Codepaket vervollständigt werden. Kein stiller Alternativpfad direkt zu Comfy, nur um G1 zu behaupten.

## Quellen und Gegenprüfung

Normativ: tasks.md §T002; clarifications.md O03; plan.md §Fachqualität und statistische Auswertung / §O; domain-contracts.md FP12/FP13/FP16; wave-b/qc-report.md. Zwei unabhängige read-only Fachprüfer bestätigten Messfolge, Gruppen-/Holdoutregeln und Ressourcen-/Brainfallen. Historische Nativewerte sind kein heutiger Baselinebeleg. _wiki/decisions fehlt weiterhin; aktuelle bestätigte Repoentscheidungen wurden gelesen.

## Fortschreibung: konkrete Quellauswahl 2026-10-13

Vorherige Aussagen „keine Medien gehasht/decodiert“ beschreiben den Vorbereitungsstand. Jetzt424Medien gehasht/geprobt, sechsVideos komplett CPUdecodiert, dreiAudiofenster begrenzt CPUdecodiert; keine GPU/Generierung. Konkrete Auswahl und Vorbenutzung: [selection-report.md](t002-selection-2026-10-13/selection-report.md). Der ursprüngliche Vorschlag unabhängiger6+3Quellen konnte nicht als unabhängiger Split belegt werden: effektiver Bestand Development/Regression, Validation/Holdout bleiben unqualifiziert. Neue Native-/Fachqualitätsmessungen weiterhin offen.

## Fortschreibung: Referenzentwürfe und Reserveprüfung

Siehe [Referenzvorbereitung](t002-reference-preparation-2026-10-13/reference-preparation-report.md):6AI-Bildentwürfe,3Audiofenster ohne erfundene Ereignisse,15einzigartige unqualifizierte Holdoutkandidaten.397/416Videopfade mit historischem Texthinweis. Menschliche Labels und Herkunftsbestätigung bleiben offen; keine Änderung der effektiven Splits, keine GPU/Generierung.

## Aktueller Nutzerentscheid: Regression statt ungeklärtem Holdout

2026-10-13: Nutzer erinnert frühere Nutzung/Familien nicht genau. Bestehende Clips ausdrücklich als Regressionstestmedien nutzen; unabhängigen Holdout offenlassen. Keine erneute Herkunftsantwort als Blocker der Vorbereitung. Siehe [Regressionsprotokoll](t002-regression-preparation-2026-10-13/regression-protocol.md). Alle früheren Herkunftsfragen bleiben dokumentierte Unsicherheit, keine ausstehende Voraussetzung für Regression. Generierung/GPU weiter verboten.
