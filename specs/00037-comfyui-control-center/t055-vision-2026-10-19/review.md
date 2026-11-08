# Unabhaengige Gegenpruefung T055/T056

## Rollen

- Transport-/Videoanalyse: native Eingaben, Parser/Rohantwort, ONNX-Eingangsgraph und abschliessender Identity-Callerreview; keine Produktedits durch Reviewer.
- Modellanalyse: vorhandenes Inventar, Bildtransport und Reasoning-Grenzen; kein Modellwechsel/Download.
- CPU-Testautor: unabhaengiger HF-PIL-Processorvergleich, rot/gruen; spaeter isolierte Reparatur eines bestehenden zeitabhaengigen Tests.
- Brain-/Identitaetsentwickler: Modellversion, Persistenz/Reload, Cache/Backfill, Vektorsuche und Videokonsumenten. Shared app_state.py ausschliesslich Hauptagent.
- Hauptagent: echte Bild-/DirectML-Serien, Integration, unabhaengige konsolidierte Tests, Hashschutz und Dokumentation.

## Findings und Abschluss

1. Vorverarbeitung CLIP statt SigLIP: lokale Processorconfig plus ONNX-Graph, sieben rote Referenztests; korrigiert und echt mit DirectML ausgefuehrt.
2. Neue Bildvektoren duerfen nicht mit altem1152D-Raum vermischt werden: v2-Identitaet bindet Producer, Reuse, Persistenz/Reload, Braincache und Backfill.
3. Erster Identity-Diff filterte nur gespeicherte Kandidaten, nicht Queryherkunft: explizite Queryidentitaet ergaenzt, unbekannt/v1 verweigert. Alle vier search-Aufrufer in src/backend geprueft.
4. VideoSpecialist-Nebenpfad erzeugte neue Vektoren ohne Identitaet: Producerstempel nach Benutzer-Metadaten ergaenzt.
5. Benutzerdefinierter Videoindex video_clips_demo umgeht namensgebundenen Storefilter: VideoSpecialist prueft Kandidatenidentitaet nun unabhaengig vom Indexnamen, auch in-memory. Beispielcaller uebergibt Herkunft seines frisch erzeugten Queries. Zwei Regressionen ergaenzt.
6. Bestehender Cooldown-Test:10ms Echtzeitfenster bei paralleler CPU-Last abgelaufen;107 Tests bestanden, einer scheiterte. Test nutzt jetzt ausschliesslich im Wrapper-Namensraum kontrollierte monotonic-Uhr, prueft Sperre und exakten Ablauf. Produktzeitverhalten und asyncio-Uhr unveraendert. Drei getrennte Wiederholungen bestanden; abschliessender Cluster separat dokumentiert.

Abschliessender read-only Codegegenreview fand keine weiteren belegten Fehler im geaenderten Scope. Generischer VectorStore mit anderem Indexnamen erzwingt keine Videoidentitaet; beim geprueften VideoSpecialist ist dafuer der Consumer verantwortlich. Keine Aussage ueber beliebige externe Aufrufer oder nachtraeglich manipulierte Herkunftsfelder.

## Beleggrenzen

pytest-identity-initial-red.txt enthaelt fuenf sachliche Vorherfehler und einen Fehler im urspruenglichen Testaufbau (Projector-Aufruf); dieser sechste Fehler ist kein Produktbefund. Beim Aufbau der Regression wurde ein kuenstlicher Repo-Mock korrigiert und object.__new__ statt Singletonregistrierung eingesetzt. Bestehende semantische Testfixtures erhielten explizite aktuelle Herkunft; ihre Auswahlassertions bleiben bestehen. Alte Tests mit absichtlich unbekannter Herkunft erwarten weiterhin Verweigerung/Fallback.

Tests und native Modelllaeufe sind getrennte Nachweisarten. Kein neues .completed/.qc-passed fuer das Gesamtprojekt, keine GUI-/Altprojekt-Abnahme, kein unabhaengiger Holdout. Medien-/Quellschutz und Testresultate siehe media-validation.json und final-validation.json.
