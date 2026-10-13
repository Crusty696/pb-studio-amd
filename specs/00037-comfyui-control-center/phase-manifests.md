# Phasenmanifest — erster Umsetzungsschritt

Status: WELLE A FREIGEGEBEN, 2026-10-13. Nutzer genehmigt T001/T003/T004 mit zugehörigen T045-Prüfungen. Keine Generierung, GPU-Läufe, Migrationen oder Installationen. T001/T003/T004 abgeschlossen; T045 ausschließlich für Welle A geprüft, Gesamtpaket bleibt offen. Nachweise: wave-a/qc-report.md. Ergänzung zum unveränderten geprüften Masterplan.

## Welle A: lesende Verbindung und Fähigkeitserkennung

Pflichtumfang: T001 (Startscope/Quellbindung), T003 → T004; T045 ausschließlich Dokumentation und Nachweise dieser Welle. T002 wird separat vorbereitet; dessen offene Medien-/Messgates blockieren T007, nicht automatisch T003/T004. T001-Scope ist ausdrücklich freigegeben. Kein Gesamtabschluss T002 oder T045 aus dieser Teilwelle.

Ziel: Richtigen ComfyUI-Endpunkt identifizieren, verfügbare Nodes/Modelle und unbekannte Identitäten ehrlich anzeigen bzw. liefern, Offline/Timeout handhaben. Keine Generierung und kein Import.

Vorgesehene Dateien laut Paketvertrag:
- T003 Modify: src/pb_studio/config_manager.py. Create: src/pb_studio/comfyui/client.py, schemas.py; Tests/test_comfyui_connection.py.
- T004 Create: src/pb_studio/comfyui/capabilities.py; Tests/test_comfyui_capabilities.py.
- T001/T045: zugehörige Plan-/Vertrags-/Nachweisdokumente. Vorhandene clarifications.md erhalten, nicht neu überschreiben.

## Voraussetzungen und Grenzen

Explizite Freigabe dieser Welle liegt vor. Vor Beginn aktuelle Hash-/Dirtyprüfung wiederholen und echte Importgrenzen/Dependencybestand lesen. Tests ausschließlich in nachgewiesen isolierten Daten-/Config-/LOCALAPPDATA-Wurzeln; produktiven Backendstart vermeiden. Testtransporte dürfen Netzwerkfehler simulieren, aber keine Medien-/Hardwareabnahme ersetzen. Bestehende Dependencies nutzen; erforderliche neue Pakete separat konkret vorlegen. Kein IApiClient-/Produktdatenbank-/Migrations-/WPF-Eingriff. Produktive Konfiguration unverändert lassen; config_manager-Codeänderung nur mit isolierten Testkonfigurationen prüfen. Keine ComfyUI-Paket-/Modellupdates, Downloads, Queueänderung, /prompt, /interrupt, /free oder GPUausführung.

Read-only-Proben nur an eindeutig gebundener Instanz, begrenzt und ohne rohe fremde Jobdaten zu speichern. Historisch/lokal passende Version ist kein vollständiger Nachweis aller geladenen Custom-Node-Dateien. Aktuelle laufende ComfyUI-Arbeit unberührt lassen.

## Abnahme dieser Welle

Gezielte isolierte Vertragstests: falscher Dienst, Timeout/Offline ohne blockierenden Aufrufer; zwei Endpunkte nicht vermischt; fehlende/defekte/unknown Komponenten nicht ready; Name allein keine Modellidentität; kein mutierender Discoverycall; keine impliziten POST-Retries. tatsächliche erreichbare Discovery separat belegen. Keine GUI-/Hardware-/Generierungsfreigabe aus diesen Tests. Abschließender Quellreview und phasenbezogener Nachweis; kein globaler Masterplan-Completionmarker.

## Folgewellen — jeweils eigene Freigabegrenzen

B: T005 → T006: Workflowregistry/Parametermapping/Outputvertrag und lokale Policy; erst nach T004. T002 liefert autorisierte Referenzen und Mess-/Qualitätsplan, nicht erfundene Messwerte.
C: T007 erst nach T002+T005+T006 und gesondert autorisiertem, begrenztem Pilotlauf. Workflow, Nodes/Modelle, Ausgabeordner, Laufgrenzen und freie Queue vorher konkret binden. G1 verlangt reales decodierbares Ergebnis und gemessene Ressourcen.
D: Persistenz/GPU-/WPF-Integration erst nach den im Masterplan vorgesehenen G1-/Schema-/API-Gates. Gmigration/Gapi bleiben separat. Unbeaufsichtigter Betrieb und managed Koordination nicht Welle A.

## Welle B — Fortschreibung 2026-10-13

Nutzer „nächser schritt“ nach Welle A als Fortsetzung der dokumentierten Folge T005 → T006 innerhalb unveränderter Betriebsgrenzen umgesetzt. T005/T006 Bibliotheks-/Vertragsscope abgeschlossen, zugehöriger T045-Anteil geprüft: wave-b/qc-report.md, 109 Tests +47 Subtests. Keine Live-ComfyUI-Abfrage dieser Welle. Keine Produktregistry eingerichtet. Raw-Nodeschema-/JSONvertrag in workflow_schemas.py und pure Redaction in log_redaction.py als explizite Teilmodule; siehe wave-b/plan.md.

T002 und reale T007-Qualifikation offen. G1, echte Audit-/Egressbelege, Submit-/Auditscope-Bindung parametrisierter Effective-Graphs und Produktverdrahtung bleiben spätere Gates. Globale T045-/Completionmarker unberührt.

## T002-Vorbereitung — 2026-10-13

Nutzer beauftragt Referenz-/Messvorbereitung ohne Generierung/GPUläufe und benennt feste Audio-/Videowurzeln. benchmark-spec.md und reference-manifest.json angelegt: nur Verzeichniseinträge geprüft, keine Medienmessungen/Labels/Einzelhashes. T002 bleibt offen. Quellenpfade dauerhaft erinnert. Gesonderte Nativebaseline-/T007-Gates bleiben bestehen.

## T002-CPU-Funktionsprüfung — 2026-10-13

Nach dem obigen Vorbereitungsstand wurden neun ausgewählte Regressionstestmedien mit isoliert ausgeführten PB-Studio-Funktionskörpern geprüft: 6/6 Videos mit Metadaten, je drei Frames und vier Vorschaubilder; 3/3 Audios mit Metadaten und je einem 30-Sekunden-Ausschnitt. Software-Videoöffnung ohne Hardwarebeschleunigung geprüft; alle neun Original-SHA-256 nach dem Lauf unverändert. A03 M4A nutzte den Librosa/audioread-Fallback mit Deprecation-Warnung. Beleg: [t002-cpu-check-2026-10-13/cpu-check-report.md](t002-cpu-check-2026-10-13/cpu-check-report.md). Das ist keine vollständige App-/API- oder Qualitätsabnahme. T002, unabhängiger Holdout und Nativebaseline bleiben offen.
