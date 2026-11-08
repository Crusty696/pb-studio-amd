# T002 — konkrete Medienauswahl und Aufteilung

2026-10-13. Quellen ausschließlich lesend geprüft. Keine Generierung, GPUinferenz, Produkt-Appstarts, Migration oder Installation. Vorhandene FFprobe/FFmpeg-Binaries; Video ausdrücklich -hwaccel none, CPUdecoder ein Thread, höchstens zwei parallele Inventar-/Stichprobenprozesse. Kontaktbögen sind abgeleitete Sichtungsnachweise, keine generierten Clips. Keine Audioableitung gespeichert; Stichprobensignal nur im RAM.

## Ergebnis

424 Mediendateien (416 Clips + 8 Audiodateien) vollständig SHA-256-gehasht und per FFprobe geprüft, null Probe-Fehler. Zusätzlich zwei Audiosidecars gelesen. 408 unterschiedliche Video-SHA256: acht Paare exakt gleicher Dateien, darunter vier Paare über zwei Ordner verteilt. 83 Mehrfachgruppen nach normalisiertem Dateititel und 18 ähnliche mittlere Framepaare (dHash-Abstand <=4) als Hinweise dokumentiert. Dateititel/ein Frame sind keine unabhängige Herkunftsprüfung; keine automatische Generierungs- oder Quellidentität daraus behauptet.

Alle 416 Clipstreams melden H.264/yuv420p: 378 mit 854x480/30fps, 29 mit1280x720/24fps, neun mit720x480/30fps. Transfer-/Farbmetadaten fehlen; keine pauschale SDR-/Farbgütefreigabe. Einzelstreamdetails samt SAR und Zeitbasis stehen im Inventar. Die Codec-/FPSangaben für den Gesamtbestand stammen aus Headern; nur die gewählten sechs Videos wurden vollständig decodiert und Frame-PTS geprüft.

## Ausgewählte Videos

| ID | Datei (eindeutiger Kurzname; Vollpfad im Manifest) | Eigenschaften | Zweck / Sichtungsbefund |
|---|---|---|---|
| V01 | Enchanted_Neon_Forest_Rave … 01jx6skcz6frkvfmgyznys8n69 | 10s,720x480,30fps,300Frames | Zentrale Figur/Neon/Wald; typischer Motivfall |
| V02 | gemini_generated_video_03f98367.mp4 | Container30.016s, Videospur30s,1280x720,24fps,720Frames | Ruinen/Figur/Handdetail, verschiedene Ansichten; Szenen-/Detailkandidat |
| V03 | Mystical_Waterfall_Dance … 01jxp6w02me7hr4fq6wtadw5yz | 10s,854x480,30fps,300Frames | Zwei Figuren, Wasserfall/Nebel/Reflexionen |
| V04 | Enchanted_Flame_Dance … 01jxp7m8dqfwpr1n4y1c2ajh72 | 10s,854x480,30fps,300Frames | Dunkler Steinraum/Feuerstellen; schwierige Beleuchtung |
| V05 | Neon_Storm_Dance … 01jxp9e13afkzsavkp55w0xj28 | 10s,854x480,30fps,300Frames | Blitze/Wolken/Silhouetten; beabsichtigte starke Helligkeitswechsel |
| V06 | Neon_Reflections_Dance … 01jxp9kxmnfvha4xnn4f439bet | 10s,854x480,30fps,300Frames | Dunkle Wasser-/Mondszene, Reflexionen |

Alle sechs: vollständiger Decode Exit0 ohne stderr; sämtliche Video-PTS vorhanden und streng steigend. 30fps-Abstände0.033333–0.033334s bzw.24fps0.041666–0.041667s entsprechen innerhalb Ausgaberundung gleichmäßigen Abständen. Kein A/V-/Farb-/Qualitäts-PASS daraus. Fünf Frames je Clip bei5/25/50/75/95Prozent angesehen; keine vollständige subjektive Echtzeitbetrachtung. Sechs Kontaktbögen V01–V06 liegen neben diesem Bericht.

V02 hat eine byteidentische Kopie gemini_generated_video_741eaffa.mp4. Nur V02 als Repräsentant verwenden, die Kopie niemals in anderen Split. V01 hat eine gleichnamige Promptfamilie mit zwei Dateien; V03/V04/V05/V06 jeweils vier gleichnamige Kandidaten. Diese Gruppen komplett zusammenhalten; weitere Familienbeziehungen bleiben möglich.

## Ausgewähltes Audio

| ID | Datei | Original | Erster Prüfbereich / Zweck |
|---|---|---|---|
| A01 | Progressive Psy Summer Dream mix  by Crusty Free download.wav |54:59.457,PCM16,44.1kHz,Stereo|01:00–03:00; bekannter Regressionseinstieg |
| A02 | Crusty -Klangkraft-21nai2022.wav |1:45:35.027,Float32-PCM,48kHz,Stereo|01:00–03:00; anderer Sampleformat-/Sampleratenfall |
| A03 | Podcast-04.m4a |3:07:38.659,AAC,44.1kHz,Stereo|01:00–03:00; komprimierter Langdateifall, später Dauerlast nur extra freigeben |

Diese Auswahl unterscheidet technische Formate und Quelldauern; musikalische Unabhängigkeit ist unbewiesen. Jeder Zweiminutenbereich decodiert fehlerfrei in960000 endliche Mono-Probesamples bei8kHz. Kein Vollmixdecode, keine Hörabnahme, kein Beat-/Tonart-/Loudness-/Stemqualitätsnachweis. Samplewerte wurden ausschließlich für begrenzte Integritäts-/Ähnlichkeitsprüfung erzeugt, nicht als neue Medien gespeichert. Prüffenster sind neutral gewählt, keine behaupteten Drop-/Blendenbereiche; geeignete fachliche Referenzfenster noch annotieren.

## Verwandtschaft und Vorbenutzung

Alle sieben Nicht-Stem-Audioquellen stimmen in Dateigröße und gespeichertem16Hex-SHA256-Präfix mit docs/measurements/2026-08-30-downbeat-phase-contrast.json überein. Historische Hashfunktion las ganze Datei, speicherte aber nur64Bit-Präfix. Dies ist starker Vorbenutzungsbeleg, kein Vergleich zweier vollständig gespeicherter256Bit-Hashes. Alte Messungen werden nicht als neue Baseline übernommen.

test.stem.mp4 enthält fünf AAC-Stereospuren, keine Videospur. Containerdauer5531.003s; Mai-WAV5531.005s. Sidecars benennen Drums/Bass/Synths/Vox, aber keine belastbare Quell-/Stemherkunft. Erster Audiostream gegen Mai-WAV: drei12s-Fenster ab60/600/1800s, CPUmono8kHz, Korrelation0.9999468/0.9999049/0.9999100 bei0Lag im geprüften +/-50ms-Raster. Deshalb gleiche vorsichtige Familie. Nicht als unabhängiges Musikbeispiel oder echte Originalstem-Groundtruth verwenden. Die anderen vier Spuren wurden damit nicht qualifiziert.

V01 ist historisch captiongetestet; V03/V04 historisch analysiert; V05/V06 historisch importiert/indexiert. Nachweise und genaue Pfade stehen bei prior_evidence im Manifest. Historische Videobytes nicht gehasht verglichen, Vorbenutzung konservativ aus exakten Dateinamentreffern abgeleitet. Für V02 kein Treffer in durchsuchten Textnachweisen, aber keine bewiesene Nichtbenutzung.

## Verbindliche vorläufige Aufteilung

- Aktuell freigegebene Zuordnung nur **Development/Regression: alle neun ausgewählten Quellen**. Auch weitere Ausschnitte derselben Mixdateien bleiben hier.
- Vorbereiteter Ablauf: Developmentkern V01/V02/A01–A03; anschließend V03/V04 als getrennte Regression-/Validierungskandidaten, V05/V06 als Stressfälle. **Keine unabhängige Validationfreigabe** solange gemeinsame Herkunft und Vornutzung ungeklärt; Manifest trennt diesen Vorschlag von wirksamen Splits.
- **Holdout leer.** Die zunächst erwogenen V05/V06 wurden wegen positiver historischer Nachweise als Holdout verworfen. Kein neues Etikett auf bekannte Medien kleben. V02 nur unbekannt, daher ebenfalls kein qualifizierter Holdout.
- Für spätere unabhängige Abnahme gezielt noch nicht verwendete Quellfamilien/Herkunftsnachweise bestimmen. Bekannte Ordner bleiben Ausgangspunkt; eine erneute Pfadanfrage ist nicht nötig. Nicht alle übrigen Videonamen historisch einzeln abgeglichen, daher keine Aussage, der gesamte Videoordner sei verbraucht.
- Fachliche Labels, tatsächliche Schnitt-/Beat-/Blendenmarken und Nutzerqualitätsurteil fehlen. Sammlung zeigt vorwiegend stilisierte Fantasy-/Tanzszenen in gesichteten Stichproben; keine Generalisierung auf beliebige Realfilmgenres, Sprache, Haut-/Farbreferenz oder HDR.

## Belege und nächste Schritte

inventory.json: Vollpfade/Hashes/Streams/Dateistatistik. video-samples.json und overview-*.jpg: mittlere Frame-Stichproben aller416Clips; Parent sah alle sechs Übersichtsseiten. video-family-check.json: Familienhinweise; audio-family-check.json: gemessene Stichprobenkorrelation. selected-verification.json: Decode-/PTS-/CPUaudioergebnisse. original-integrity.json: alle neun ausgewählten vollständigen SHA256 vor/nach identisch; Größe/mtime aller424Medien unverändert. reference-manifest.json: maschinenlesbare Auswahl, keinerlei GPU-/Generierungsfreigabe. **Publikationsgrenze 2026-10-13:** Die JPG-Vorschaubilder bleiben auf ausdrücklichen Nutzerwunsch lokal und werden nicht in das öffentliche GitHub-Repository aufgenommen; referenzierte Bilddateien sind daher nur in der lokalen Arbeitskopie verfügbar.

Als Nächstes unabhängige Fachlabels und genaue musikalische Referenzfenster auf dem Developmentbestand vorbereiten; Familien-/Vornutzungsfragen gezielt klären. Nativebaseline weiterhin eigener begrenzter Laufauftrag, GPU/Generierung weiter gesperrt. T002 bleibt offen. Reale Workflow-/Policy-/Effective-Identitygates aus WaveB bleiben bestehen.
