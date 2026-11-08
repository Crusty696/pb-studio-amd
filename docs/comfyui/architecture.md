# ComfyUI-Bridge: Architektur, Welle A

Stand: nur T003/T004 werden geliefert; keine produktive Startup-/WPF-/Jobverdrahtung. PB besitzt später Projekte/Medien/Jobs; ComfyUI bleibt separater Prozess mit eigener Umgebung. Kein Import von ComfyUI in PB, keine Paketinstallation.

ConfigManager → validierte ComfyConnectionSettings → explizit aufgerufener async ComfyClient → typisierter DiscoverySnapshot. Kein Netzwerk beim Konfigurationslesen oder PBimport. Default disabled. Aktuelle API ist eine Bibliothek für folgende Pakete; neue RESTrouten/Views erst T022ff.

Endpointbindung enthält lokale kanonische URL, stabile Endpoint-ID und Discoverygeneration; Generation ist kein Beleg eines Serverneustarts. Unbekannte Laufzeit-/Modell-/Bootidentität bleibt unbekannt. Node-Schemafingerprint ist kein Code-/Paketfingerprint. Reine Discovery qualifiziert keine ausführbaren Workflows.

Sicherheitsgrenzen: feste GET-Routen, keine Redirects/Umgebungsproxies, endliche Zeit-/Antwortgrenzen, keine Submits/Cancel/Free-Aufrufe. Lesendes /object_info kann serverintern Assetscan anstoßen; tatsächlicher Minimalnachweis bei laufender Arbeit deshalb ausschließlich /system_stats. Eigener lokaler WS-Ownervertrag, aber kein LiveSocket im Discoverypfad.

Spätere Wire-/Job-/Import-/GPU-/Recoveryarchitektur: specs/00037-comfyui-control-center/plan.md und communication-contract.md. Diese späteren Funktionen sind hier nicht als implementiert ausgewiesen.

`models` enthält ausschließlich die beobachtete Teilmenge. `models=()` allein beweist bei vorhandenen unerreichbaren `model_roles` keine vollständige Abwesenheit. Pro Rolle unterscheidet `state=observed` mit leeren names von `state=unavailable` mit names=None. Das gelieferte Profil ist ausdrücklich source_candidate, keine Laufzeitattestierung.

## Welle B

WorkflowRegistry speichert explizit gewählte JSONdateien, unabhängig von Produkt-SQLite. Unveränderliche Bundles, mutable Aktivierungsreceipts, Generation und CAS sind getrennt. Keine Produkt-/Startup-/UIverdrahtung. Workflowpolicy ist Offlineprüfung, keine Egresssandbox. Backendlog-Publisher redigieren Payloads vor SSE-Veröffentlichung; Live-SSE-/WPF-Abnahme ausstehend. Umfang, Belege und Restoregrenzen: ../../specs/00037-comfyui-control-center/wave-b/qc-report.md.
