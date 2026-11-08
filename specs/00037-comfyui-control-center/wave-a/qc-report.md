# Welle A — QC-Nachweis

Stand2026-10-13. PASS für freigegebenen Bibliotheks-/Vertragsscope T001/T003/T004 und zugehörige T045-Prüfungen. Kein Gesamtprodukt-/GUI-/GPU-/Workflow-PASS.

## Geändertes Verhalten

ConfigManager ergänzt standardmäßig deaktivierte, strikt validierte Comfy-Verbindungseinstellungen. Lesen löst kein Netzwerk aus. Ungültige comfyui-Setwerte werden vor RAM-/Dateimutation abgelehnt; Speicherfehler stellen den vorherigen RAMstand wieder her. Produktive config.json wurde nicht verändert.

ComfyClient liefert typisierte, unveränderliche, an den angefragten Endpoint gebundene Discovery-Snapshots. Explizite Diagnose auch disabled erlaubt; keine Hintergrundverbindung. Feste GET-Allowlist, Loopback, keine Redirects/Umgebungsproxies/automatischen Retries, finite Kontrollfristen und Byte-/JSONgrenzen. Unbekannte Modell-/Nodepaket-/Laufzeit-/Bootidentität bleibt unknown. Sourceprofil ist Kandidat, execution_ready immer false. Modellrollen tragen eigene Verfügbarkeit. Lokale WS-Owner-/Frame-/SIDverträge vorhanden, keine echte Socketverbindung.

## Ausgeführt

- Parent: 53 pytest-Tests und20Subtests bestanden, Exit0. Vier Dateien: test_comfyui_config, test_comfyui_connection, test_comfyui_capabilities, bestehende test_config_hot_reload. Beleg tests.xml.
- Config RED:13fehlende-Funktions-/Validierungsfälle; zusätzlicher invalid_set-Test scheiterte vor Guard. Worker RED: beide Testdateien scheiterten vor Modulimplementierung. Initial24Client-/Capabilitytests grün; Reviewkorrekturen auf31Tests erweitert.
- Syntaxprüfung:155Pythondateien aus src/pb_studio, backend und neuen Testdateien ohne Imports kompiliert,0Fehler. source-verification.json.
- Reale Adapterprobe: genau GET http://127.0.0.1:8188/system_stats, ComfyVersion0.39.2, discovered, execution_ready=false. inventory=False; keine /object_info-/Queue-/History-/WS-/Mutationsaufrufe. live-discovery.json.
- Unabhängiger Quellreview nach Korrekturen: keine verbleibenden Blocker. independent-review.md.
- git diff --check ohne Fehler (nur Git-Hinweis zur künftigen Zeilenendennormalisierung).
- Geschützte config.json, DB/Recoverydateien und bestehende UI-/lokale Einstellungsänderungen identisch zum Vorherhash. Von254alten inventarisierten Quellen ausschließlich geplantes config_manager.py geändert.

## Testisolation und Nichtausführung

Python3.11.9, vorhandenes httpx0.28.1/pydantic2.13.4. --noconftest + eigene pytest.ini verhindert globalen GPU-/Backend-Autouse. Eigener temporärer LOCALAPPDATA und isolierte Testkonfigurationen. Keine Installation, kein produktiver Backend-/WPFstart, kein Build/Deployment nötig für diese noch nicht automatisch integrierte Pythonbibliothek; keine .NET-Datei aus dieser Welle geändert. Keine GPUinitialisierung/-ausführung durch diese Tests, keine Generierung, Migration oder Medienmutation. Fremde ComfyUI-Aufträge nicht angefasst.

## Beweisgrenzen und nächste Gates

Vollständiges echtes Node-/Modellinventar nicht abgefragt, weil /object_info serverintern Assetscan auslösen kann. Vollständiger Discoveryvertrag mit Testtransport geprüft; tatsächliche Probe nur system_stats. Kein qualifiziertes Workflowprofil, kein G1. Settings-CAS/aktive Consumerverdrahtung erst T023, Socket-Lifecycle/Reconciliation später; Transferfrist hier nur Vertrag. Keine harte Echtzeit-/Speicherpeak-Garantie. T002 Referenzen/Messwerte und T005ff offen. Kein Root-.completed/.qc-passed. Welle-A-Marker gelten nur diesem engen Teilumfang.
