# T002 / T053 — Bildinhaltsanalyse, 2026-10-19

## Ergebnis und Umfang

Technischer Teilnachweis bestanden, semantische Qualitaet nicht freigegeben. Sechs zuvor vom Nutzer bewertete Referenzbilder V01-V06, je zwei echte HTTP-Inferenzen mit geleertem PB-Tagcache. Kein Vollvideo-Verstaendnis, kein zeitlicher Bewegungsnachweis, kein unabhaengiger Holdout. Native Funktion `extract_tags_and_model_via_lmstudio` mit unveraendertem Standardprompt und Parser; keine Router-/WPF-/DB-Abnahme. Produktcode unveraendert.

## Laufbedingungen und Schutz

- LM Studio war anfangs aus. Lokalen Dienst fuer die autorisierte Analyse gestartet. Erste Inventarabfrage waehrend Initialisierung meldete voruebergehend keine Runtimes; erneute Abfrage bestaetigte vorhandene, bereits ausgewaehlte Vulkan-Runtime 2.60.0. Keine Installation/Runtimeumstellung.
- Konfigurierter Override `qwen3.5-9b` fehlt im aktuellen LM-Studio-Inventar. Vorhandenes bildfaehiges Modell `google/gemma-4-e4b`, Q4_K_M, fuer den begrenzten Versuch vorgeladen (Kontext 4096, GPU max, TTL 600 s). Native Wrapper-Modellauswahl ohne expliziten Modelloverride verwendete dieses Modell. Das beweist Auswahl bei vorgeladenem Gemma, keinen Kaltstart des urspruenglich konfigurierten Qwen.
- Ausgefuehrter Prozess: `llama.cpp-win-x86_64-vulkan-avx2-2.60.0/llama-server.exe`, siehe runtime-process.json. PB-DirectML-Regel bleibt bestehen; externe LM-Studio-Vulkan-Ausnahme genutzt.
- Frische LHM-Messung: RX 7800 XT, monitoring_status ready, GPU-Last 0 %, belegter GPU-Speicher 3 MiB vor Modellladen. Keine durchgehende Ressourcen-/Peakmessung.
- Eigenes APPDATA/LOCALAPPDATA/TEMP/Projektverzeichnis; Offline-Schalter fuer HF/Transformers. Schutz umfasst sechs Original-SHA-256, vorhandene Projekt-/Brain-DB-Dateien, config.json und Recovery-Marker. Vorher/Nachher identisch. Referenzbild-Hashes stimmen exakt mit Nutzerbewertung ueberein.
- Nur lokaler LM-Studio-Endpunkt und Gemma fuer Inferenz zugelassen; andere Providerinferenz im Harness gesperrt. Keine Bild-/Videogenerierung, keine Medien-/Konfigurationsaenderung, kein ComfyUI-Auftrag gestartet oder gestoppt. Vor Start keine LM-Studio-Modelle geladen; eigenes Modell danach entladen und API-Inventar bestaetigt alle Modelle not-loaded.
- Vorlauf scheiterte vor Inferenz an inzwischen unerreichbarem LM-Studio-Dienst (WinError 10061). Auch dessen abschliessende Inventarabfrage scheiterte; dieser erste Harnessversuch schrieb deshalb keinen Ergebnisbericht. Abschlusspfad anschliessend gegen API-Ausfall abgesichert. Neuer gemeinsamer Dienststart/Probe-Lauf erfolgreich. Ursache des vorherigen Dienstendes nicht belegt; keine Behauptung einer reparierten Dienstlebensdauer.

## Gegenpruefung der Inhalte

Grundlage: gespeicherte Nutzerbeschreibungen und erneute Sichtpruefung des privaten Referenzbogens. Nutzerbewertungen waren angeleitet, nicht verblindet. Keine erfundene Trefferquote.

| Bild | Passende Ausgabe | Fehler / fehlende wichtige Inhalte |
|---|---|---|
| V01, 5 s | Eine weiblich wirkende Figur, Wald, dunkle Kleidung, farbiges Licht | Leuchtende geometrische Formen fehlen. Tanzen wird als sicherer Tag ausgegeben, obwohl Bewegung aus diesem Einzelbild nicht belegt ist. |
| V02, 15 s | Steinerne Architektur, teilweise blau-violett | Beide Laeufe behaupten Gruppe und dunkle Gewaender; im Referenzbild nicht belegt. Innenraum widerspricht der erkennbaren Umgebung; neongruen im ersten Lauf passt nicht zu den auffaelligen violetten Leuchtformen. Tor und schlangenartige Ranken fehlen. |
| V03, 5 s | Zwei weiblich wirkende Figuren, dunkle Kleider, Wasser, Nebel | Wasserfall fehlt in beiden Laeufen; stattdessen unbelegter nebliger Wald. |
| V04, 5 s | Einzelne Figur, dunkles Gewand, Stein und warmes Licht | Fackeln und Steinmauer fehlen als genaue Begriffe. Erste Rohantwort enthaelt Kerzenlicht, aber Parser entfernt es als elften Tag. |
| V05, 5 s | Gewitterhimmel, dunkel/blau, stuermisch, Mensch | Gruppe in beiden Laeufen unbelegt; sichtbare kleine Figur wird nicht korrekt als einzelne beschrieben. Blitzschlag steht im ersten Rohtext, wird als elfter Tag abgeschnitten. |
| V06, 5 s | Gruppe, Wasser, Mondschein, Nacht | Farbige Spiegelungen fehlen. Stehen/Tanzen nicht als zeitliche Bewegung qualifiziert. Keine falsche exakte Kopfzahl ausgegeben. |

## Technischer Befund

12/12 echte Aufrufe mit nichtleeren Tags; alle Antworten finish_reason stop. Keine PB-Cacheantwort als Inferenz gezaehlt. Rohantworten, Model-ID, Endpoint und Tags je Lauf in results.json. Laufzeiten 0,538 bis 5,863 s inklusive Wrapper; nach explizitem Vorladen, kein belastbarer Kaltstart-/Durchsatzbenchmark. Alle sechs Taglisten variieren zwischen den zwei Aufrufen; feste musikalische/visuelle Wahrheit folgt daraus nicht.

Standardprompt verlangt 8-12 Tags, Parser begrenzt auf zehn. In sechs der zwoelf Antworten wird der elfte Tag verworfen. Bei V05 geht damit der konkrete Begriff Blitzschlag verloren, waehrend allgemeine Stimmungswoerter erhalten bleiben. Personen-zuerst-Prompt koennte die erfundenen Gruppen beguenstigen; Ursache ist ohne kontrollierten Promptvergleich nicht bewiesen. Kein Produktfix aus dieser Hypothese abgeleitet.

## Naechste Schritte / Gates

1. Begrenzter Prompt-/Parservergleich auf denselben Referenzen: keine Personen voraussetzen, sichtbare Hauptobjekte priorisieren, keine sichere Bewegungsbehauptung aus Standbild. Rohantwort und Parser getrennt bewerten; keine Modellinstallation erforderlich.
2. Erst nach Gegenbelegen Produktanpassung und gezielte Regression. Fehlenden Qwen-Override und tatsaechliche Ersatzwahl transparent behandeln; keine automatische Konfigurationsumstellung in diesem Auftrag.
3. Danach weitere Zeitpunkte/Vollclip-Aggregation und SigLIP separat pruefen. Router, Persistenz, SSE und WPF bleiben eigenstaendige Abnahme.

T053 als begrenzte Pruefung abgeschlossen; T002, G1, Qualitaetsfreigabe und Gesamt-T045 bleiben offen. Kein Release-Build erforderlich: nur Pruefharness/Dokumentation, keine Produktbinaries geaendert.
