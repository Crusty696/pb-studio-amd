# PB Studio — manuelle Checkliste

Datum: __________  Tester: __________  Logdatei: __________

Jeden Punkt mit **PASS / FAIL / NICHT GETESTET** und Uhrzeit beantworten. Bei Fehler: sichtbaren Wortlaut, letzter Schritt und Screenshot ergänzen. Nicht weiter testen, wenn Projektidentität oder Datenbestand unerwartet wechseln. Kein Löschen, kein Cache-/DB-Reset, keine Wiederherstellung alter Projekte.

## 1. Logaufnahme einschalten

- [ ] **Vor erneutem App-Start:** Im Explorer `%LOCALAPPDATA%\PB_Studio\recovery-control\v1` prüfen. Nach normalem Shutdown muss `RUNTIME_DIRTY` verschwunden sein. Am 03.10. nach dieser Session blieb er trotz beendeter App bestehen; Ursache noch ungeprüft. Wenn weiterhin vorhanden: nicht löschen und nicht neu starten, erst Recovery-Zustand prüfen lassen.
- [ ] `LOG-AUFZEICHNUNG.bat` im Repository doppelklicken. Das Fenster muss **LOGDATEI: …** und **Aufzeichnung aktiv** anzeigen. Offen lassen.
- [ ] Falls PB Studio bereits läuft: Aufnahme beginnt ab jetzt; vorherige Aktionen fehlen. Für einen vollständigen neuen Test PB Studio selbst normal schließen, Shutdown abwarten, dann über `start.bat` starten. Keine Prozesse hart beenden.
- [ ] Angezeigten Logpfad oben eintragen. Datei liegt in `C:\Users\david\Documents\Pb_studio_AMD_version\logs\sessions\manual_<Zeit>_<ID>.log` und wächst während des Tests.
- [ ] Uhrzeit und erwartetes Ergebnis jedes Schritts hier notieren. Die App zeichnet keine vollständigen Texteingaben, kein gehörtes Audio und nicht jedes interne Ereignis auf. Diese Bewertungen hier ergänzen.

## 2. Richtiges Projekt und Quellen prüfen

- [ ] PROJEKT → Projekt öffnen → **befülltes Unterprojekt** wählen:
  `C:\Users\david\Documents\PBStudio\t013_psy_20260930\t013_psy_20260930`.
- [ ] Angezeigten Projektpfad und Zahlen prüfen. Ausgangsdateien am 03.10.2026: **1 Audio, 61 Videos, 2.889 Timeline-Cuts**. Das äußere gleichnamige Projekt war leer (ID 11); befülltes Unterprojekt ID 10.
- [ ] AUDIO/VIDEO: Medien tatsächlich abspielen. **Bekannter Blocker:** gespeicherte Quellen zeigen teilweise auf nicht mehr vorhandene `E:\02_Musik_&_Medien\…`-Pfade nach Laufwerks-Neuorganisation. Originale wurden in `E:\02_Musik_&_Audio\…` bzw. `E:\03_Video_&_Medien\…` gefunden. Solange Quellen nicht korrekt verbunden sind, Preview/Analyse/Export **NICHT GETESTET — QUELLEN FEHLEN** markieren. Nicht blind erneut importieren oder DB editieren.
- [ ] Projektübersicht mit AUDIO-/VIDEO-Listen vergleichen. Zahlen und Pfad widerspruchsfrei? Ergebnis/Uhrzeit: __________

## 3. Oberfläche und vorhandene Ergebnisse

- [ ] Jeden Tab öffnen: PROJEKT, AUDIO, VIDEO, KI-REGIE, TIMELINE, EXPORT, HIRN, SETTINGS, PERFORMANCE, MODELLE, CHAT, TERMINAL, ANCHOR. Kein Absturz, keine leere Fehleransicht; **INGEST-Tab fehlt absichtlich**.
- [ ] AUDIO: vorhandene Analysewerte, Tempo/Tonart, Struktur und Beatgrid-Zweitschätzung ansehen. Warnung/„suspect“ muss sichtbar bleiben; Zahlen allein beweisen keine musikalische Richtigkeit.
- [ ] VIDEO: vorhandene Szenen, Motion, Tags und Teilanalyse-/Fehlerstatus ansehen. Erfolgreiche Szenen dürfen trotz anderer fehlgeschlagener Stufe sichtbar bleiben.
- [ ] MODELLE: Provider, geladenes Modell und Eignung prüfen. „Installiert“ ist kein „geladen“. Caption-/Chat-Live-Test nur mit tatsächlich geladenem zulässigem Modell; LM Studio Vulkan erlaubt, ROCm verboten.
- [ ] TERMINAL: eigene Klicks und Backend-Meldungen sichtbar? Kein „Terminal leeren“ während dieser Abnahme.

## 4. Analyse und Retry — nur mit verfügbaren Quellen

- [ ] Ein bestehendes Audio aus AUDIO analysieren; Fortschritt beobachten, bis tatsächlicher Abschluss oder klarer Fehler erscheint. Keine Erfolgsbehauptung bei fehlenden Stufen.
- [ ] Kleine bestehende Videoauswahl analysieren. Szenen/Motion/Captions getrennt prüfen; Tags ohne Projekt-Neuöffnung sichtbar?
- [ ] Bei fehlendem Modell: Stufe muss fehlgeschlagen/unverfügbar bleiben. Nach zulässiger Modellbereitstellung dieselbe Auswahl erneut analysieren; echte neue Tags/Stufen prüfen. Fehlertext und Zeiten notieren.
- [ ] Caption-Fakten selbst mit Clip vergleichen: Personen, Handlung, Umgebung. Hautfarbe darf nicht getaggt sein; ab vier Personen Gruppe statt genauer Zahl. Falsch/unsicher/fehlend je Clip aufschreiben. Bestehende menschliche Abnahme ersetzt keine Bewertung neuer Ergebnisse.

## 5. Vorschau, Ton und Scrubbing

- [ ] TIMELINE → Start **0 s**, Dauer **10 s**, „Vorschau rendern“. Fertigmeldung abwarten. Sichtbare Fehlermeldung notieren, falls Quellen fehlen.
- [ ] Vorschau starten. Video läuft; Mastermusik hörbar, beide Stereokanäle plausibel, Dauer etwa 10 s; keine falsche Clip-Tonspur. **Ton selbst anhören**.
- [ ] Während gerenderter Vorschau einen Cut innerhalb 0–10 s auswählen. Gerenderte Vorschau bleibt Quelle; Auswahl unterbricht sie nicht.
- [ ] Timeline fokussieren; Links/Rechts = 0,1 s scrub, Shift+Links/Rechts = 1 s. Bild/Zeitanzeige passen? **Ctrl/Alt vermeiden**, diese können Position/Trim verändern.
- [ ] Cut außerhalb 0–10 s wählen: Vorschau wechselt zu dessen Quelle. Scrub im Clip: Quellstart + Timeline-Versatz muss stimmen. Keine unbeabsichtigten Timeline-Änderungen speichern.
- [ ] Musik-/Bildqualität bewerten: Schnitte passend, Wiederholungen, Thema, Übergänge. Wahrnehmung hier notieren; Log ist kein Qualitätsbeweis: __________

## 6. Export und Abbruch

- [ ] EXPORT: eindeutigen neuen Dateinamen im vorhandenen Projekt wählen, z. B. `…\t013_psy_20260930\output\manual_20261003_01.mp4`. Bestehende Datei nicht überschreiben. AMD-AMF-Encoder verwenden.
- [ ] „Render starten“. **Export rendert vollständige Timeline (ca. 55 Minuten Inhalt), nicht die 10-s-Vorschau.** Aufgabenstatus und Fortschritt sichtbar?
- [ ] Zuerst separaten Abbruchtest: nach tatsächlich gestarteter Aufgabe „Render abbrechen“. Status wird abgebrochen, kein falsches „erfolgreich“. App bleibt bedienbar. Fehlgeschlagene/abgebrochene Artefakte erhalten.
- [ ] Mit anderem neuen Namen vollständigen Export starten und abwarten. Sichtbare **Validierungsphase und Prozentanzeige** beobachten; erst nach Validierungsabschluss Erfolg akzeptieren.
- [ ] Exportdatei öffnen, Anfang/Mitte/Ende ansehen/anhören. Dauer, Musik, Übergänge, letzte Frames plausibel? Das ist eine manuelle Stichprobe; vollständiger Decode/Frame-/True-Peak-Test folgt separat durch Agent.

## 7. Speichern und Wiederöffnen

- [ ] PROJEKT → Speichern. Sichtbarer Erfolg; keine Persistenzwarnung. Projekt-/Medienzahlen und Timeline vorher notieren.
- [ ] PB Studio normal über Fenster-Schließen beenden. Launcher vollständig fertig werden lassen; Recovery-Snapshot kann Zeit brauchen. Nicht Task-Manager/„Task beenden“ verwenden.
- [ ] Über `start.bat` starten, genau dasselbe Unterprojekt öffnen. Pfad, Medien, Analyse, Cut-Zahl und Stichproben der Timeline identisch?
- [ ] Vorschau erneut laden/erzeugen und Wiedergabe prüfen. Projektwechsel/SSE darf keine fremden Projektwerte zeigen.

## 8. Aufnahme beenden und zurückgeben

- [ ] PB Studio normal schließen, Launcher-Abschluss abwarten; dann im Aufnahmefenster **Strg+C**. „LOG GESICHERT: …“ ablesen.
- [ ] Logdatei enthält `RECORDER END`. Bei abruptem Recorder-Abbruch bleiben bereits geflushte Zeilen erhalten, Abschluss kann fehlen.
- [ ] Diese ausgefüllte Checkliste + eine `manual_…log` zurückgeben. Bei Bedarf Screenshots und Exportpfad dazu. Persönliche Pfade/Dateinamen bleiben im Diagnose-Log; Credential-Redaction ist keine Garantie für beliebige sensible Inhalte.

## Ergebnisprotokoll

| Schritt | Uhrzeit | PASS / FAIL / NICHT GETESTET | Beobachtung / genauer Fehler |
|---|---|---|---|
| Projekt/Quellen | | | |
| Tabs/Analyse/Modell | | | |
| Preview/Ton/Auswahl/Scrub | | | |
| Export-Abbruch | | | |
| Export/Validierung | | | |
| Speichern/Wiederöffnen | | | |
| Musik-/Caption-Qualität | | | |

**Gesamtabnahme offen**, solange Quellen fehlen, Pflichtschritte fehlschlagen oder nicht getestet sind. Keine automatische Release-Freigabe durch diese Checkliste.
