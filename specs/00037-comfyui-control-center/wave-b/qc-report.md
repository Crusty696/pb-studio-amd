# Welle B — QC-Nachweis

Stand 2026-10-13. PASS für Bibliotheks-/Vertragsscope T005/T006 und zugehörigen T045-Anteil. Kein Gesamtprodukt-, Sicherheits-Sandbox-, Medien- oder GUI-PASS.

## Ergebnis

T005: unveränderliche JSON-Workflowrevisionen; an Discovery-Fingerabdrücke gebundene vollständige Nodeschemata; typsichere Parameter und Form-/Framegrenzen; persistente Aktivierung mit CAS, Revision, Registrygeneration und Idempotenz. Caller-owned JSON-Registry mit atomarem Austausch und Prozesssperre. Keine automatische Produktregistry angelegt. Tatsächliche Uploadreferenzen und erfolgreiche Pflichtoutputs werden anhand vollständiger Endpoint-/Attempt-/Prompt-/Workflowbindung geprüft.

T006: lokale Policyprüfung lehnt bloße Selbstdeklaration, fremde Ziele, unerlaubte Loopbackziele, Credentials und veränderte Ausführungsidentität ab. Auditevidence benötigt separat injizierten vertrauenswürdigen Prüfer. execution_ready bleibt immer false. Backend publish_log und SSELogHandler redigieren Logpayloads vor Veröffentlichung; Original-LogRecord bleibt erhalten.

## Ausgeführte Nachweise

- Finaler Parentlauf: 109 Tests, 47 Subtests, 0 Fehler; tests.xml. Sechs Dateien: Comfy config/connection/capabilities/workflow_bundle/workflow_policy sowie bestehende config_hot_reload.
- 163 Pythondateien aus src/pb_studio, backend und Comfytests ohne Imports kompiliert; source-verification.json.
- Echte Zwei-Prozess-CAS-Gegenprobe ausschließlich auf temporärer Registry: genau ein Gewinner, ein Konflikt. Persistenz-/Reopen-/Idempotenz-/Restoregenerationtests enthalten.
- Unabhängiger Source-Review: keine verbleibenden konkreten Blocker im Scope; independent-review.md.
- RED→GREEN: fehlende Module; beide bisherigen unredigierten SSE-Publikationspfade; Windows-Gerätenamen (vier Gegenfälle); Credential-Logschlüssel; Klartextcredentials und leere Host-Allowlist. Nicht jeder einzelne Test wurde vor seiner Implementierung rot ausgeführt.
- git diff --check ohne Fehler, lediglich CRLF-Normalisierungshinweise.
- Baselinehashes: Produktconfig, DB, Recoverydateien, vorherige Wave-A-Module und fremde UI-/Einstellungsänderungen unverändert. Ausnahmen ausschließlich geplantes backend/dependencies.py und bereits beim Baselinezeitpunkt vorhandener erster Wave-B-Entwurf workflow_schemas.py.

## Isolation und Beweisgrenzen

Vorhandene Pythonumgebung; PYTHONPATH=src, eigener temporärer LOCALAPPDATA, --noconftest mit wave-a/pytest.ini. Keine Installation, Migration, Produkt-Appstarts, Live-ComfyUI-Aufrufe, Generierung oder GPUarbeit. Laufende ComfyUI-Aufträge unberührt.

SSEtests führen die tatsächlich aus backend/dependencies.py extrahierten Funktionen mit Test-Publishern aus. Kein vollständiger Backendimport, keine echte SSE-/WPF-Abnahme. Keine WPFänderung dieser Welle und kein .NET-Build. Registry nur temporär getestet, nicht in Produktstate eingebunden. Prozesskonkurrenz geprüft; Stromausfall-/Dateisystem-Durabilität nicht gemessen.

Unsupported Enum-/dynamische Nodeschemata und literale Listen werden abgewiesen. Nur statischer Adapter comfy.files.v1, kein freier Code aus Metadaten. Kein aktuelles Workflowprofil qualifiziert. Vollständiger externer Registry-Dateirestore muss künftig unter Recoveryfence rotate_generation_after_restore aufrufen; vollständiger Rollback aller Dateien wird nicht automatisch erkannt.

Policyvalidität ersetzt weder echten auditierten Runtimebeleg noch erzwungene Egresssperre. Ein Test-Verifier ist kein realer Audit. Effective-Graphvergleich bindet aktuell die unveränderliche Vorlage; parametrisierte Abweichungen bleiben bis zur späteren Submit-/Auditscope-Integration gesperrt. resolved_prompt_sha256 ist ausschließlich lokaler Vorbereitungshash. Parserreferenzen sind kein Download-, Decode-, Qualitäts- oder Importnachweis. Geheimnisfilter erkennen bekannte strukturierte/markierte Credentialformen, keine beliebigen unbeschrifteten Geheimnisse.

## Verbleibende Gates

T002: autorisierte Referenzmedien, unabhängige Qualitätslabels und Messplan. T007: separat freigegebener, konkret begrenzter lokaler Pilot samt tatsächlicher Audit-/Node-/Modell-/Runtimebindung und Messwerten. Kein Root-.completed/.qc-passed; T045 im Master bleibt offen. Die Marker in diesem Ordner gelten ausschließlich der geprüften Welle B.
