# Bestätigte Architekturentscheidungen

Status: vom Nutzer ausdrücklich bestätigt, 2026-10-12. Ergänzung zum Architekturreview; keine Implementierungs- oder Produktionsfreigabe.

## D01 — Getrennte GPU-Laufzeitregeln

**Nutzerentscheidung:** „ComfyUI-Ausnahme erlauben; PB bleibt DirectML“.

ComfyUI darf als separat installierte externe Ausführungsengine seine eigene AMD-/ROCm-Laufzeit verwenden. PB-Studio-interne ONNX-/GPU-Inferenzpfade bleiben DirectML. Die Ausnahme erlaubt weder Comfy-Pythonimporte noch Comfy-Abhängigkeiten in der PB-Umgebung und erweitert die ROCm-Freigabe nicht auf PB-interne Provider.

Begründung: Der Nutzer erlaubt die externe Runtime ausdrücklich; dadurch ist der im Review erfasste Geltungsbereichskonflikt F05 geklärt. Bestehende GPU-Koordination, Hardware-Smoke, Workflowqualifikation und Medienabnahme bleiben erforderlich. Runtimeerlaubnis ist kein Funktions- oder Qualitätsnachweis.

Keine Runtime, Konfiguration, Abhängigkeit oder bestehende Policydatei wurde dafür geändert. Dieser Entscheidungsrecord dokumentiert die spätere ausdrückliche Nutzeranweisung gegenüber älteren allgemeinen Regeln.

## D02 — Lokal zuerst, Cloud separat freigeben

**Nutzerentscheidung:** „Lokal zuerst; Cloud nur separat freigegeben“.

Erster Generierungsrelease arbeitet lokal. Kostenpflichtige Cloud-/Partner- oder Hybridworkflows dürfen nicht automatisch ausgewählt, als Fallback benutzt oder durch Retries aktiviert werden. Spätere Cloudausführung benötigt separate ausdrückliche Freigabe mit klarer Workflow-/Datentransfer-/Kosten-/Retrygrenze.

Ein lokaler Comfy-Endpoint allein beweist keine lokale Ausführung. Workflows müssen ihren tatsächlichen Ausführungsort und externe Modell-API-Aufrufe deklarieren; unbekannter Ausführungsort qualifiziert nicht für Local-only-Automation. Diese Entscheidung ist keine pauschale Regel zu Updates oder manuell freigegebenen Modelldownloads.

Begründung: Lokaler erster Scope reduziert unfreigegebene Kosten- und Uploadwirkungen. Cloudarchitektur kann später vorbereitet werden, ohne Cloudnutzung bereits zu erlauben.

## Weiterhin offene Designgates

- Shared- oder garantiert kooperativer GPUbetrieb, einschließlich konkurrierender Clients.
- Operative Pause-/Shutdownsemantik laufender Jobs.
- Autorisierte Referenzmedien und messbare Qualitäts-/Abnahmegrenzen.

Job-/Import-/Recoveryverträge und Qualitätsgates bleiben unverändert notwendig. Die beiden Entscheidungen starten keinen Workflow und erlauben keine Migration oder Providerablösung.
