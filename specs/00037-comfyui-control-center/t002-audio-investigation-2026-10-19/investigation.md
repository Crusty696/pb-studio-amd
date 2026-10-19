# T002: Ursachenanalyse BeatNet und Downbeats — 19.10.2026

## Auftrag und Ergebnisgrenzen

Reine Untersuchung mit Audio-, GPU-, PB-Master- und Systematic-Debugging-Skills; drei Spezialagenten für BeatNet, Upstream-Gegenprüfung und Pacing-Verbraucher. Keine Reparatur des Produktcodes oder der installierten Pakete. Kein Build/Deployment erforderlich. Keine Generierung oder Installationen. Vorherige Ergebnisse nicht als musikalische Abnahme behandelt.

## 1. BeatNet: konkreter Absturz reproduziert

Produktpfad: backend/routers/audio_router.py:523 verwendet offline/DBN. BeatDetector fängt Fehler in src/pb_studio/audio/beat_detector.py:359 ab; dadurch bleibt im Standardlog nur die Fehlermeldung. Ein anfänglicher Einzeltest mit default online/PF lief erfolgreich, war aber nicht äquivalent. Mit dem tatsächlichen offline/DBN-Modus wurde der Fehler auf A03 reproduziert.

Installierte Versionen live: Python-Projektvenv, NumPy 1.26.4, torch 2.11.0+cpu, librosa 0.11.0, BeatNet 1.1.1, madmom 0.16.1; BEATNET_AVAILABLE=True. Historische Skill-/Modulnotizen, madmom sei nicht vorhanden und BeatNet immer deaktiviert, treffen diese Laufzeit nicht.

Exakte Kette: BeatNet/BeatNet.py:144 -> madmom/processors.py:120 -> madmom/features/downbeats.py:287. Die Auswahl `np.argmax(np.asarray(results)[:, 1])` versucht drei Paare aus langem Zustandsvektor und skalarem Score in ein homogenes Array umzuwandeln. NumPy 1.26.4 lehnt diese gemischte Struktur ab: `(3, 2) + inhomogeneous part`. Kein Hinweis auf beschädigte Musik oder DirectML-Fehler; diese Stufe läuft auf CPU.

Gegenprobe ausschließlich im Arbeitsspeicher einer Testinstanz: nur den Score-Anteil zur argmax-Auswahl verwenden. Gleicher A03-Ausschnitt läuft danach durch: 68 Beats, 34 Downbeats. Die drei Kandidaten 2/3/4 Beats je Takt erhielten Scores -3999.6617/-4030.1451/-4034.3459; gewählt wurde Zweiermetrum. Das beseitigt den beobachteten Typfehler im Experiment, beweist keine richtige musikalische Taktfolge. Installierte Bibliothek und Produktcode nicht gepatcht.

Zusätzliche CPU-Gegenprobe der tatsächlichen detect_beats_with_downbeats-Methode: A01-30-s-Fixture liefert unverändert librosa 67 Beats/0 Downbeats, mit lokalem Score-Adapter DBN 70/35; A02-30-s-Fixture 36/0 -> 68/34. Auch hier keine musikalische Abnahme. Der Fixturebatch erfasste zusätzlich ein älteres 120-s-Fixture; Dauer im Beleg ausdrücklich gekennzeichnet, nicht als aktueller 30-s-T002-Fall gezählt. Alle im Batch verwendeten Fixture-SHA-256 blieben unverändert.

Der BeatNet-Abbruch erklärt nicht die vielen Beat-This-Downbeats: nach dem Legacy-Fallback ersetzt die native Beat-This-Stufe dessen Zeitpunkte.

Belege: beatnet-dbn-traceback.txt, beatnet-score-selection.json, beatnet-fixture-countercheck.json. Reproduktion/Experiment: scratch/t002-beatnet-investigation/reproduce_dbn.py und probe_workaround.py (isolierte lokale CPU-Proben, vorhandene abgeleitete WAV-Fixture).

## 2. Beat This: hohe Anzahl entsteht bereits im Modellausgang

Vier tatsächliche DirectML-Vergleichsläufe auf A01/A03. Jeweils gleiches Bewertungsfenster Originalsekunden 60–90; einmal isolierte 30 Sekunden, einmal 90 Sekunden Eingang (Original 30–120). Rohlogits vor der Nachverarbeitung abgegriffen, ohne Produktdateien zu ändern.

| Fall | Beats im Zielfenster | positive lokale Downbeat-Spitzen vor Zuordnung | Downbeats nach Zuordnung |
|---|---:|---:|---:|
| A01_bounded30 | 68 | 37 | 37 |
| A01_context90 | 69 | 36 | 36 |
| A03_bounded30 | 68 | 40 | 40 |
| A03_context90 | 68 | 43 | 43 |

Die hohe Anzahl wird nicht erst beim Zuordnen auf Beats erzeugt. Mehr Kontext beseitigt sie nicht: A01 37 -> 36, A03 40 -> 43. Median der Abstände der markierten Taktanfänge in allen vier Fällen ungefähr 0,44 s; mehrfach direkt benachbarte Beats werden markiert. Das ist eine konkrete auffällige Modellentscheidung, keine durch unabhängige Labels bewiesene Fehlerquote. Die Ursache hinter diesen Modellentscheidungen (Trainingsdaten, musikalische Mehrdeutigkeit, Export-/numerische Güte) ist noch nicht isoliert. Original-PyTorch-vs-ONNX-Inferenzparität wurde hier nicht gemessen.

Vorverarbeitung/Portierung gegengeprüft:

- Binäre Mel-Filterbank bitgleich zur torchaudio-Referenz; synthetische Log-Mel-Probe maximale Abweichung 0,0. frame_length-Normalisierung korrekt.
- ONNX-Ausgangsgraph liefert Logits, keinen Sigmoid-Ausgang. Schwelle >0 entspricht dem Referenzverfahren.
- 80 synthetische Postprocessing-Fälle gleich der Referenz, mit dokumentierter Sonderbehandlung ohne Beats.
- Chunk-Zusammensetzung über 18 synthetische Längen von 1 bis 6001 Frames exakt gleich; insbesondere 1501 Frames ohne doppelte Übernahme oder Lücke.
- Kein Metrum-Zwang im minimalen Referenz-Postprocessing. Eine zusätzliche willkürliche Viererfilterung würde Taktphase erfinden.

Diese Checks grenzen konkrete Portierungsfehler ein; sie beweisen weder allgemeine Modellgüte noch vollständige numerische Exportparität. Kein CPU-Modellfallback verwendet. ORT registriert zusätzlich CPUExecutionProvider, während DirectML zuerst steht; der bestehende enforce_directml_session prüft disable_cpu_ep_fallback=1 und beide deaktivierten Speicherflags, deaktiviert außerdem automatische Retries. Die Providerliste allein ist kein Nachweis einer CPU-Modellausführung; separate Node-Profilierung wurde nicht durchgeführt.

## 3. Nachgelagerte Qualitätslücke

Router audio_router.py:2843–2869 übernimmt native Beats/Downbeats nach validate_neural_events unverändert. align_downbeats wird in diesem Pfad nicht aufgerufen. downbeat_alignment.py:15–28 kontrolliert Form, endliche/sortierte Zeiten, Grenzen und Teilmengenbeziehung. Reiner CPU-Gegenfall: 60 Beats und dieselben 60 Downbeats bestehen diese technische Validierung (120 BPM).

`measured` dokumentiert hier Modellherkunft, keine bestätigte Taktposition. PacingService:450,470–495 übernimmt diese Zeitpunkte; advanced_pacing_engine.py:2175–2193 baut daraus exakte Downbeat-Trigger beziehungsweise zusätzliche Gewichtung. Persistenz kopiert Werte. Somit stammen die hohen Zahlen vor diesen Verbrauchern; sie werden danach ohne separate musikalische Verlässlichkeitsprüfung weitergereicht. Finale Render-/Schnittwirkung nicht ausgeführt.

Tests/test_beat_this_integration.py verwendet überwiegend vorgegebene ideale Viererfolgen oder formal ungültige Zeiten. scripts/dev/verify_beat_this_product.py prüft technische Konsistenz und identische Weitergabe; musikalisch falsche, aber formal gültige Werte können alle bisherigen Checks bestehen.

## 4. Empfohlene nächste Arbeit, noch nicht umgesetzt

1. BeatNet-Kompatibilität gezielt am Score-Selektionsschritt beheben, mit lokal versionierter/reproduzierbarer Lösung statt manueller Änderung in site-packages oder NumPy-Downgrade. Gleiche offline/DBN-Reproduktion vor/nach, Modelle 2/3/4, leerer Eingang und Fehler-/Fallbacksichtbarkeit prüfen.
2. In kurzen klaren Bereichen unabhängige Beat- und Takteins-Markierungen erstellen. Beat This und reparierten BeatNet-Pfad gegen diese Labels vergleichen. Keine automatische Annahme, dass Psytrance zwingend die richtige Viererphase vorgibt.
3. Herkunft und Qualitätsvertrauen getrennt erfassen; diagnostische Auffälligkeiten weitergeben. Keine erfundenen Taktanfänge, keine pauschale Unterdrückung jedes zweiten/dritten Kandidaten.
4. Vor einer weiteren Modell-/Decoderänderung A01/A03 plus Kontrollfall A02 und Kontextbindung beibehalten. Exportparität nur gesondert kontrolliert prüfen; aktuelle HuggingFace-main-Version nicht stillschweigend anstelle des gepinnten Modells einsetzen.

T002 bleibt offen; keine Qualitäts-/Migrations-/Releasefreigabe.

## 5. Sicherheit und Belege

A01/A03 vollständige Original-SHA-256 vor/nach identisch und mit Auswahlmanifest abgeglichen. BeatNet-Proben nutzten nur bereits vorhandene abgeleitete Fixture. config.json, produktive Datenbank samt WAL/SHM und RUNTIME_DIRTY vor/nach sowie abschließend identisch gehasht. Keine Recoveryänderung, kein backend.main-Start. Keine Aufträge gestoppt oder entladen; keine ComfyUI-Steueranfrage. Isolierte APPDATA/LOCALAPPDATA/Projektpfade. GPU-Läufe sequenziell unter shared with_gpu_task und 2048-MB-Modellbudget; LHM ready und freie Reserve vorab geprüft. Private WAV-/NPZ-Dateien bleiben in ignoriertem scratch.

Ein erster neuer Diagnose-Harness hatte sein Modellbudget nicht registriert und wartete deshalb vor Modellstart. Nur diesen eigenen Prüfprozess abgebrochen; Registrierung im neuen scratch-Harness ergänzt. Vier folgende Inferenzfälle beendet, Exit 0. Das war ein Diagnose-Harnessfehler, kein Produkt-VRAM-Mangel. Erfolgreicher Lauf: scratch/t002-downbeat-probe-20261019-184228/run_probe.py.

## Primärquellen und Versionsbindung

- [Offizielle Vorverarbeitung](https://github.com/CPJKU/beat_this/blob/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c/beat_this/preprocessing.py#L25-L56).
- [Offizielles Chunking](https://github.com/CPJKU/beat_this/blob/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c/beat_this/inference.py#L94-L175).
- [Offizielles Postprocessing](https://github.com/CPJKU/beat_this/blob/b95c8ab0c58c2d9fcfd40508ae8dffbc05ac4f5c/beat_this/model/postprocessor.py#L76-L125).
- [Tatsächlich verwendeter ONNX-Export](https://huggingface.co/musetric/beat-this-onnx/blob/45ba973e6c1fbee08a8a75b485e1c5adf45d2bc4/README.md).

Referenzdateien für die Untersuchung lokal in scratch/t002-downbeat-reference gespeichert; aktuelles Remote-main ist nicht der gepinnte PB-Export.
