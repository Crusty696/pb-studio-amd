# Reviewloop: verbindliche Korrekturen Runden01 und03

Diese Regeln ergänzen Plan Q/P/S, Kommunikationsvertrag und Arbeitspakete. Ausschließlich Planabsicht; alle folgenden Produktprüfungen NOT RUN.

## L01 — Nutzerkontrolliertes Warten ist kein Fehler

Generierungserfolg, Übernahmeentscheidung und Analysebereitschaft getrennt persistieren. LogicalJob awaiting_import ist ein dauerhafter nichtterminaler Nutzerwartezustand; Activity-/Lease-/Closeprüfung behandelt ihn nicht als laufenden Worker. Artifact-/Importsagazustand awaiting_import sichert valide owned Stagingbytes samt Hash/QC/Provenance; bloß deaktivierter Autoimport erzeugt keine Quarantäne. Noch laufende Pflichtoutputs werden weiter verfolgt; Job erst parken, wenn keine sonstige Pflichtarbeit läuft.

Bewusster Import erzeugt weiterhin neuen lokalen Intent/Claim ohne neuen Generierungsattempt. Durable relation origin_job_uuid→import_intent_uuid→import_receipt_uuid bindet Original und Fortsetzung. Die nichtterminale ursprüngliche Importsaga darf unter CAS den freigegebenen Import fortführen; genau ein Artifactpublikations-/Medieneintrag. Nach Catalogcommit Originaljob available_partial, nach echten Pflichtreceipts ready; der lokale Importintent besitzt eigenen dokumentierten Abschluss. Bereits cancelled/obsolete Originaljobs bleiben terminal. Ein bewusst neu freigegebener Import aus terminaler Quarantäne erhält eine neue lokale Importsaga ab discovered mit erneuter Hash/QCprüfung des erhaltenen Artefakts; terminale alte Saga und ursprüngliche Provenance bleiben unverändert.

Autoanalyse=false belässt die Importsaga catalog_committed mit analysis_not_requested und Job available_partial. Keine automatische Analyse, kein aktiver Worker, kein GPUlease, kein Retry/Endlospolling. Explizites POST /jobs/{id}/analyze erzeugt idempotenten AnalysisContinuationRequest/Receipt; Import-/Projekt-/Revisionsbindung und noch fehlende Pflichtstages prüfen. Native-MVPanalyse hat keinen neuen Comfy-Generierungsattempt. Spätere alternative Analyseprovider besitzen ihre eigenen klar typisierten Analysejobs, niemals heimlich eine zweite Mediengenerierung.

Restart rekonstruiert Nutzerwartepolicy, Intents und Receipts ohne automatische Freigabe. Batchprojektion trennt ausführung_fertig von medien_bereit und wartet_auf_nutzer; ein geparkter Batch meldet weder unendliche aktive GPUarbeit noch Gesamtbereitschaft. Retention schützt wartende Ergebnisse bis bewusstem Abbruch/Archivierung und separat freigegebener Löschung; keine stille TTL-Löschung. Cancel/obsolete während Import/Analyse nutzt bestehende CAS-/Drainregeln; spätere Importreceipts reaktivieren keinen terminalen Originaljob. UI zeigt Übernehmen/Analysieren/Abbrechen und Ursache; Workflow-/Jobwire-Enummapping ausdrücklich ergänzen.

Endabnahme T026: alle vier Autoimport/Autoanalyse-Kombinationen, mehrere Pflichtoutputs, Restart, spätere Freigabe, verlorene Antwort/Doppelklick, Cancel im Fortsetzungsrennen. Keine ungewollte Analyse, keine doppelte Katalogzeile und kein neuer Generierungsattempt. T010/T011/T019/T021/T022/T024/T025 liefern vorher ihre isoliert prüfbaren Teilverträge.

## L02 — Reshot vor seiner vollständigen Timelineabnahme

T040 hängt zusätzlich von T030 ab. FP17-Endabnahme verwendet erst danach einen real qualifizierten Reshot-Child. Allgemeine Variantenfixtures ersetzen diesen Nachweis nicht. Keine weitere Nutzerentscheidung erforderlich; ursprünglicher Reshotzielumfang bleibt erhalten.

## L03 — Unbeaufsichtigte Longform benötigt qualifizierte Koordination

T041/Phase-Manifest unterscheidet G8-shared-supervised und G8-managed-unattended. Ersteres verwendet ausdrücklich beaufsichtigtes observed_shared mit dessen Grenzen. Verlässlich unbeaufsichtigte Freigabe verlangt bedingt T016 einschließlich vollständiger lokaler Consumerintegration, qualifiziertem tatsächlich kooperierendem Scope und Cleanup-/Lease-/Nichtkooperatorprüfungen. T016 bleibt keine erste MVPpflicht, wird aber zwingende Vorgängerfreigabe für diesen später gewählten Betriebsclaim. Runtime darf ein ungeeignetes Profil nicht allein wegen leerer Queue in unattended hochstufen.

## L04 — Pflichtdokument unabhängig vom optionalen Wizard

T045 ist Createowner von docs/comfyui/developer-guide.md. Der Guide entsteht phasenweise mit den tatsächlich gelieferten Verträgen; geplante Kapitel bleiben als geplant erkennbar. T044 konsumiert ihn nur und liefert bei gewähltem Wizard seine Ergänzungen über T045. Vollständiger Pflichtscope liefert architecture.md, installation.md, workflow-format.md, provider-system.md, troubleshooting.md und developer-guide.md ohne Wizard. Phasen-QC prüft nur bereits fällige Abschnitte, keine vorgezogene Vollständigkeit späterer Funktionen.

## L05 — Workflowinhalt und Aktivierung besitzen verschiedene Revisionen

WorkflowRevisionKey bleibt unveränderliche Contentidentität. WorkflowActivationReceipt trägt enabled, activation_revision und registry_generation sowie opaken Token. Aktuellen Receipt aus GET /workflows lesen; PATCH mit expected_activation_token/client_request_id. Gleicher Mutationintent/Payload liefert denselben Receipt, anderer Payload409. Fremder/veralteter Token409; erfolgreichen Wechsel dauerhaft speichern und erst dann publizieren. Restoregeneration verhindert Wiederverwendung alter Tokens.

Enable-off verhindert neue, noch nicht autorisierte Dispatches. Freigabeprüfung und lokale durable Dispatchautorisierung werden mit Aktivierungswechsel linearisiert; bereits mögliche Sends werden beobachtet/bei ausdrücklichem Cancel gezielt abgebrochen. Disable allein schreibt keine terminalen Receipts um. Kein Lock über Netzwerkwartezeit. T005 liefert Repository-/CASteil; T022 API; T024 vollständige UI-Endabnahme mit zwei Fenstern, Antwortverlust, Replay und Reopen.

## L06 — Autoritative spätere Nichtannahme löst Unknown

Q2 erlaubt submission_unknown/needs_decision→rejected nur mit exakt gebundenem autoritativem Nichtannahmereceipt oder nachweislichem Nicht-Send. Ein validierter später verarbeiteter Requestreceipt kann genügen; generisches Proxy400/5xx, Connectionloss und leere History/Queue nicht. Widerspruch zu vorhandener Annahme/Ausführung erzeugt Conflict, keine Retryfreigabe. Danach unveränderte Retrypolicy/Budget; neuer Attempt mit neuer Prompt-ID erst nach definitiver Entscheidung. T010 Zustandsvertrag; T012 Transportreceipt; T013 vollständige Reconciliationprüfung; T014 Retryregression.

## L07 — Native-Analyseidentität ohne erfundenen Comfyauftrag

ResultEnvelope diskriminiert execution_kind=native/comfy. Result-/Projekt-/Sourceidentität bei Analyse zwingend; job_uuid nur bei tatsächlichem aktuellen PB-Ausführungskontext. Comfy benötigt gebundenen Remoteattempt, Prompt und Workflow; Native führt diese Felder als null/not_applicable und bindet lokale Algorithmus-/Code-/Processor-/Config-/Adapteridentität. Modellidentität ist bei modellbasierten Verfahren erforderlich, bei reinem Native-DSP explizit nicht anwendbar. Q6 bleibt für unbekannten effektiven Comfygraphen maßgeblich; kein neuer erfundener Hashpflichtnachweis.

AnalysisRun ist die persistierte analysebezogene Projektion des validierten gemeinsamen Kontexts. Herkunft des analysierten Mediums (origin_generation_job/attempt) bleibt von aktueller Analyseausführung getrennt. Nativeanalyse nach Comfygeneration übernimmt niemals den Generierungsattempt als eigenen Ausführungsattempt. Nativeanalyse einer bestehenden Datei ohne jeglichen Comfyjob bleibt möglich; Cache-/Stagedependencyregeln gelten unverändert.

T008 prüft diskriminierte Schemafälle inklusive verbotener künstlicher Remoteidentität; T009 persistiert/projiziert beide Kontexte konsistent; T020 weist den schmalen echten Native-SigLIP-Run vor MVP nach; T031 liefert vollständige Native-Capabilitydurchleitung. Gegenfälle: reine Native-DSP-Analyse ohne Modell/Remotejob, modellbasierte Nativeanalyse bestehender Datei, Native-SigLIP nach Comfyimport und echte Comfyanalyse. Vorhandene lokale/Remoteherkunft weder erfinden noch vermischen. Konkrete öffentliche DTO-/Schemafreigaben bleiben Gapi/O04.
