# Projektrefaktorierung Implementation Plan

**Goal:** Wartbarkeit, vermeidbare Arbeit und Audio-Bibliotheksbedienung gemeinsam verbessern.
**Architecture:** Bestehende WPF/FastAPI/Core-Architektur bleibt. Kompatible Fassaden delegieren an kleine Module; UI bewahrt projektgebundene Objektidentität.
**Tech Stack:** .NET 9 WPF, Python 3.11, bestehende Dependencies.
**Spec:** spec.md

## Global Constraints

Keine Installation, Providerumschaltung, Datenmigration oder Änderung geschützter separator.py. Fremde Änderungen erhalten. PYTHONPATH=src; Tests isolieren APPDATA/LOCALAPPDATA. Release-Build nach C#-Änderungen. Tests sind keine sichtbare Abnahme.

## Review Focus

- Projektwechsel mit identischen numerischen Clip-IDs: keine fremden Modelle/Auswahl behalten.
- Entfernte und umsortierte Audioclips: Auswahl verbleibender Einträge erhalten, Reihenfolge Backend-getreu.
- Timeline mit fehlender Dauer/Quellenwiederholung: Metadaten, In-place-Vertrag und Exportbudget erhalten.
- API-Partialaufteilung: genau ein Lifecycle-/Cancellationzustand; DI und öffentliche Typen unverändert.
- Fehlende oder fehlerhafte Anchor-Datei: bisheriges Fehlerverhalten erhalten.

## Tasks and Validation

### T001 — API-Verantwortungen
Files: PBStudio.UI/Services/ApiClient.cs und neue ApiClient.*.cs/ApiResponseModels.cs.
Transportklasse nach vorhandenen Domänengrenzen in partial-Dateien teilen; Response-Records unverändert auslagern. Kein SSE-Algorithmuswechsel ohne eigene Charakterisierung.
Prüfung: Release-Build, TransportContractTests, ApiClientContractTests, vollständige native Suite.

### T002 — Audio-Bibliothek
Files: PBStudio.UI/ViewModels/AudioLibraryViewModel.cs, neue PBStudio.UI.Tests/AudioLibraryRefreshTests.cs.
Zuerst reproduzierender STA-Test für Mehrfachauswahl/Objektidentität und entfernte Einträge. Identitätsbasiert aktualisieren, Backend-Reihenfolge erhalten, Projektwechsel weiterhin leeren. Unveränderte Antwort verursacht keine CollectionChanged-Events; das ist ein Arbeitsmengenbeleg, keine Zeitmessung.
Prüfung: neue Tests, ProjectSwitchUiPublicationTests, vollständige native Suite, sichtbare Bibliothek.

### T003 — Gemeinsamer Timelineabschluss
Files: src/pb_studio/pacing/timeline_finalizer.py, src/pb_studio/services/pacing_service.py, backend/routers/render_router.py, Tests/test_timeline_finalizer.py.
finalize_cut_list(cut_list, target_duration, duration_resolver) extrahiert vorhandenen Algorithmus. Pacing-Methode bleibt Delegator. Export nutzt Finalizer mit kompatibler Dauerprobe ohne PacingService-Import. Dauerprobe nutzt denselben ffprobe-Vertrag und aufruflokalen Cache.
Prüfung: Charakterisierung zu Mutation, Wiederholung, Metadaten, Dauergrenzen; vorhandene Pacing-/Render-Vertragstests. Import-/Initialisierungsreduktion belegen, keine ungemessene Laufzeitbehauptung.

### T004 — Anchor-Persistenz
Files: backend/project_anchors.py, backend/routers/project_router.py, backend/routers/pacing_router.py.
Vorhandene load_project_anchors-Funktion in gemeinsames Modul auslagern; Projekt-Router reexportiert zur Kompatibilität. Pacing importiert direkt. Tests test_project_close_anchor_contracts.py und test_pacing_canvas_contract.py.

### T005 — Konvergenz
Eigene Diffs auf Fremdänderungen prüfen. Python-Kompilation und betroffene Tests; Release-Build/native Suite sequenziell. Laufzeitprüfung mit offiziellem Launcher nur nach Prüfung aktiver Prozesse/Jobs. Prüfbericht, CHANGELOG und Vault aktualisieren. Offene Risiken und nicht geprüfte Abläufe explizit dokumentieren.

### T006 — Bestehende Embedding-Testvertraege synchronisieren
Baselinevergleich reproduziert alle fuenf Fehler ohne diese Refaktorierung. Positive Fixtures in Tests/test_clip_selector_provenance.py, Tests/test_full_audit_video_contract.py und Tests/test_pacing_analysis_preflight.py auf bestehenden T056-Identitaetsvertrag aktualisieren. FAISS-Fake akzeptiert/prueft query_identity; Analyse- und Vektormetadaten enthalten aktuelle Identitaet. Resume lehnt fehlende/veraltete Identitaet auf beiden Seiten weiterhin ab. Produktionscode unveraendert. Pruefung: drei betroffene Dateien plus Tests/test_t056_embedding_identity.py.

Abschlusslauf: sechste veraltete Fixture in Tests/test_pacing_video_data_flow.py ebenfalls gegen Baseline reproduziert. Aktuelle/fehlende/veraltete Identitaet parametrisieren, has_embedding und Vektorweitergabe pruefen; uebrige Motion-/Tag-/Farbassertions erhalten.

## Weitere geprüfte Kandidaten

Streaming-Checkpoint, Render-Belegwriter, Pacing-Triggerbau, Timeline-VM und Video-VM: geeignete Folgeextraktionen, aber nicht allein wegen Dateigröße umbauen. AppState/Recovery sowie Chat-Auth sind hochriskante Zustandsgrenzen und bleiben bis eigener Charakterisierung unverändert. Die Gesamtinventur ist kein Abschluss dieser Kandidaten.
