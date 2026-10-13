# Bestätigte Architekturentscheidungen

Status: vom Nutzer ausdrücklich bestätigt, 2026-10-13 (D01 bestätigt2026-10-12). Ergänzung zum Architekturreview; keine Implementierungs- oder Produktionsfreigabe.

## D01 — Getrennte GPU-Laufzeitregeln

**Nutzerentscheidung:** „ComfyUI-Ausnahme erlauben; PB bleibt DirectML“.

ComfyUI darf als separat installierte externe Ausführungsengine seine eigene AMD-/ROCm-Laufzeit verwenden. PB-Studio-interne ONNX-/GPU-Inferenzpfade bleiben DirectML. Die Ausnahme erlaubt weder Comfy-Pythonimporte noch Comfy-Abhängigkeiten in der PB-Umgebung und erweitert die ROCm-Freigabe nicht auf PB-interne Provider.

Begründung: Der Nutzer erlaubt die externe Runtime ausdrücklich; dadurch ist der im Review erfasste Geltungsbereichskonflikt F05 geklärt. Bestehende GPU-Koordination, Hardware-Smoke, Workflowqualifikation und Medienabnahme bleiben erforderlich. Runtimeerlaubnis ist kein Funktions- oder Qualitätsnachweis.

Keine Runtime, Konfiguration, Abhängigkeit oder bestehende Policydatei wurde dafür geändert. Dieser Entscheidungsrecord dokumentiert die spätere ausdrückliche Nutzeranweisung gegenüber älteren allgemeinen Regeln.

## D02 und O01–O04 — Fortschreibung2026-10-13

Nutzer bestätigt O01–O04-Empfehlungen; konkrete Messwerte und Migrationsfreigaben bleiben offen. Cloud ausdrücklich aus PB-Umbau gestrichen; separat in ComfyUI einstellen. Frühere spätere Dienstefreigabe ist ersetzt; kein PB-Ausbau-/Folgegate.

Verbindlicher Detailrecord: [clarifications.md](../../specs/00037-comfyui-control-center/clarifications.md).

- O01: observed_shared zuerst; später managed vor zuverlässig unbeaufsichtigter Produktion, nur für tatsächlich kooperierende Clients. Technische Installation/Qualifikation gesondert.
- O02: neue Dispatches pausieren, laufender Shot endet; PB-Schließen speichert/detacht separate ComfyUI, Neustart reconcile ohne blindes Resubmit. Cancel/obsolete Outputs gesichert, nicht automatisch verwendet; katalogisierte Medien behalten, Verwendung sperren, konsistent abschließen.
- O03: reale autorisierte Referenzen, Native-Baseline, unangetasteter Holdout; konkretes Inventar, Autorisierung, Messwerte/Abnahmegrenzen offen.
- O04: additive Erweiterung im bestehenden Katalog/API, kein zweiter Medienkatalog; konkrete SQL/API-/Migrationsfreigaben offen.

Keine Produktimplementierung, Migration, Installation, Ausführung oder Providerablösung freigegeben.
