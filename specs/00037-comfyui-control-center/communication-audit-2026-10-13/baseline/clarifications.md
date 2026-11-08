# Bestätigte Entscheidungen und offene Detailgates

Stand: 2026-10-13. Nutzer bestätigt Empfehlungen zu O01–O04. Nur Dokumentfortschreibung; keine Implementierung, Workflowausführung oder Migration freigegeben.

## O01 — GPU-Koordination: Grundentscheidung bestätigt

Erster Scope observed_shared: eigene Dispatches begrenzen, Queue/Auslastung beobachten, bei erkennbaren Konflikten warten und Grenzen sichtbar anzeigen. Keine harte Exklusivitätsgarantie gegenüber unabhängigen Clients. ComfyUI bleibt separat bedienbar. Für später verlässlich unbeaufsichtigte Produktion verbindliche managed Koordination vorsehen; Garantie nur für tatsächlich kooperierenden Scope. Konkrete Gateinstallation, vollständige Clientintegration und technische Qualifikation separat; keine versteckte Voraussetzung für ersten manuellen MVP.

## O02 — Pause, PB-Schließen und Abbruch: Betriebsregel bestätigt

Pause stoppt neue Dispatches; laufender Shot darf fertig werden. Fortsetzen startet nächste offene Arbeit. PB-Schließen sichert Auftragszustand dauerhaft; separat laufende ComfyUI darf begonnenen Auftrag beenden. Neustart gleicht belegte Ergebnisse und ungeklärte Attempts ab; kein blindes Resubmit. ComfyUI-Beenden oder Rechner-Shutdown garantiert keine exakte Fortsetzung mitten im Workflow.

Cancel/obsolete bleibt terminal. Späte Outputs gesichert/quarantänisiert erhalten, keine automatische produktive Verwendung oder Timelineübernahme. Bewusster späterer Import ist neuer Intent. Bereits katalogisierte Medien bleiben erhalten; Verwendung sperren, lokale Schreibvorgänge konsistent drainen/reparieren. Keine automatische Löschung oder Statusumschreibung. Tatsächliche Own-Cancel-Fähigkeit und Recovery später testen.

## O03 — Qualität und Referenzen: Vorgehen bestätigt, Details offen

Repräsentative ausdrücklich autorisierte reale Medien, unveränderte Originale, Native-Baseline und getrennten unangetasteten Holdout verwenden. Verwandte Varianten nicht über Splitgrenzen verteilen. Entwicklungsmedien erlauben Tuning; Holdout dient abschließender Prüfung. Fach-/visuelle Qualität und technische Integrität getrennt beurteilen. Erst Basismessung, dann profilbezogene Grenzwerte vor Qualifikation; keine erfundenen Zahlen.

OFFEN: konkretes Medieninventar/Autorisierung, Referenzlabels, Qualitätsgrenzen, Zeit-/RAM-/VRAM-/Disk-/Retry-/Drainwerte. Owner: Nutzer für Medienfreigabe/Qualitätsziel, jeweiliger Fachverantwortlicher für Messprotokoll; T002/T007/T018 vor abhängigen Abnahmen. Bestätigung ist keine bereits erfolgte Medienfreigabe oder Messung.

## O04 — Katalog/API: Richtung bestätigt, Änderungsfreigaben offen

Bestehenden PB-Katalog/API additiv erweitern; Nativefunktionen und vorhandene Medien erhalten. Kein paralleler Comfy-Medienkatalog. Konkrete Tabellen/DTOs/Routes/ReaderWriter-Verträge in Schema/API-Spec ausarbeiten; Auswirkungen alter Projekte verständlich dokumentieren. Migration auf isolierter Kopie, Compatibility-/Recovery-/Rollbacknachweise vor Produktionsfreigabe.

OFFEN: konkrete DDL/Schema/API-Spec, explizite Migrations- und betroffene API-Kontraktfreigaben sowie technische Nachweise. Owner: Architekturverantwortlicher legt Änderungspaket vor, Nutzer genehmigt konkrete Auswirkungen; T011/T022 und Gmigration/Gapi. Bestätigte Richtung ist keine pauschale Migrations-/API-Freigabe.

## Scopeentscheidung D02 — PB lokal; separate ComfyUI-Konfiguration

Cloud gehört nicht zum PB-Umbau. Einstellungen dafür ausschließlich separat in ComfyUI. Keine PB-Cloudsettings, Cloudprovider-/Kosten-/Credentialsteuerung, Cloudausbaupakete oder Cloudfreigabegates. Früheres O05 entfällt aus dem aktiven Plan. Separat konfigurierte ComfyUI-Funktionen erhalten dadurch keine automatische PB-Qualifikation; die PB-Bridge qualifiziert lokale Profile und behält allgemeine Workflow-/Netzwerk-/Dateisicherheitsprüfungen. D01 bleibt: externe ComfyUI AMD/ROCm erlaubt, PB intern DirectML.

## Gültigkeit und Nachweis

Originalauftrag, Auditquellen und unveränderte countercheck-baseline sind historische Belege, keine aktuelle Entscheidungsliste. decision-revision-baseline-2026-10-13 bewahrt Stand vor dieser Änderung. Alle 45 Produktpakete offen; keine .completed/.qc-passed. Messwerte und konkrete Änderungsfreigaben dürfen nicht aus der Grundsatzbestätigung abgeleitet werden.
