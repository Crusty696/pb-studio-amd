# Spezifikation: KI-Modus-Sync, Modell-Zuordnungs-Heuristik & LM-Studio Fallbacks

## 1. Problemstellung und Ist-Zustand

Der KI-Bereich von PB Studio weist aktuell drei kritische Schwachstellen auf:

1. **Modus-Drift zwischen Frontend und Backend:**
   Das WPF-Frontend ermöglicht es dem Nutzer in den Einstellungen, den KI-Modus (`Speed`, `Balance`, `Quality`) zu wechseln und zu speichern. Dieser Wert wird jedoch nur in `%APPDATA%\PBStudio\settings.json` abgelegt und nicht an das Python-Backend übertragen. Das Backend nutzt fest codierte Standardwerte (`mode="balance"`) in der Video-Analyse (`video_router.py`) sowie bei der Bestimmung der aktiven Tasks im Modell-Manager (`models_router.py`). Dadurch bleibt der KI-Modus-Wechsel für den eigentlichen Analyseprozess wirkungslos und die Anzeige aktiver Modelle aktualisiert sich nicht.

2. **Heuristik-Bug bei unbekannter Modellgröße (Registry-Fehler):**
   In `model_registry.py` parst `_parse_parameter_size` die Modellgröße aus dem Namen. Enthält ein Modellname keine Parameterangabe (wie `llava-nousresearch_nous-hermes-2-vision`), liefert die Funktion `0.0` zurück. In `_sort_models_by_mode` führt dies im `Balance`-Modus dazu, dass dieses Modell fälschlicherweise exakt als `8B`-Modell eingestuft wird (da `x[1] if x[1] > 0 else 8.0` angewendet wird). Dadurch erhält das Modell eine perfekte Distanz von `0.0` zu `8B` und verdrängt andere, tatsächlich geeignete und funktionierende Modelle (wie `google/gemma-4-e4b`).

3. **Mangelnde Robustheit bei LM-Studio Ladefehlern:**
   Versucht LM-Studio ein Modell zu laden, das inkompatibel oder beschädigt ist (z.B. Multimodaler Projektor-Fehler `unknown projector type` bei `llava-nousresearch`), antwortet der Server mit `HTTP 400 Bad Request`. Das Backend fängt diesen Fehler zwar im Chat-Wrapper ab, fällt aber sofort auf das (nicht vorhandene) lokale Moondream-ONNX-Modell zurück. Es findet kein automatisches Ausweichen auf das nächstbeste installierte Modell (wie `google/gemma-4-e4b`) statt.

## 2. Zielsetzung und Soll-Zustand

- **API-gesteuerter Modus-Sync:** Das WPF-Frontend benachrichtigt das Backend per API-Call (`POST /models/mode`), wenn sich der KI-Modus ändert oder gespeichert wird. Das Backend persistiert diesen Wert in seiner `config.json` unter `ai.default_mode` und wendet ihn dynamisch in der Video-Analyse und bei der Ermittlung der aktiven Tasks an.
- **Korrigierte Sortier-Heuristik:** Modelle mit unbekannter Parametergröße werden bei der Sortierung im `Speed`-, `Quality`- und `Balance`-Modus ans Ende gestellt, sodass bekannte, passend dimensionierte Modelle immer Vorrang haben.
- **Robustes Retry-Ladeverfahren (Modell-Kaskade):** Schlägt das Laden eines Modells in LM-Studio fehlschlägt (z.B. HTTP 400), wird dieses Modell temporär ausgeschlossen (`exclude`) und die Auswahl kaskadiert automatisch auf das nächste geeignete Modell in der Liste.

## 3. Architektur-Änderungen

### 3.1 Backend (Python API)
- Neuer Endpoint `POST /models/mode` in `models_router.py`.
- Aktualisierung von `video_router.py` (Verwendung des konfigurierten `default_mode` statt `"balance"` bei der Analyse).
- Aktualisierung von `models_router.py` (Verwendung des konfigurierten `default_mode` bei der Ermittlung von `active_tasks`).
- Fehlerbereinigung in `src/pb_studio/ai/model_registry.py` (`_sort_models_by_mode` zur Benachteiligung unbekannter Modellgrößen).
- Ausfallsicherheit in `src/pb_studio/video/lmstudio_vision_wrapper.py` (`_async_extract_tags` mit Retry-Ausschlussliste).

### 3.2 Frontend (C# WPF)
- `IApiClient` und `ApiClient.cs` erweitern um `UpdateKiModeAsync(string mode)`.
- `SettingsViewModel.cs` anpassen: Beim Ändern/Speichern des `KiMode` den Backend-Endpoint aufrufen und nach Erfolg die Modellliste aktualisieren (damit die Badges korrekt gezeichnet werden).
