# Umbau: belegter Stand 2026-10-20

Neueste Nutzerentscheidung: ComfyUI-Lauf T007 ueberspringen. Unabhaengiges T008-Vertragspaket abgeschlossen; T007/G1 offen.

T008-Vertragsgrundlage additiv umgesetzt und isoliert getestet; [Bericht](t008-contracts-2026-10-19/report.md). T008-Vertrag abgeschlossen. Numerische QualityProfile-Grenzen bleiben T002, echte Consumerabnahme T031; keine Produktintegration behauptet.

T010 als reiner Zustands- und Wirevertragsentwurf fortgesetzt; [Teilbericht](t010-contracts-2026-10-20/report.md). 34 gezielte Tests, 155 Comfy-Vertragstests/47 Subtests bestanden. Attempt-Receipts und Q1-Terminalevents an Identitaeten gebunden, Q3-`same_event`-Freitext abgewiesen, Cancelintent und Analyse-Wartegrund bewahrt; echte Autoritaet, API-/WPF- und Persistenzbindung fehlen, T010 offen. WPF-Release-DLL gebaut (0 Warnungen/0 Fehler), 86 WPF-Tests bestanden; keine neue WPF-Produktfunktion oder sichtbare Laufabnahme.

Fruehere Livepruefung am 19.10.: ComfyUI nach fremdem Neustart kurz erreichbar, Queue **1 laufend / 0 wartend**. Am 20.10. verweigerten 8188/8190 die Verbindung; im Prozessabgleich war kein Comfy-main.py/Filmrunner belegt, doch die Filmstatusdatei blieb bei `running`. Das beweist keinen sicheren Abschluss. Nutzer hat ComfyUI-Laeufe weiter verschoben; kein eigener Pilot.

Vorherige T007-Vorpruefung am 19.10.: Nutzer hatte T002 fuer die Arbeitsreihenfolge uebersprungen. Externer ComfyUI-Server0.41.2 auf8190 waehrend Pruefung weggefallen; fremder Filmtest mit Stopanforderung und running-Eintrag. Kein Pilot gestartet, kein G1. [T007-Bericht](t007-preflight-2026-10-19/report.md). Die damals nicht ausgefuehrte CPU-Tonartprobe wurde am 20.10. nach erneuter Anweisung zum Weiterarbeiten ausgefuehrt; T002 bleibt offen.

Lesbare Gesamtübersicht: [masterplan-status.md](masterplan-status.md). Statuspflege nach Nutzerhinweis auf Wiederholungsschleifen: vorhandene Belege verwendet, keine neuen Modell-/Medientests. 11 erledigte Teilaufgaben T046-T056 bleiben getrennt von 6 erledigten Hauptpaketen. T055-Untersuchung erledigt, Erkennungsqualität weiterhin offen.

## Umsetzung

6 von 45 urspruenglichen Paketen abgeschlossen: T001, T003, T004, T005, T006, T008. 39 offen, einschliesslich T002/T007 und wiederkehrendem T045; Paketanzahl ist kein Aufwand-Prozentsatz. Wellen A/B belegen Bibliotheks-/Vertragsumfang, keine fertige WPF-ComfyUI-Steuerung. Belege: wave-a/, wave-b/. Letzter zuvor verifizierter Codecommit: 71e086493f122fb5a24e5a3e83039d9d7dac9621.

## T002

- Sechs Videos V01-V06 und drei Audioquellen A01-A03 ausgewaehlt; Nutzerbewertungen gespeichert in t002-human-review-2026-10-19/. Herkunft reicht fuer Regression; unabhaengiger Holdout bewusst offen.
- CPU-Teilpruefung 9/9 Quellen; begrenzte GPU-Teilpruefung 18 Laeufe: Audio Beat This und Video RAFT-Bildpaare. Belege: t002-cpu-check-2026-10-13/, t002-regression-preparation-2026-10-13/technical-countercheck-2026-10-19.md, t002-gpu-check-2026-10-19/. Keine vollstaendige Clip-, Caption-, Ressourcenpeak- oder GUI-Pruefung.
- T046/T047: BeatNet-DBN-Kompatibilitaet repariert. T048/T049: Dateizustand wiederverwendeter Instanzen isoliert. 63 gezielte Tests und A01-A03 CPU-Reihenfolge-/Wiederholungspruefung bestanden. Belege: t002-beatnet-fix-2026-10-19/, t002-beatnet-state-fix-2026-10-19/qc-report.md. Historische Fehlerberichte bleiben erhalten; ihre damaligen Aussagen sind keine aktuellen offenen Kompatibilitaetsfehler.
- Offen: musikalische Richtigkeit der Taktanfangslabels (insbesondere A01/A03); exakte unabhaengige Beat-/Downbeatreferenzen; qualifizierte Nativebaseline, Ressourcen-/Qualitaetsgrenzen, Holdout und sichtbare Produktabnahme. A02 70-80 s: unsicherer Wechsel, Stimmen/weniger Bass/leiser laut Nutzer; kein bestaetigtes Strukturklassifikationslabel.
- T051 abgeschlossen: A01-A03 CPU-Spektral-/Strukturmodule im Fenster 60-90 s, je zwei identische Wiederholungen. A02 70-80 s messbar leiser/bassaermer; Stimmen und genaue Strukturklassifikation ungeprueft. Beleg: [Bericht](t002-spectral-structure-2026-10-19/report.md).
- CPU-Tonart-Teilprobe A01-A03 am 20.10.: zwei Arrayaufrufe und derselbe Chroma-Pfad pro Quelle reproduzierbar `F# minor`; Original-/Schutzdateien hashgleich. Keine unabhaengigen Tonartlabels, keine musikalische Abnahme. [Bericht](t002-key-2026-10-19/report.md).
- T002-Manifest-Offlinepruefer: neun gezielte und 50 Vertragstests insgesamt bestanden; aktueller Neun-Quellen-Bestand strukturell konsistent, aber `qualification_ready=false` mangels Holdout, unabhaengiger Labels, Profilen und Messungen. Nicht authentifizierte Receipt-Strings koennen den Pruefer nicht freischalten. Kein Produkt-Gate oder Qualitaets-PASS. [Bericht](t002-manifest-2026-10-20/report.md).
- T052 abgeschlossen: V01-V06 vollstaendige CPU-Szenenerkennung, je zwei Laeufe, Framezahlen gegen ffprobe bestaetigt, Softwaredecode, unveraenderte Schutzdateien. Alle sechs Clips durch No-cut-Ersatzpfad als eine Szene ausgegeben; keine Szenengrenzenqualifikation. Beleg: [Bericht](t002-scenes-2026-10-19/report.md).
- T053 abgeschlossen: sechs bewertete Standbilder je zweimal durch nativen Caption-Wrapper, 12 echte Antworten mit Gemma 4 E4B ueber vorhandenes Vulkan 2.60.0. Qwen-Override fehlt im Live-Inventar; vorgeladenes Gemma wurde als Ersatz genutzt, Konfiguration unveraendert. Quell-/Schutzdateien identisch, eigenes Modell anschliessend entladen. Technischer Teilnachweis bestanden, Qualitaet nicht freigegeben: erfundene Gruppen V02/V05, fehlender Wasserfall V03, wichtige Detailverluste. Parser schneidet sechs elfte Tags ab, darunter Blitzschlag. [Beleg](t002-caption-2026-10-19/report.md).
- T054 abgeschlossen: Budget12 bis zum Clip-Merge, Hautfilter und numerische Gruppenregel repariert; Kandidat2-Prompt anhand realer Vergleiche uebernommen. 101 Tests bestanden, 84 echte Aufrufe inkl. verworfener Varianten; letzte12 mit endgueltigem Code. Original-/Schutzdateien gleich, Modell entladen. Qualitaet bleibt begrenzt: V03 Wasserfall/Zweizahl und V02 Torform/Ort fehlerhaft; kein GUI-Nachweis. [Bericht](t054-caption-2026-10-19/report.md).
- T055:42 neue Caption-Aufrufe pruefen native Aufloesung, JPEG/PNG, Reasoning und18 native Bilder/drei Zeitpunkte pro Clip. T053/T054 waren480x270-Vorschautests, kein Originalframe-Nachweis. V03 erkennt am spaeten Zeitpunkt Wasserfall und erhaelt ihn im Clipmerge; mittlerer Einzelbildfehler und V02-Orts-/Formfehler bleiben. Keine globale Transport-/Reasoningumstellung. [Bericht](t055-vision-2026-10-19/report.md).
- T056: SigLIP-Vorverarbeitung verwendete belegbar CLIP- statt SigLIP-Normalisierung; auf0.5/0.5 korrigiert, Einzel-/Batchpfad vereinheitlicht.42 echte DirectML-Inferenzen auf18 nativen Bildern,18 bitidentische Wiederholungen; Quell-/Schutzdateien gleich, eigenes Modell entladen. Identitaet jetzt siglip_vision/onnx-dml-v2: Altvektoren und unbekannte Queries werden nicht mit neuen Vektoren vermischt, Reuse/Persistenz/Reload/Backfill abgesichert. Keine Migration/Neuberechnung; alte trainierte Projektorgewichte werden bei Versionskonflikt unveraendert abgelehnt. Textencoder fehlt, daher kein Text/Bild-Semantiknachweis.
- Naechste offene Prueffamilien: semantische Caption-Abnahme V02/V03 und weitereZeitpunkte ohne unabhaengige Labels; SigLIP-Rangfolgenqualitaet/fehlender Textencoder; genaue unabhaengige Beat-/Downbeat- und Szenenreferenzen; Tonart/Stems und Volltrack-/Langdateipfade; lueckenarme Ressourcenmessung; sichtbare Produktkette. Neue Probe nur mit begrenztem Laufvertrag und aktueller Lastpruefung; GPU nicht aus vergangenen Leerlaufwerten als frei annehmen. Technische T055/T056-Belege schliessen T002 nicht ab.

## Betriebliche Nacharbeiten

Eine fruehe nicht isolierte Pytest-Ausfuehrung oeffnete produktive BrainStore-Seitendateien. embedding_cache.db wurde danach als malformed erkannt; Vorherhash fehlt, Schadensursache unbekannt. Auf ausdruecklichen Nutzerauftrag anschliessend aus der neuesten vollstaendigen, geprueften Sicherung vom 01.10.2026 wiederhergestellt: 247 Cache-Eintraege, 247 referenzierte Vektordateien vorhanden, quick_check ok. weights.db und patterns.db ebenfalls quick_check ok. Das ist ein Restore eines aelteren Cache-Stands, keine nachgewiesene vollstaendige Bergung aller eventuell neueren Eintraege.

Lokaler Beleg: `%APPDATA%\PB_Studio\backups\manual_repair_embedding_cache_20261019_213200\repair-manifest.json`; beschaedigte DB und WAL/SHM dort erhalten. Kein Produktneustart/GUI-Nachweis daraus ableiten.

## Wissensspeicher und Grenzen

Nutzerkorrektur: Obsidian wird nicht mehr als Projektgedaechtnis verwendet. Neues KI-Hirn unter `http://127.0.0.1:3000`; Recall und MCP-Handshake mit hirn_recall/hirn_remember bereits erfolgreich geprueft. Codex-Konfiguration gesichert und um ki-hirn erweitert. Erinnerungen koennen veraltet sein; konkrete Repo-/Pruefbelege und aktuelle Nutzerentscheidungen haben Vorrang. Synchronisation dieses Stands ist jetzt ausdruecklich beauftragt.

PB bleibt DirectML; externe ComfyUI-ROCm-Ausnahme gilt. Cloud liegt ausserhalb des PB-Umbaus. Originale und laufende Auftraege schuetzen. Keine Generierung, Installation, Migration oder Wiederherstellung alter Projekte aus diesem Auftrag ableiten. T007 braucht weiterhin konkret gebundenen, freigegebenen Pilotlauf. G1/Gesamt-T045/Produktabnahme offen.

## KI-Hirn-Synchronisation

Aktueller Stand als neue, datierte Statuskorrektur gespeichert und exakt zurueckgelesen. Beleg: ki-hirn-sync-2026-10-19.json. Historische Erinnerungen nicht geloescht; dieser Stand ersetzt deren veraltete Offen-/Nichtgemessen-Aussagen. T050 abgeschlossen.

Ergaenzung T053: siehe t002-caption-2026-10-19/ki-hirn-sync.json fuer den separaten Schreib-/Ruecklesebeleg. Technischer Caption-Nachweis und negative Qualitaetsbefunde getrennt halten; T002 bleibt offen.

T054 im KI-Hirn separat mit Reparaturen, negativen Qualitaetsbefunden und Tradeoffs synchronisiert; Schreib-/Ruecklesebeleg t054-caption-2026-10-19/ki-hirn-sync.json. Historische T053-Filterfehler sind damit behoben, dessen fehlende Gesamtqualitaetsfreigabe bleibt bestehen.

T055/T056 technisch im dokumentierten Scope abgeschlossen:186 verschiedene gezielte Tests bestanden (108+78), unabhaengiger Review ohne verbleibenden belegten Scopefehler. Belege t055-vision-2026-10-19/final-validation.json und review.md; kein Gesamtprodukt-PASS. Neues KI-Hirn mit genau diesem Stand gespeichert und per ID/Text exakt zurueckgelesen: t055-vision-2026-10-19/ki-hirn-sync.json, ID1792442895275. Fruehere Erinnerungen behalten ihren historischen Charakter; T002 und semantische Qualitaet bleiben offen.


Planpflege nach Wiederholungshinweis: vollständige Paketübersicht und Haken konsistent abgeglichen, keine neuen Laufprüfungen. Neuer KI-Hirn-Eintrag mit Arbeitsregel und Zählung exakt zurückgelesen; Beleg masterplan-status-sync.json.
