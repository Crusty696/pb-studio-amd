# T337 — Models-Recommendation-Wahrheitsvertrag

Status: CONFIRMED

## Symptom

Der Release-Models-Tab und `GET /models/list` bestätigten LM Studio als
erreichbar und meldeten ein installiertes aktives Textmodell. Gleichzeitig
antwortete `GET /models/recommendations?task=video_captioning&mode=balance`
mit `Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)`.

## Root Cause und Caller

`recommend_model` rief `_make_alive_client("vision")` auf.
`_make_alive_client` verwendete bei gesetzter Capability
`supports_capability` statt `is_alive`. Ein erreichbarer Provider ohne
aktives Vision-Modell wurde dadurch wie ein nicht erreichbarer Provider
behandelt. Die falsche Diagnose floss über `ApiClient` in Settings,
Models-Tools und alle Recommendation-Caller.

## Fix und Seiteneffekte

Die Auswahl bleibt capability-first. Nur wenn kein geeigneter Client
gefunden wird, erfolgt eine allgemeine Live-Probe für die Diagnose. Ist ein
Provider erreichbar, lädt `ModelRegistry.refresh` dessen installierte Modelle
und liefert den bestehenden präzisen `NoSuitableModel`-Grund, statt einen
Verbindungsfehler zu behaupten.

- Keine Providerpräferenz oder Task-Override wird geändert.
- Ein vorhandener Vision-Provider wird weiterhin direkt gewählt.
- Sind wirklich alle Provider offline, bleibt die bisherige Offline-Antwort.
- Öffentliche DTOs und OpenAPI bleiben unverändert.

Regression:
`Tests/test_models_capability_routing.py::test_recommendation_distinguishes_live_provider_from_missing_capability`.

Gezielter Cluster nach Korrektur: 15/15 PASS.
