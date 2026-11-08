# T010 — isolierter Vertragsentwurf, offen

## Ausgefuehrt

T008-Vorgaenger abgeschlossen. Plan S erlaubt T008–T010 reine Verträge/Testfixtures vor G1; produktive Persistenz bleibt an G1/Gmigration gebunden. Q1/Q2/Q3-Transitionskarten und minimale ProjectIdentity/ProductionBatch/LogicalJobSnapshot/AttemptIdentity/ArtifactReceipt als additive Python-Module angelegt. Katalog-/Datei-Projekt-UUID muessen uebereinstimmen; runtime_epoch aendert die persistente UUID nicht. CAS prueft state_revision; unbekannte Kanten und unbelegte Guardkennungen werden abgewiesen. Terminale Job-/Attempt-/Artifact-Zustaende bleiben terminal. Wartende Importausgabe gilt nicht als Fehler. Fruehe Remote-Beobachtung ueberspringt Dispatch nicht; Unknown/Cancel wird nicht durch leere History oder HTTP200 als abgelehnt/beendet interpretiert.

## Tests

Vor Implementierung schlug Import von `pb_studio.jobs` fehl. Nach erstem Modell: 7 gezielte Tests bestanden. ProductionBatch-Gegenfall zeigte fehlenden Typ per Importfehler; danach 10 gezielte Tests bestanden. Abschliessende isolierte Cross-Regression mit T008/Comfy-Vertraegen: 96 Tests und 27 Subtests bestanden; `py_compile` und `git diff --check` erfolgreich (CRLF-Hinweis ohne Diff-Fehler).

## Grenzen / naechster Schritt

Die `evidence`-Kennungen sind lokale Testkategorien, keine gebundenen signierten oder autoritativen Remote-/DB-Receipts. Outbox-, Importclaim-, CAS-Repository-, Crash-/Restart-/Recovery- und produktive Wirevertraege fehlen. Ohne diese darf keine Transition an produktive Jobs angeschlossen werden. T010 bleibt offen, ebenso T002/T007/G1 und Gmigration. Keine DB-/Backend-/ComfyUI-/Medienoperation ausgefuehrt.

## Fortsetzung 2026-10-20

RED: 17 ungültige Job-/Attempt-/Artifact-Snapshots wurden angenommen; nach Validierung 27/27 Tests grün. UUIDs kanonisch, bekannte Zustände und nichtnegative int64-Revisionen werden nun bereits beim Modellbau geprüft. RED: fehlender Wire-Parser; JobReceipt und provider_job_changed-Ereignis mit Pflichtfeldern, explizitem null für attempt_uuid, Enum-, Identitäts- und int64-Prüfung ergänzt. RED: repair_pending verlor die letzte belegte Phase; Rückkehr ist nun ausschließlich dorthin möglich. 30/30 gezielte Tests und 151 Comfy-Vertragstests mit 47 Subtests bestanden; py_compile und git diff --check ohne Fehler. Der erste Cross-Regression-Aufruf enthielt einen falschen Testdateinamen und startete keine Tests; danach wurden alle vorhandenen test_comfyui*.py ausgeführt.

Die Wire-Fixtures sind keine registrierte API/OpenAPI oder WPF-Parität. Die lokale Kategorie `recovery_verified` und noch ungebundene lokale Guards sind keine echten DB-Receipts; Persistenz, Crash-Recovery und produktive Übergänge bleiben offen. T010 bleibt [ ]. Keine ComfyUI-Läufe.

## Fortsetzung 2026-10-20: Attempt-Belegbindung

RED: Freitext `authoritative_not_accepted` konnte Unknown als sicher abgelehnt markieren; ein neuer Gegenfall zeigte, dass selbst gleicher Receipt-Hash mit anderem terminalem Belegtyp als idempotent durchging. GREEN: `AttemptReceiptEvidence` erzwingt kanonische Attempt-/Job-/Prompt-UUID, Endpoint und SHA-256 und wird vor Q2-Transition exakt gegen den Attempt gebunden. Autoritative Kategorien und `proved_non_send` erfordern jetzt dieses Objekt. Terminalzustände speichern Belegtyp und Hash; nur identische Wiederholung ist idempotent, abweichende bleibt Konflikt. 31 gezielte und 152 Comfy-Vertragstests/47 Subtests bestanden. WPF Release-Build 0 Warnungen/0 Fehler und 86 WPF-Tests bestanden; keine neue WPF-Funktion implementiert. Der Typ beweist selbst keine Herkunft: qualifizierter HTTP-/WS-/History-Adapter, durable Store, Widerspruchsabgleich und G1/Gmigration fehlen weiterhin. T010 bleibt offen.

## Weitere Q2/Q3-Gegenfälle

RED: `catalog_committed→catalog_committed` fuer `analysis_not_requested` fehlte; `cancel_requested` verlor beim Wechsel nach `needs_decision` den Cancelintent. GREEN: ArtifactReceipt haelt den expliziten Wartegrund; erst ein bewusster Analyseintent entfernt ihn. AttemptIdentity haelt den Cancelintent auch im ungeklärten Zustand. 32 gezielte und 153 Comfy-Vertragstests/47 Subtests bestanden. Das sind Zustandsfixtures; dauerhafte DB-Claims, echter Remote-Cancel und Recovery bleiben offen.

## Fortsetzung 2026-10-20: Terminalereignisse

RED: Q1-Terminaljobs akzeptierten ein frei gesetztes `same_event`; Q3-Terminalartefakte ebenfalls. GREEN: `JobTerminalEvidence` bindet Event-UUID, Job- und Projekt-UUID und Belegtyp. Q1 speichert Eventidentitaet und Typ; nur die exakt gleiche Wiederholung bleibt idempotent. Q3 lehnt unbelegte `same_event`-Wiederholungen ab, bis ein persistenter Importreceipt diese Identitaet liefert. 34 gezielte und 155 Comfy-Vertragstests/47 Subtests bestanden. Die Evidence-Typen sind weiterhin Offline-Fixtures ohne autoritativen Domaincommit; T010 bleibt offen.
