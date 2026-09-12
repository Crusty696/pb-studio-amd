# Tasks: Offenen Backlog vollständig verifizieren

**Status:** OPEN
**Spec:** spec.md
**Plan:** plan.md

- [ ] T001 [OBJ-76] Reales Tagging, Degradation, Shutdown, Restart/Resume; Evidence in specs/00021-live-runtime-truth-and-observability/evidence/
- [ ] T002 [OBJ-76] Zehn Canary-Clips mit unveränderten validen Stage-Hashes; gleicher Evidence-Pfad
- [X] T003 Pacing-Degradation ohne Video-Audio live prüfen; evidence/pacing-degradation-without-audio-key.md
- [X] T004 audio_key unavailable/failed real unterscheiden; evidence/audio-key-unavailable-failed.md
- [X] T005 Beschädigte Video-Stage-Schlüssel inventarisieren und gezielt heilen; evidence/video-stage-keys-audit.md (0 von 706 beschädigt, sauber)
- [ ] T006 WPF mit echtem Backend vollständig sichtbar prüfen; evidence/
- [X] T007 [P] has_audio_embedding entlang Cache/Analyse/Reload/Listing korrigieren; evidence/audio-embedding-flag.md
- [X] T008 [P] peak-Struktur vollständig und konsistent gewichten; evidence/peak-regression.md
- [X] T009 [P] Binding-Wächter auf exakte Pfade und passende DataContexts umstellen; Tests/test_viewmodel_binding_wiring.py
- [X] T010 DTOs mit generierten NSwag-Typen konsolidieren; PBStudio.UI/
- [ ] T011 Brain-Semantik/Projector mit realen Medien und 20 korrekt bezeichneten Bewertungen prüfen; evidence/
- [X] T012 Render-Retention und progress_percent schließen; backend/routers/render_router.py
- [X] T013 Externes Config-Hot-Reload schließen; src/pb_studio/core/config.py
- [X] T014 Echte Chat-Token-Deltas verdrahten; src/pb_studio/ai/chat_agent.py
- [X] T015 Video-Grid-Virtualisierung nach explizitem Detaildesign implementieren; PBStudio.UI/Views/VideoLibraryView.xaml
- [X] T016 Legacy-Aufbewahrung oder Löschung evidenzbasiert entscheiden; evidence/legacy-decision.md (dauerhaft behalten; neun AST-Pruefungen bestanden)
- [X] T017 Test-Skip-Ausnahmen aktuell prüfen und begründet behandeln; config/pytest-skip-allowlist.json
- [X] T018 Security-Ausnahmen aktuell prüfen und begründet behandeln; config/
- [X] T019 Alte Wegwerf-Umgebungen auf Nutzung prüfen und kontrolliert bereinigen; .venv-pre-lock-20260830 und .venv-lock
- [X] T020 Draft-PR 29 samt IRON-Hook prüfen und aktualisieren/fertigstellen oder schließen; evidence/pr29-decision.md (CLOSED verifiziert; Branch behalten)
- [ ] T021 Unabhängige Reviews, vollständige Tests, Release-Build und abschließende GUI-QC; qc-report.md
- [ ] T022 Brain-Projektlog und autorisierte Codex-Erinnerungen aktualisieren; C:/Users/david/Brain/10_Projects/PB_studio/
