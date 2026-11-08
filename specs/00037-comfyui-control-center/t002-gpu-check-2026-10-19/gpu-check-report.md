# T002: begrenzte GPU-Analyse am 19.10.2026

## Ergebnis und Umfang

18 tatsächliche Inferenzprüfungen: drei Musikausschnitte und sechs Video-Bildpaare, jeweils zweimal. Wiederholungen liefern identische Ergebniswerte. RX 7800 XT, DirectML, DXGI-Gerät 1; LHM vor den Läufen ready, GPU-Last 0 %, keine Monitoringfehlermeldung. Keine vollständige Native-/Qualitätsbaseline, keine WPF-Abnahme. T002 bleibt offen.

Audio: jeweils Originalsekunden 60–90. Echte Audio-Route mit Beat This ONNX, gemeinsamer GPU-Sperre und Budgetverwaltung; In-Memory-SQLite, AppState, Checkpoints, Reload/API und exakte Übernahme der erkannten Downbeats als Pacingtrigger geprüft. Produktive DatabaseCore-Konstruktion per Tripwire verboten. Kein backend.main/Lifespan; Brain-Embedding-Schreibpfad im Harness deaktiviert. A01/A02 werden vom vorhandenen Produktprüfskript begrenzt in private WAV-Fixtures gelesen. A03 wird vorher per vorhandenem FFmpeg als 30-s-Float-WAV decodiert: der M4A-Import der gesamten Produkt-App ist damit ausdrücklich nicht geprüft.

| Quelle | Modell-BPM | Beats | erkannte Taktanfänge | Lauf 1 / 2, Sekunden |
|---|---:|---:|---:|---:|
| A01 | 136.36 | 68 | 37 | 9.85 / 4.70 |
| A02 | 136.36 | 73 | 20 | 3.22 / 2.51 |
| A03 | 136.36 | 68 | 40 | 7.16 / 5.58 |

Zeitwerte messen die begrenzte Analyse samt Prüfpfad, nicht nur ONNX-Inferenz; Quellhashing und A03-Decodierung sind nicht eingeschlossen. Lauf 1/2 sind keine qualifizierte Kalt-/Warm-Benchmarkreihe. Gleiche BPM-Werte bestätigen keine musikalisch identischen Tempi.

Video: RAFT-MotionAnalyzer für V01–V06, jeweils das Bild am zuvor bewerteten Zeitpunkt und das unmittelbar folgende Frame (Index aus Zeitpunkt × FPS). CPU-Decodierung mit deaktivierter Hardwarebeschleunigung, zwei echte RAFT-Auswertungen unter with_gpu_task; aktiver Provider DmlExecutionProvider. Endliche Bewegungswerte, exakte Wiederholbarkeit. Keine Captions, SigLIP-Embeddings, Szenengrenzen, vollständigen Clips oder Router-/GUI-Persistenz geprüft. Frameindexbindung ist kein neuer unabhängiger PTS-Nachweis. Keine semantische Bestätigung von Tanzen, Figuren oder Tempelstil.

## Befunde und offene Qualität

- BeatNet wirft in allen Audioausführungen `setting an array element with a sequence`. Der Legacy-Pfad läuft danach weiter; erfolgreiche native Ergebnisse stammen von Beat This. Dieser Fehler bleibt offen, keine Reparatur vorgenommen.
- A01: 37 Taktanfänge bei 68 Beats; A03: 40 bei 68. Fachlich auffällig, noch kein bewiesener Fehler ohne präzise unabhängige Referenz. Ein korrekt gespeichertes Ergebnis kann musikalisch falsch sein. Keine Downbeat-Freigabe und keine BPM-/Beat-F1-Behauptung.
- A02-Wechsel 70–80 s wurde nicht fachlich geprüft: Struktur-/Spektralanalyse und Tonarterkennung waren deaktiviert.
- VRAM-Log meldet Buchhaltung 13324 MB gegenüber Sensor 15673 MB. Diese Zahlen bezeichnen verfügbare Reserven, nicht 15 GB gemessenen Verbrauch. Warnung allein beweist keine fremde GPU-Arbeit. Keine lückenlose Peak-VRAM-/RAM-Messreihe; Ressourcenobergrenzen bleiben offen.
- Deprecation-Warnungen für Starlette/httpx und pkg_resources beobachtet. Keine Installation oder Versionsänderung.
- Erste Harness-Vorprüfung erwartete fälschlich Status `ok`; tatsächlicher gesunder Status ist `ready`. Vor Inferenz abgebrochen, Harness korrigiert, neue Ausführungsablage verwendet. Kein Produktfehler.

## Schutz und Gegenprüfung

Alle neun vollständigen Original-SHA-256 stimmen vor/nach dem Lauf und mit reference-manifest.json überein. Recovery-Marker RUNTIME_DIRTY, config.json, data/pb_studio.db sowie vorhandene WAL/SHM-Dateien unverändert gehasht. Marker weder gelöscht noch zurückgesetzt. APPDATA, LOCALAPPDATA und Projektpfad für Testprozesse isoliert. Keine Originale überschrieben; abgeleitete Audiofixtures nur im ignorierten scratch-Verzeichnis. Keine Medien/Bilder in diesem Berichtordner.

Keine ComfyUI-Steueranfragen, keine Aufträge gestoppt/entladen, keine Generierung. Standardports 8765/8188/1234 vor den Prüfläufen ohne Listener; das ist keine Inventur sämtlicher möglicher fremder Dienste. GPU-Sperren sind prozessintern. Beide eigenen Prüfprozesse endeten mit Exit 0; RAFT explizit entladen. Kein produktiver Backendstart und keine Recovery-/Migrationsfreigabe.

## Belege und nächster Schritt

run-1.json: A01/A02. run-2.json: A03/V01–V06. provenance.json: Gitstand und Harness-/Modellhashes. Private ausführbare Harnesses verbleiben an den dort genannten scratch-Pfaden. Berichte enthalten Messergebnisse, keine Originalmedien. Sämtliche JSON-Belege zurückgelesen; 9 Quellen × 2 Wiederholungen und Quell-/Schutzdateihashes gegengeprüft.

Als Nächstes BeatNet-Fehler reproduzierbar eingrenzen und Downbeat-Ausgaben gegen unabhängig markierte Taktanfänge prüfen. Bildinhaltsanalyse, exakte Musiklabels, Gesamtclips, Ressourcenpeaks, unabhängiger Holdout und GUI-Nutzung bleiben gesonderte offene Nachweise. Keine Qualitätsgrenzen aus diesen wenigen Läufen ableiten.
