# QC Report: KI-Modus-Sync, Modell-Zuordnungs-Heuristik & LM-Studio Fallbacks

## 1. Testumgebung
- OS: Windows 10
- GPU: AMD Radeon RX 7800 XT (DirectML)
- Python Version: 3.11.9
- .NET SDK: 10.0

## 2. Testergebnisse

### 2.1 Backend Unit-Tests
- Datei: `Tests/test_model_registry.py`
- Status: **BESTANDEN** (24/24 Tests)
- Kommando: `.venv/Scripts/pytest Tests/test_model_registry.py`

### 2.2 System-weite Modell-Tests
- Status: **BESTANDEN** (66 passed, 2 skipped, 674 deselected)
- Kommando: `.venv/Scripts/pytest Tests/ -k model`

### 2.3 Frontend-Kompilierung
- Status: **BESTANDEN** (0 Fehler, 0 Warnungen)
- Kommando: `dotnet build PBStudio.UI/PBStudio.UI.csproj -c Release`

## 3. Manuelle Verifikationsschritte
1. **KI-Modus Sync:** Endpoint `POST /models/mode` verifiziert, persistiert den Modus korrekt in `config.json`.
2. **Sortier-Heuristik:** Heuristik-Bug behoben; unbekannte Modellgrößen werden an das Ende sortiert, sodass das VLM `google/gemma-4-e4b` korrekt vor `llava-nousresearch` priorisiert wird, wenn letzteres seine Größe nicht angibt.
3. **Retry-Fallbacks:** VLM-Ladefehler in LM-Studio werden durch die Retry-Schleife mit Ausschlussliste abgefangen. Die Anwendung fällt nahtlos auf das nächste funktionierende Modell zurück.

QC bestanden am 2026-06-08.
