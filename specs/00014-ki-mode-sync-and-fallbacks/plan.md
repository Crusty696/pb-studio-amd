---
type: plan
project: pb_studio
created: '2026-06-08'
updated: '2026-06-08'
title: KI-Modus-Sync, Modell-Zuordnungs-Heuristik & LM-Studio Fallbacks
status: draft
tags: [ai, model-management, robust-fallbacks]
---
# Plan: KI-Modus-Sync, Modell-Zuordnungs-Heuristik & LM-Studio Fallbacks

## Übersicht

Behebung von Synchronisationsproblemen des KI-Modus (Speed/Balance/Quality) zwischen Frontend und Backend, Behebung des Sortierungsfehlers bei Modellen mit unbekannter Parametergröße sowie robustes Retry-Fallback-Handling bei fehlgeschlagenem Laden von Multimodal-Modellen in LM-Studio.

## Status

- [ ] Phase 1 — Backend-Implementierung (API, Registry-Fix, Fallback-Retry)
- [ ] Phase 2 — Frontend-Implementierung (ApiClient-Erweiterung, Settings-Integration)
- [ ] Phase 3 — Integrationstest & Verifikation (WPF-Build, Python-Tests)

## Phasen

### Phase 1 — Backend-Implementierung

**Ziel:** API bereitstellen, Sortierung korrigieren und Fehlertoleranz beim Laden verbessern.

**Schritte:**
1. **Sortier-Heuristik fixen:** In `src/pb_studio/ai/model_registry.py` unbekannte Modellgrößen ans Ende sortieren, damit bekannte Größen Vorrang erhalten.
2. **Retry-Logik implementieren:** In `src/pb_studio/video/lmstudio_vision_wrapper.py` fehlerhafte Modelle temporär ausschließen und das nächste Modell versuchen.
3. **Modus-Sync API bereitstellen:** In `backend/routers/models_router.py` neuen POST-Endpoint `/mode` definieren, der den Modus in `config.json` persistiert.
4. **Modus-Dynamik aktivieren:**
   - In `models_router.py` (`list_models`) den konfigurierten `default_mode` für die Task-Zuweisung verwenden.
   - In `backend/routers/video_router.py` den konfigurierten `default_mode` für das Tag-Extraction-Routing nutzen.

**Verifikation:**
- Python Unit-Tests ausführen, insbesondere `test_model_registry.py`.
- Swagger / OpenAPI Dokumentation aufrufen und den neuen `/models/mode` Endpoint manuell verifizieren.

### Phase 2 — Frontend-Implementierung

**Ziel:** WPF-Frontend an den neuen Modus-Sync anbinden.

**Schritte:**
1. **ApiClient erweitern:** `IApiClient.cs` und `ApiClient.cs` um die Methode `UpdateKiModeAsync(string mode)` erweitern.
2. **Settings-Anbindung:** In `SettingsViewModel.cs` beim Speichern der Einstellungen (und beim Ändern des Modus) die Methode `UpdateKiModeAsync` aufrufen.
3. **Status-Aktualisierung triggeren:** Nach erfolgreichem Modus-Sync die Modellliste aktualisieren (durch Aufruf von `ModelManagerViewModel.LoadAsync`), damit die Task-Badges ("aktiv in...") sofort der neuen Auswahl entsprechen.

**Verifikation:**
- Dotnet-Kompilierung ohne Fehler und Warnungen.

### Phase 3 — Integrationstest & Verifikation

**Ziel:** Das Gesamtsystem E2E testen und robustes Fallback-Verhalten nachweisen.

**Schritte:**
1. **Smoke-Test:** Backend und Frontend starten, in Settings den Modus umschalten und prüfen, ob die Badges im Tab MODELLE sich sofort korrekt anpassen.
2. **Simulierter Ausfall:** LM-Studio mit inkompatiblem VLM-Modell aufrufen und prüfen, ob das Backend stabil auf ein funktionierendes Alternativmodell (z.B. gemma-4-e4b) ausweicht.

## Anweisungen für Agenten

- **Zonen:** Z-CORE, Z-VIDEO, Z-UI-VM, Z-UI-SERVICES
- **Iron Rule 1:** AMD DirectML only.
- **Iron Rule 10:** Fehlerhaftes Laden in LM-Studio darf nicht zum Absturz führen, sondern muss kaskadieren.

## Referenzen

- Specs: [spec.md](file:///C:/Users/david/Documents/Pb_studio_AMD_version/specs/00014-ki-mode-sync-and-fallbacks/spec.md)
