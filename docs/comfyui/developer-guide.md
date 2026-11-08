# Developer Guide — Welle A

Keine Installation nötig: vorhandenes .venv verwenden. Tests ohne globales Tests/conftest.py durchführen, dessen Autousefixtures Hardware-/Backendbereiche berühren. PYTHONPATH=src und eigener temporärer LOCALAPPDATA-Pfad vor Prozessstart; nur konkrete Testdateien wählen.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$env:LOCALAPPDATA = Join-Path $env:TEMP ('pb-wave-a-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $env:LOCALAPPDATA | Out-Null
./.venv/Scripts/python.exe -m pytest --noconftest -c specs/00037-comfyui-control-center/wave-a/pytest.ini Tests/test_comfyui_config.py Tests/test_comfyui_connection.py Tests/test_comfyui_capabilities.py Tests/test_config_hot_reload.py -q
```

Kein produktiver Backendimport, kein GPUlauf. Testtransporte modellieren Kommunikationsfehler, keine erfundenen Medien. Reale Verbindungsproben separat als solche erfassen; nur kontrollierte lesende Route. Limits sind konfigurierbare Schutzwerte, keine gemessenen Medienbudgets. Normale Produkt-Konfigurationsdatei während Prüfungen unangetastet lassen.

T045 gilt phasenweise. Installation-/Providersystemdokumente werden erst bei den dafür verantwortlichen Paketen T023/T038 fällig; diese Welle liefert Architektur, Workflowgrenze, Troubleshooting und Entwicklungsanleitung. Keine Abnahme späterer Pakete behaupten.

Explizites `inspect()` ist eine bewusst aufgerufene Diagnose und auch bei enabled=False erlaubt. enabled ist für spätere automatische Hostintegration reserviert; diese Welle implementiert keinerlei automatische Verbindung. `inventory=False` ruft nur /system_stats auf. max_response_bytes begrenzt sowohl einzelne Antworten als auch das aggregierte Antwortbudget eines inspect; Kontrollfrist begrenzt Netzwerkwartezeiten, keine harte CPUpräemption.

## Welle B: Offline-Verträge

Zur obigen Testauswahl zusätzlich Tests/test_comfyui_workflow_bundle.py und Tests/test_comfyui_workflow_policy.py angeben. Finaler Nachweis: specs/00037-comfyui-control-center/wave-b/qc-report.md.

WorkflowBundle(JSON-Daten) validiert unveränderliche Revisionen. WorkflowRegistry(path, discovery_snapshot) verlangt expliziten Pfad in vorhandenem caller-owned Verzeichnis; Konstruktion kann dort einen neuen JSONstore samt Lockdatei anlegen. Niemals ungefragt Produktpfade verwenden. register/get/validate und set_enabled verwenden persistente Identitäten; CAS braucht aktuellen activation_token und client_request_id. authorize_dispatch pinnt nur lokale Berechtigung, sendet nichts und ersetzt keine Policy-/G1-/Schedulerprüfung.

resolve_parameters erzeugt Kopien und resolved_prompt_sha256. Dieser Hash ist kein Beleg einer tatsächlich ausgeführten Graphfassung. check_workflow_policy braucht für höheres Vertrauen eine separat injizierte vertrauenswürdige Evidenceprüfung; niemals Verifier aus Manifest übernehmen. execution_ready bleibt false. Parametrisierte Graphen bleiben bei Abweichung von der Vorlage gesperrt, bis der spätere Submit-/Auditscope die aufgelöste Identität bindet.

parse_outputs verlangt observer-bound Endpoint/Attemptdaten und expected_* aus künftig persistiertem Submissionkontext. Erwartete Werte niemals aus der Remoteantwort kopieren. Parser liefert Dateireferenzen, keine fertigen Medien. Registry-Restore künftig unter exklusiver Recoveryfence mit rotate_generation_after_restore; vollständiger externer Rollback aller Dateien ist lokal nicht automatisch erkennbar.
