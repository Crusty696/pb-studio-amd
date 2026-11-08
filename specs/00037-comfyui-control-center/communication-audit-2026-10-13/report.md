# Consulting Team Review — Kommunikation PB ↔ ComfyUI

> Auftrag: Kommunikationsplan anhand gelesener PB-/Comfyquellen, offizieller Protokolldokumentation und unabhängiger Gegenprüfung präzisieren.
> Reversibilität: Dokumentänderungen reversibel; künftige DB/APIänderungen separat freizugeben.

## Executive Summary

GO mit dokumentierten Präzisierungen für den Plan; keine Produktfreigabe. Vierzehn Kommunikationsverträge konkretisiert und32 künftige Abnahmefälle definiert. Drei unabhängige read-only Agenten prüften Comfy, PB und einen ausschließlich artefaktbasierten Gegenentwurf. Nach erneuter Prüfung fünf konkrete Fehler im neuen Vertragsentwurf korrigiert: genaue Q2-Enums, Upload-/Outputnamensunterschied, Closing vor OnExit, Batchidentität und Closefreezeauflösung. Confidence HIGH für die zitierten statischen Quellbefunde; Laufzeitfunktion UNVERIFIZIERT.

## Beweisniveau

[ABSICHT] communication-contract.md, aktualisierte Tasks und Gwire beschreiben erst zu implementierende Verträge. [BEOBACHTUNG] Quellstand und konkrete Kontrollflüsse gelesen; Comfy HEAD3c1b7a17fdf239d35ce98cc777756f572d089795. Keine erfolgreiche heutige HTTPantwort an den sechs lesend geprüften Routen: alle Verbindungen zu vorgesehenen Loopbackports8188/8765 verweigert, WinError10061. Das belegt Nichterreichbarkeit dieser Endpoints zum Messzeitpunkt, nicht generell Abwesenheit aller Installationen/Prozesse. [NACHWEIS] Dokument-/Zuordnungs-/Hashprüfung separat in verification.json; keine Produkt-, WebSocket-, Workflow-, Shutdown-, GUI-, GPU- oder Medienabnahme ausgeführt. Produktdaten unverändert. Zusätzlich zehn isolierte Quellprüfungen ausgeführt: unveränderten UUIDvalidator und exakten Statusauswahlzweig per AST entnommen, keine Appimports. Ergebnis in isolated-source-checks.json; reproduziert bestehendes Verhalten, keine End-to-End-Abnahme. Missing/unknown Status ergab tatsächlich completed im isolierten Zweig.

## Fachperspektiven

| Rolle | Falsifizierbarer Beitrag / Beleg |
|---|---|
| Engagement Manager | Kommunikationsgrenzen getrennt prüfen: WPF/PB, PB/Comfy, Ergebnisdateien, Restart. Ein fehlender Owner in Tasks würde CM-Abnahme verhindern; Ownerzuordnung überprüft. |
| Senior Partner | Unabhängige Apps behalten: WPF darf keinen zweiten Comfyclient oder Comfy im PB-Killbaum besitzen. CM05/Closing-Abnahme kann das widerlegen. |
| Analyst | Offizielle Comfy-Dokumentation unterscheidet executed-Knotenausgabe und execution_success; GET-Probes aktuell erfolglos. Kein tatsächlicher Laufbeleg aus Dokumentation. |
| Domain Expert | Comfy Cancelbool mehrdeutig; normalisiertes completed ohne Rohstatus möglich; Python/C#-Enumkonverter nicht automatisch vorhanden. CM06/07/09 Quellen und Wirefixtures. |
| Risk Officer | Drei Fehlerfenster:202 verloren, Snapshot/SSE-Lücke, Close vor Flush. W01/W05/W26 testen genau diese Übergänge statt allein Happy-path. |
| Devil’s Advocate | Unabhängig vier Restlücken: Snapshot/Cursor, dauerhafter WPFintent, frühe WSereignisse, Half-open. Bereits vorhandene Lease-/Unknown-/Hashregeln ausdrücklich nicht als neue Findings gezählt. |
| Synthesizer | Präzisierungen in32 testbare Fälle und bestehende Taskowner überführt. Erst tatsächliches Gwire plus Medienflow rechtfertigt Integrationsfreigabe. |

Skillreferenzen enthalten ältere Stackannahmen; sie wurden nicht als Quellwahrheit übernommen. Hier gilt gelesene WPF/FastAPI-/separate-Comfyarchitektur. Es wurden drei reale Subagenten eingesetzt; sieben Rollen sind Fachperspektiven, keine Behauptung sieben separater Prozesse.

## Findings

Die folgenden Risiken beschreiben unzureichend genaue Planverträge, keine nachgewiesenen eingetretenen Produktschäden. Vollständiger neuer Vertrag: [communication-contract.md](../communication-contract.md). Historische Vorherfassung: baseline/.

### CM01 — HIGH — Verlorene PB-Annahme und dauerhafter WPF-Intent

**Statischer Beleg:** ApiClient.cs:919–931,1002–1034; plan.md baseline:492,563. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Requestbezogenes typisiertes Ergebnis und dauerhaft gespeicherte client_request_id vor Send; identischen Intent nach WPF-Neustart mit identischer ID/Payload abgleichen.

**Owner:** T011, T022, T024, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM02 — HIGH — Lücke zwischen Snapshot, Pagination und SSE

**Statischer Beleg:** backend/dependencies.py:386–392; SSEClient.cs:37–49; plan.md baseline:219,339. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Konsistenter paginierter Snapshot plus dauerhafter Jobänderungscursor; transport id getrennt, Changefeed repariert verlorene Deltas.

**Owner:** T011, T022, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM03 — HIGH — Legacyparser verliert Provideridentität und Statussemantik

**Statischer Beleg:** events_router.py:173–183; SSEClient.cs:341–342,440–451,533–534,576–585,641–667. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Eigener provider_job_changed Parser; nullable Fortschritt, expliziter Jobstatus, keine Legacy100%-Fertiglogik.

**Owner:** T022, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM04 — HIGH — Offener Stream ohne aktuelle Daten

**Statischer Beleg:** SSEClient.cs:102–103,194,302; events_router.py:31,132–134. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Getrennte Streamgesundheit, monotone Idlefristen, begrenzter HTTP-Abgleich und stale/degraded Anzeige.

**Owner:** T003, T013, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM05 — HIGH — PB-Schließen vor dauerhaftem Übergabereceipt

**Statischer Beleg:** App.xaml.cs:221–249; PythonBridgeService.cs:321–333; backend/main.py:369–374. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Kontrollierter Closehandshake vor Backendstop; Crash durch Write-ahead/Reconciliation abfangen, Comfy außerhalb PB-Prozessbaum.

**Owner:** T021, T022, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM06 — MEDIUM — JSON- und Fehlervertrag zwischen Python/C#

**Statischer Beleg:** ApiClient.cs:26–35; plan.md baseline:483–518. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Gemeinsame Wirefixtures, explizite Enumstrings/UUID/UTC/null/Revisionen, requestbezogener ErrorEnvelope.

**Owner:** T010, T022, T024, T025. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM07 — HIGH — Cancelbool beweist kein Remoteende

**Statischer Beleg:** Comfy server.py:952–995; execution.py:1396–1407; comfy_execution/jobs.py:539–548. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** 200 cancelled:true ist nur angenommenes Lösch-/Interruptbegehren; ohne Terminalbeleg bounded needs_decision statt falschem Erfolg oder Pollschleife.

**Owner:** T010, T013, T014. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM08 — HIGH — WS-SID-Rennen und unkorrelierte Nachrichten

**Statischer Beleg:** Comfy server.py:276–293,327–329,1125–1126,1390–1398. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Ein WS-Owner, kein überlappender gleichnamiger Socket; clientId/client_id exakt abbilden, unkorrelierte Events nur Anzeige.

**Owner:** T003, T012, T013. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM09 — HIGH — Normalisiertes completed kann Rohstatus verdecken

**Statischer Beleg:** Comfy comfy_execution/jobs.py:25–31,214–245,261–263; server.py:943–950. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Explizite Remotestatusabbildung; completed ohne belegten success kein autoritativer Erfolg.

**Owner:** T004, T005, T013. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM10 — HIGH — Erfolgsmeldung vor Historypublikation

**Statischer Beleg:** Comfy execution.py:824,831–834,1345–1350; main.py:368–373. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Ausführungserfolg und verfügbare Ergebnisbelege getrennt; bounded Nachabfragen, kein erneuter Submit bei leerer History.

**Owner:** T013, T019. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM11 — HIGH — Prompt-ID vor Send fehlt als expliziter Wirevertrag

**Statischer Beleg:** Comfy server.py:1098–1112; comfy_execution/jobs.py:34–48; execution.py:1307–1311,1345. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Kanonische Prompt-UUID vor Send persistieren und mitsenden; keine Comfy-Deduplizierung voraussetzen, keine automatischen POST-Retries.

**Owner:** T003, T011, T012, T013. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM12 — MEDIUM — Uploadresponse und Downloadparameter nicht deckungsgleich

**Statischer Beleg:** Comfy server.py:400–465,521–563,567ff. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Tatsächliches UploadReceipt verwenden; name zu filename übersetzen; Originaldownload ohne Previewtransformation.

**Owner:** T005, T017. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM13 — MEDIUM — Discovery und WS-SID sind keine Bootidentität

**Statischer Beleg:** Comfy server.py:276–281,727–745; execution.py:1304,1335–1336,1436–1442. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Endpoint-/Discovery-/Connection-/belegte Bootidentität getrennt; unknown ausdrücklich erhalten.

**Owner:** T003, T004, T013. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

### CM14 — HIGH — Remoteereignis vor HTTP-Annahme

**Statischer Beleg:** plan.md baseline:567,596–610; Comfy server.py:1139–1140. PB-Pfade beziehen sich auf das Repository; Comfy-Pfade auf C:/Users/david/ComfyUI-Installs/ComfyUI/ComfyUI. Hashes stehen in source-hashes.json.

**Verbindliche Planpräzisierung:** Beobachtungen puffern und nach Bindungsprüfung monoton reduzieren; keine illegalen Dispatching-Transitions oder Regression durch spätes ACK.

**Owner:** T010, T012, T013. **Abnahme:** zugeordnete W-Fälle in communication-contract.md; aktuell nicht ausgeführt.

## Steel-Man Gegenposition

Zwei unabhängige Programme mit flüchtiger Remotehistorie können nach Antwortverlust und Neustart nicht jeden Ausgang zweifelsfrei rekonstruieren. Mehr Text kann diesen Informationsverlust nicht beseitigen. Der tragfähige Vertrag muss daher manche Fälle ausdrücklich als ungeklärt erhalten, automatische Doppelversendung verhindern und Bedienung trotz ungeklärtem Remoteende ermöglichen. Exakte Garantien werden nur für nachgewiesene Profil-/Versions-/Kooperationsgrenzen abgegeben.

## Offene Nachweise

- O03: tatsächliche Fristen, Grenzen, Referenzmedien und Qualitätswerte vor Profilqualifikation festlegen; keine neuen erfundenen Zahlen.
- O04: konkrete zusätzliche Journal-/DTO-/APIverträge und Migration prüfen/freigeben; Grundentscheidung ist keine Umsetzungserlaubnis.
- Gwire: W01–W29,W31–W32 mit echten Produktadaptern/Fault-Injection und W30 sichtbarer echter Kommunikationsflow; anschließend Medienqualität separat.
- Serverbootidentity bleibt unknown ohne belegten erweiterten Receiptvertrag; unbekannte Ergebnisse werden nicht durch Annahmen ersetzt.

## Recommendation

**GO mit Modifikation auf Planebene.** Änderungen sind im Masterplan und den betroffenen Aufgaben eingearbeitet. Keine100%-Garantie, keine Implementierung und keine Produkt-QC. Freigabe erst für konkret getestete Versionen, Ausfallfälle und Medienprofile. D01/D02/O01–O04 unverändert; Cloud außerhalb PB-Auftrag.

## Primärquellen

- [Offizielle Comfy-Nachrichten](https://docs.comfy.org/development/comfyui-server/comms_messages): executed ist Knotenausgabe; Fortschritt und erfolgreicher Abschluss sind unterschiedliche Ereignisse.
- [Offizielle Comfy-Routen](https://docs.comfy.org/development/comfyui-server/comms_routes): Submit und Statusabfragen getrennt; lokaler gepinnter Source entscheidet die genaue Antwortform.
- [RFC9110 §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2): Nicht-idempotente Requests dürfen nicht ohne Nachweis ihrer sicheren Wiederholbarkeit automatisch erneut gesendet werden.
- [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html): Last-Event-ID hilft beim Transportreconnect, ersetzt keinen dauerhaften fachlichen Zustand.

