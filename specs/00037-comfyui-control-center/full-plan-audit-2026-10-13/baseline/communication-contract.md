# Verbindlicher Kommunikationsvertrag PB ↔ ComfyUI

Stand2026-10-13. Ergänzt plan.md Kapitel V. Alle neuen DTOs, Routen, Tabellen und Abläufe sind [ABSICHT], noch nicht implementiert. D01/D02 und O01–O04 gelten unverändert; Messwerte und konkrete Schema-/API-/Migrationsfreigaben bleiben offen. Cloud gehört ausschließlich zur separaten ComfyUI-Konfiguration.

## 1. Kommunikationsgrenzen und belegter Stand

WPF kommuniziert ausschließlich mit PB über REST/SSE. Das PB-Backend besitzt Jobstore, Scheduler und genau einen Bridgeowner je Endpoint; nur dieser spricht Comfy REST/WS und übernimmt Dateien. Der Benutzer darf Comfy separat bedienen. Fremde Aufträge werden weder verändert noch aus globalem Fortschritt als eigene interpretiert.

Quellprüfung: Comfy HEAD3c1b7a17fdf239d35ce98cc777756f572d089795; lokale Dateien und Hashes im communication-audit-2026-10-13/. PB-Quellen belegen vorhandene Hilfsmethoden, nicht die geplante Bridge. Heutige sechs GET-Probes gegen 127.0.0.1:8188 und :8765 wurden mit WinError10061 abgewiesen; kein aktueller Server-/Integrationsnachweis. Keine Anwendungen gestartet, keine Mutationsroutes oder Workflows ausgeführt.

## 2. Identitäten und Wireformat

Dauerhafte Identitäten: project_uuid, job_uuid, attempt_uuid, client_request_id, artifact_uuid, event_uuid. Je Attempt zusätzlich vor Send eigene remote_prompt_uuid. UUIDs kanonisch lowercase mit Bindestrichen. EndpointIdentity bindet kanonische URL, endpoint_id, Profilrevision und Discoverygeneration. server_boot_identity nur mit unabhängig belegtem Receipt, sonst null/unknown. WS-SID, Version, Gerätemodell oder gleiche URL beweisen keinen gleichen Prozessstart. PB backend_instance_uuid ändert sich pro Start; store_generation_uuid ändert sich bei inkonsistentem Restore/Neuaufbau und bindet Domaincursor.

Neuer PB-Wirevertrag: UTF-8 JSON, snake_case, schema_version=1; Enumwerte explizite lowercase Strings. Keine implizite C#-Enumdeserialisierung voraussetzen. IDs als Strings; Revisionen/Sequenzen nichtnegative int64 innerhalb des vereinbarten Bereichs, Überlauf ablehnen. UTC-Zeit RFC3339 mit Z; Fristen monoton messen. required/null/missing pro DTO im freizugebenden JSONschema/OpenAPI definieren. Pflichtidentitäten nie aus Defaults erraten. Nullable Fortschritt: progress_known=false, progress=null; Listen [] wenn tatsächlich leer, null nur wenn ausdrücklich unavailable. Unbekannte Statuswerte/schema major → incompatible, keine Verwendung als ready. Unbekannte optionale Felder dürfen alte Reader ignorieren; unbekannte Pflichtsemantik nie.

ErrorEnvelope (geplant): schema_version, request_id, error_code, message_safe, retryable, outcome_uncertain, current_revision?, details_safe?. Keine Rohprompts, Tokens oder vollständigen Providertracebacks in UI-/Diagnoselogs. request_id ist Diagnosekorrelation, client_request_id dauerhafte Intentidentität; nicht austauschbar.

## 3. WPF-Befehle: ein Nutzerintent, ein dauerhafter Schlüssel

Vor erstem POST speichert WPF client_request_id + projektgebundenen normalisierten Request + payloadhash dauerhaft im zugriffsgeschützten PendingIntentStore. Sensible Inhalte nicht in Logs; Größe/Retention begrenzen. Unaufgelöste Intents nicht automatisch löschen. Doppelklick und Wiederaufnahme nach Crash verwenden dieselbe ID/Payload. Bewusst neue Variante erhält neue ID. Backendunique(project_uuid, client_request_id) und payloadhash prüfen atomar vor Anlage; gleicher Schlüssel/anderer Inhalt409.

POST /jobs: neue dauerhafte Anlage202 mit JobReceipt; identische Wiederholung200 mit demselben Job und ohne neue Ausführung. Requestheader Idempotency-Key muss client_request_id entsprechen; widersprüchliche Werte400. Angelegte Job-/Outboxrecords werden nicht wegen abgebrochenem HTTPrequest zurückgenommen. JobReceipt: schema_version, request_id, client_request_id, project_uuid, job_uuid, state, state_revision, store_generation_uuid. Location verweist auf /jobs/{job_uuid}.

Geplante Zusatzroute GET /jobs/by-request/{client_request_id}?project_uuid=... liefert vorhandenes Receipt200 oder404. 404 bedeutet nur zum Abfragezeitpunkt kein gespeicherter Intent; erneutes POST ausschließlich mit identischem Schlüssel. Persistierter Tombstone/Minimalreceipt verhindert nach GC eine versehentliche Neuanlage alter Schlüssel; Restore kann jüngere bestätigte Intents verlieren → wiederhergestellte Generation als Reconciliationfall markieren, keine automatische Neuversendung alter WPF-Intents.

Eigener Provider-ApiOutcome pro Request: accepted/definitively_rejected/not_sent_proven/outcome_unknown/transport_unavailable. HTTPstatus und Body gemeinsam auswerten; kein alleiniger null-/gemeinsamer LastErrorDetail-Vertrag. 400/403/409/422 definierte lokale Ablehnungen; malformed/truncated Antwort, Timeout oder Cancel nach möglichem Send → outcome_unknown. 5xx/Proxyantwort niemals pauschaler Nichtannahmebeweis. Lokales CancellationToken beendet Warten, nicht Remotejob. Idempotente PB-Abfrage/Wiederholung darf nur gleichen Intent betreffen. Comfy-POST erhält keinen allgemeinen HTTP-Retryhandler.

## 4. PB → Comfy: exakter Submit- und Socketvertrag

Profilgebundener POST /prompt JSON enthält prompt (APIgraph), prompt_id (vor Send persistierte remote_prompt_uuid), client_id (exakt WS-SID) und optional extra_data für vereinbarte Korrelation ohne Geheimnisse. Antwort des geprüften Profils: prompt_id, number, node_errors. HTTPstatus+Shape+ID prüfen; number ist Queueordnung, keine Identität. Eigene zusätzliche Felder nur mit belegtem Profil; keine UUID als serverseitige Deduplizierung behandeln. Comfy kann gleiche ID mehrfach einreihen und spätere History überschreiben. Deshalb pro Attempt nur ein möglicher Send; unsicherer Send wird reconciliiert, niemals automatisch erneut gesendet. Profile ohne Client-prompt_id sind für ersten automatisierten MVP nicht qualifiziert.

WS-URL verwendet clientId, POST verwendet client_id. Ein PB-Bridgeowner je Endpoint serialisiert Connect/Close; kein überlappender Socket mit derselben SID. Vor Wiederverwendung SID alten Handler vollständig schließen; verbleibendes serverseitiges Reconnectrennen als Degradedzustand erkennen, HTTP-Abgleich bleibt Wahrheitsweg. Optional neue SID erst für neue Attempts; bestehende pinnen alte Identität und werden bei fehlenden Events per HTTP beobachtet. Mehrere Browser-/Fremdclients dürfen eigene SID behalten. Keine Behauptung, lokale Disconnectbestätigung beweise serverseitige Handlerbereinigung.

JSON-Frame und Binärframe getrennt dekodieren. Previewbytes begrenzt verwerfen, nicht als Ergebnisdatei/JSON lesen. status/queue_remaining globales Anzeigesignal; reconnect-executing kann ohne prompt_id kommen und darf keinen Attempt ändern. Fremde oder nicht korrelierbare prompt_id ignorieren/diagnostisch zählen. node IDs bezeichnen Knoten, nicht Jobs. Alle Beobachtungen enthalten local connection_generation, received_at, endpoint/profile und vorhandene Promptidentität.

## 5. Monotone Verarbeitung statt Reihenfolgeannahme

Transportbeobachtung getrennt von Domaintransition. Frühes running/success/error vor HTTP-Acceptreceipt wird begrenzt/persistiert korreliert gesammelt; unknown Identität nie anhand eines einzigen laufenden Jobs erraten. Mit qualifiziertem prompt_id und passendem Queue-/Historyreceipt darf Reconciliation die Annahme belegen und Q2 in zulässiger Reihenfolge queued→running/terminal reduzieren. Fehlt Bindung, dispatching→submission_unknown. Spätes HTTPqueued überschreibt keinen Terminalzustand. Widersprüchliche terminale Belege erzeugen Conflict, keine neue Ausführung. Dedup über unveränderliche Receiptidentität/Hash, ohne erfundene Comfy-event_uuid.

execution_cached belegt übersprungene Nodes; executed liefert Knotenausgabe und ist kein Gesamterfolg. progress/100% und executing node=null geben niemals Library-ready frei. Ein korrekt korreliertes execution_success kann Ausführungserfolg belegen, aber Comfy publiziert History danach. Ergebnisbeobachtung erhält result_evidence_pending (separates Feld, kein heimlicher neuer Q2status); History mit begrenztem Backoff erneut lesen. Ausgabe kann fehlen, verspätet sein oder Pflichtslots verletzen. Dann LogicalJob nach erschöpftem Abgleich needs_decision, kein erneuter Submit; Ausführungserfolg bleibt historische Beobachtung. Importsaga startet erst mit validierter vollständiger Outputreferenz; ready erst nach gesamten Pflichtstages/QC/Import.

Comfy /api/jobs-Statusabbildung: pending→queued; in_progress→running; completed ist zunächst nur Kandidat für success; failed/cancelled ebenfalls mit Rohreceipt prüfen. Der geprüfte Normalisierer verwendet completed auch für fehlenden/unbekannten status_str. Deshalb execution_status.status_str==success oder anderweitig eindeutiges korreliertes terminales Receipt verlangen; error/interrupted differenzieren. /api/jobs/{id}404, /history/{id}200{} oder fehlende Queue-ID bleiben unknown. HTTPerfolg beweist keine fachliche Vollständigkeit.

## 6. Cancel: bestätigter Nutzerwunsch und ungeklärtes Remoteende

LogicalJob wird nach O02 cancelled/obsolete, gewünschte Wirkung dauerhaft gespeichert. Gezieltes POST /api/jobs/{prompt_id}/cancel nur für owned Attempt. Das geprüfte {cancelled:true} unterscheidet Pendinglöschung und Interruptanforderung nicht; es belegt dispatch_accepted, keinen terminalen Zustand. {cancelled:false} beweist weder Erfolg noch Fehler noch Nichtausführung. Vorherige Queueabfrage beseitigt das Pending→Running-Rennen nicht.

Erhält PB autoritatives terminales Receipt, Q2 entsprechend cancelled/execution_succeeded/execution_failed; Job bleibt cancelled/obsolete. Nach bounded Abgleich ohne Beleg: cancel_requested→needs_decision, cancel_intent erhalten, outcome_reason=cancel_outcome_unresolved. Ebenso queued/running→needs_decision bei unaufklärbarer fortgesetzter Beobachtungslücke. Kein aktives Endlospolling, kein Leasefreibeweis, kein Retry. Kontrollierte spätere Reconciliation darf bestehende Q2-needs_decision-Kanten nutzen. Autoritativ bestätigte Pendinglöschung erfordert erweitertes qualifiziertes Serverreceipt; nicht als bereits vorhandene Fähigkeit ausgeben. Kein pauschales /interrupt, /queue clear oder /free als Fallback.

## 7. Dateiübertragung: tatsächliche Referenz verwenden

Geprüfte /upload/image-Route: multipart image plus type/subfolder/overwrite; kanonisches UploadReceipt name/subfolder/type. Kollisionsumbenennung möglich. Eindeutigen eigenen Inputnamespace nutzen, overwrite aus; Referenz für Loader ausschließlich aus validiertem Receipt erstellen. Dateinamen nicht aus Anfrage rekonstruieren. Diese Route allein qualifiziert keinen Audio-/Videoloader.

GET /view benötigt filename (bei Uploadreferenzen aus UploadReceipt.name, bei erzeugten Outputs aus Outputreferenz.filename gemäß qualifiziertem Slotadapter), subfolder und type; Parameter korrekt URL-encoden. Für kanonisches Artefakt keine preview/channel-Transformation. Pfad-/Typ-/Byte-/Hash-/Decode-/Ownerprüfung unverändert. 404/403/abgebrochener Transfer → sichtbarer Transferzustand, Teilstaging nicht veröffentlichen. HTTPtimeout für große Medien getrennt von kleinen Controlrequests; keine Dateiübernahme anhand bloßer Größenstabilität. Externe Comfy-Ausgabereferenzen niemals als PB-Media-ID behandeln.

## 8. PB → WPF: lückenfreier Snapshot und Änderungspfad

Bestehende numerische SSE-id bleibt Transportcursor; sie ist weder event_uuid noch Jobrevision oder Bootidentität. Neuer Eventname provider_job_changed, eigener DTO/Parser und Backendfilter. Envelope: schema_version, event_uuid, store_generation_uuid, job_change_seq, project_uuid, entity_kind (job/batch), entity_uuid, entity_revision; für Jobs zusätzlich job_uuid/attempt_uuid?/state_revision. Eventname bleibt aus Kompatibilitätsgründen provider_job_changed, entity_kind ist verbindlich. SSE ist Hinweis/Invalidierung, kein alleiniger terminaler Beleg. Keine Legacy100%-Fertiglogik; event_uuid/revisionsgebundene Dedup. Zukünftige inkompatible Providerdaten sichtbar melden und Abgleich auslösen.

T011 ergänzt geplantes provider_job_change-Journal im vorhandenen Katalog: store_generation_uuid, monotone job_change_seq, event_uuid, project_uuid, entity_kind, entity_uuid, entity_revision, change_kind einschließlich delete/tombstone. Dauerhaftes Journal gemeinsam mit zugehöriger Domainänderung committen; SSE erst nach Commit. Rollback publiziert keinen wirksamen Change. Erzeugung, Status, Membership, Löschung und Batch-/Reorderänderungen abbilden. Retentiongrenze explizit, nicht mit RAM-SSE-Journal verwechseln. Keine globale Eventlückenheuristik aus projektgefilterten Sequenzen.

GET /jobs liefert für mehrere Seiten konsistente gebundene Sicht: snapshot_id, store_generation_uuid, snapshot_watermark, project_uuid, items[] mit Job-/Batchprojektionen, next_cursor. Alle Seiten dieselbe Sicht; serverseitig bounded materialisieren oder äquivalent belegte konsistente Pagination. Keine SQLite-Transaktion über Netzwerkwartezeiten offen halten. Snapshot-TTL/Maxgröße aus O03profil; Ablauf410/snapshot_expired löst neuen Snapshot aus, keine Mischung. Nächste Seite nur mit opaque cursor, keine clientseitige Offsetrekonstruktion. Große Int64cursor nicht in Float konvertieren.

Statische Routen wie /jobs/changes vor generischem /jobs/{id} registrieren; reale App/OpenAPI und tatsächliche Requests prüfen, kein bloßer isolierter Routertest.

Zusatzroute GET /jobs/changes?project_uuid=...&after_cursor=...&limit=...: dauerhafte Änderungspages mit generation, items, next_cursor, high_watermark und has_more. Cursor ist opak und enthält Scope+Generation+Position; Backend prüft Scope. Bei zu altem/fremder Generation Cursor410/replay_unavailable und vollständigen Snapshot verlangen. Changes liefern Entitätsrevision plus komplette Job- oder Batchprojektion oder entsprechenden Tombstone; keine unvollständigen Deltas, die übersprungene Zwischenstände voraussetzen.

WPF-Sync: neue lokale view_generation beim Projekt-/Backendwechsel; Providerstream abonnieren und Hinweise begrenzt puffern; vollständigen Snapshot einlesen; anschließend Changes ab snapshot_watermark bis high_watermark holen, dann atomar sichtbaren State wechseln. Während Catch-up neue Hinweise merken und weiter abgleichen. Nur neuere Revisionen derselben entity_kind/entity_uuid übernehmen; reine Batchpause/Reorder benötigt keine fiktive Jobrevision; laufende UIantworten müssen gleiche view_generation besitzen. Bei Overflow/410/Generationswechsel Hydration verwerfen und neu beginnen; UI bleibt sichtbar stale. Periodischer begrenzter Changeabgleich heilt fehlende SSE auch ohne Reconnect. Jobliste erst bei geschlossenem Catch-upfenster aktuell nennen; bei Dauerlast bounded Budget erreichen → sichtbar synchronizing/degraded, keine falsche Vollständigkeit.

## 9. Liveness, Fristen und Ressourcen

Getrennte Zustände backend_reachable, job_stream_live, comfy_http_reachable, comfy_ws_live, snapshot_current. Funktionierender Log-/GPUstream beweist keinen Jobstream. Monotone Idlewatchdogs, Cancel/Connect/Read/Control/Transfer/Reconciliationfristen, Pollintervall, Backoffobergrenze, max_message_bytes, max_pending_observations und Snapshotbudget im O03-Profil verbindlich festlegen. Keine unendlichen Wiederholungen oder stille numerische Standardwerte. Vor Qualifikation vollständiges Profil erforderlich; jetzt keine ungemessenen Werte als freigegeben behaupten.

Heartbeats prüfen; Comfyprofil ohne Appheartbeat durch begrenzte HTTPprobes überwachen. Nach Ablauf stale/degraded, Socket kontrolliert neu verbinden und HTTPabgleich; unbekannte Nutzung ist nicht frei und Stillstand nicht Fehlererfolg. Getrennte kleine Controlrequests bleiben auch bei Mediendownload reaktionsfähig; begrenzte Parallelität. Netzwerk-/Transferwarten nicht unter SQLite-/Recovery-/GPUlocks. Beobachtungsbudget erschöpft → durable needs_decision/repair_pending passend zur Phase, kein Watchdog-Retry von /prompt.

## 10. PB-Schließen und Wiederstart

Geplante Route POST /jobs/lifecycle/prepare-close, request client_request_id/expected_backend_instance; requestbezogener idempotenter CloseIntent. Backend sperrt neue Dispatches, klassifiziert bereits mögliche Sends und lokale Import-/Vektorcommits, speichert alle Übergaben und bounded Quiesce. Antwort CloseReceipt mit close_intent_uuid, backend_instance_uuid, store_generation_uuid, dispatch_frozen, durable_handoff, unresolved_attempt_ids und local_repair_required. Kein Remoteende abwarten. Server kontrolliert auch bei HTTPverlust weiter bis durable Ergebnis; Geplante GETroute /jobs/lifecycle/close-intents/{id} fragt dasselbe Receipt ab. POST /jobs/lifecycle/close-intents/{id}/abort mit client_request_id/expected_revision hebt ausschließlich den eigenen Closefreeze nach durable Reconciliation per CAS auf; closed/überholte Instanz409, kein heimliches Resume. Batchpausen und andere Admissiongrenzen bleiben erhalten. CloseIntentstatus prepared/aborted/closed plus Revision persistieren, gleiche Mutation idempotent. Bei Backendneustart alten CloseIntent historisch abgleichen; neue Session nimmt Arbeit erst nach abgeschlossener Reconciliation und gemäß gespeicherter gewünschter Pause-/Resumepolicy auf.

WPF fängt den regulären Fensterabschluss in MainWindow.Closing/OnClosing vor dem tatsächlichen Schließen ab, setzt e.Cancel und führt den Handshake asynchron mit Reentrancyguard durch. Erst erfolgreiches Receipt erlaubt erneutes endgültiges Close ohne Schleife und anschließend BeginShutdown/Backendstop; OnExit ist für einen abbrechbaren Dialog zu spät. Nur bestätigter durable_handoff erlaubt regulär nachfolgendes StopAsync. Bei Timeout/Persistenzfehler Schließen als unvollständig anzeigen; kein erzwungener Prozessbaumkill als erfolgreiche Übergabe ausgeben. Expliziter harter Abbruch/Crash bleibt eigener Fehlerpfad; Korrektheit stützt sich auf Write-ahead vor jedem Send/Commit, nicht auf garantiertes OnExit. Separates Comfy niemals unter PB-Killbaum starten/stoppen. Zombie-Watcher berücksichtigt kurzfristige lokale Jobcommits/Quiesce, Remotejob allein verlangt keinen unbegrenzten PB-Dauerbetrieb. Wiederstart liest Freeze-/Attempt-/Importreceipts und reconciliiert vor neuem Dispatch.

## 11. Verpflichtende Abnahmematrix — noch nicht ausgeführt

Jeder Fall muss nach Implementierung über echte Adapter/Parser und die angegebenen Fehlerfenster geprüft werden. Protokollfixtures/Fault-Injection dürfen Nachrichten simulieren; sie beweisen keine Medienqualität. Danach reales autorisiertes lokales Comfyprofil und sichtbarer WPF-Flow getrennt abnehmen.

| Test | Störung | Erwartetes Ergebnis | Owner |
|---|---|---|---|
| W01 | PB commit,202 verloren,WPF-Neustart | gleicher Intent; genau ein Job | T011,T022,T024 |
| W02 | Doppelklick; gleicher Key anderer Payload | ein Job beziehungsweise409 | T022,T024 |
| W03 | reale statische/dynamische Routen;409/422/503/kaputtes JSON/Timeout/Cancel parallel | requestbezogene unterscheidbare Outcomes | T022,T025 |
| W04 | fremde/missing ID, Enum unbekannt, null, int64-Rand | Reject/incompatible, keine Fake-Defaults | T010,T022,T025 |
| W05 | Terminal während Snapshotseite, neue Jobs, Reorder | konsistente Sicht plus Catch-up | T011,T022,T025 |
| W06 | Projektwechsel bei verspätetem altem Snapshot | alte view_generation verworfen | T025 |
| W07 | Backendrestart/Uhr zurück/Restore/Journalauslauf | Generation/reset/snapshot, kein alter Cursorclaim | T021,T022,T025 |
| W08 | mehr Events als Puffer; gefilterte Seq-Lücken | Resync; keine falsche Lückenerkennung | T022,T025 |
| W09 | Sampling100,missing Progress, Legacyfilter | laufend/unbekannt, eigene DTOs Ende zu Ende | T022,T025 |
| W10 | SSE half-open, Logstream lebt | job_stream stale; HTTP heilt Zustand | T025 |
| W11 | WS binär/fremde prompt_id/reconnect ohne prompt_id | keine fremde Attempttransition | T003,T013 |
| W12 | alter SID-Handler endet beim Reconnect | Kanalverlust erkannt; HTTPreconcile wirksam | T003,T013 |
| W13 | Prompt-ACK verloren | bekannte vorher persistierte Prompt-ID abgleichen; kein zweiter Send | T011,T012,T013 |
| W14 | Transportretry/Proxytimeout/Leaseexpiry | kein impliziter zweiter /prompt | T003,T012 |
| W15 | uppercase/falsche Promptuuid | vor Send abweisen | T003,T012 |
| W16 | WSsuccess/error vor ACK; spätes queued/running | monotone bestätigte Reduktion | T010,T012,T013 |
| W17 | success, mehrfach History{}, dann Output | result_evidence_pending, ein Import, kein Resubmit | T013,T019 |
| W18 | completed ohne Rohstatus/null/unknown | unknown/needs_decision statt success | T005,T013 |
| W19 | Erfolg dauerhaft ohne Pflichtoutput | keine Readyfreigabe; sichtbar ungeklärt | T013,T019 |
| W20 | Pendingcancel200true, Queue/History leer | Logicalcancel, Remoteoutcome ungeklärt bounded | T010,T014 |
| W21 | Pending→Running-Cancelrennen200true | Remoteende nicht behauptet | T014 |
| W22 | Cancel200false/fremde ID/Terminalrace | kein globaler Fallback, Job bleibt cancelled | T014 |
| W23 | gleicher Endpoint neu gestartet/History gelöscht | Bootidentity unknown, kein Resubmit | T004,T013 |
| W24 | Namenskollision/Unicode/subfolder | tatsächliches UploadReceipt an Loader | T017 |
| W25 | Previewparameter/404/Teiltransfer/anderer Hash | keine kanonische Veröffentlichung | T017,T019 |
| W26 | PBclose vor Send/nach Send vor ACK/im Commit | durable Handoff oder ehrlicher unvollständiger Close | T021,T022,T025 |
| W27 | harter WPF-/Backendcrash ohne OnExit | Write-ahead-Recovery, kein Doppelauftrag | T021,T026 |
| W28 | Comfy beendet Shot bei geschlossenem PB | später receipts/QC/import; keine Fremdprojektzuordnung | T013,T021,T026 |
| W29 | lokaler Persistenzfehler/CloseACK verloren | kein falscher durable_handoff; selber CloseIntent | T021,T022,T025 |
| W30 | echte Generate→Progress→Import→Reopen-Kette | sichtbarer tatsächlicher Flow mit Source/Outputreceipts | T026,T045 |
| W31 | reine Batchpause/Reorder ohne Jobrevision; SSE verloren | vollständige Batchprojektion nach Catch-up korrekt | T011,T022,T025 |
| W32 | CloseACK verloren, Close zurückgenommen, erneutes Close/Restart | Receipt abfragbar, nur eigener Freeze gelöst, Batchpause erhalten | T021,T022,T025 |

Gwire: W01–W29 sowie W31–W32 müssen für gewählten Profil-/UIstand mit tatsächlichen Produktadaptern bestanden sein; W30 und Medienabnahme zusätzlich. Failures blockieren betroffene Lieferung. Tests nennen Software-/Profilhashes, Fehlerfenster, erwartete/erhaltene Zustände und verbleibende Unsicherheit. Dokumentchecks, synthetische Modelle, grüne Builds oder offene Ports gelten nicht als Gwire-PASS.

## 12. Quellen

Lokale Belege mit exakten Zeilen: communication-audit-2026-10-13/findings.json; unveränderte Baseline und Quellhashes daneben. Aktuelle Anforderungen hier sind Entwurf, tatsächliche Comfy-Felder oben profilgebunden.

- [Comfy Server Routes](https://docs.comfy.org/development/comfyui-server/comms_routes): Submit/Queue/History und getrennte Transportaufgaben.
- [Comfy Server Messages](https://docs.comfy.org/development/comfyui-server/comms_messages): executed ist Knotenausgabe; Fortschritt und Ausführungsabschluss unterscheiden.
- [HTTP Semantik RFC9110 §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2): Nicht-idempotente Requests benötigen gesonderte Begründung für automatische Wiederholung.
- [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html): Last-Event-ID ist Transportmechanik; die geplante dauerhafte Jobreparatur benötigt eigenen Vertrag.
