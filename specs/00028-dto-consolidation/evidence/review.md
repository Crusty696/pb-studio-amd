# Review: DTO-Konsolidierung (Spec 00028)

Datum: 2026-09-12

## Vertragsreview & Befund
1. **NSwag-Generator & Snapshot-Integrität**:
   - `PBStudio.UI/openapi.snapshot.json` deckt alle 45+ Routen und Schemas der FastAPI-Applikation vollständig und driftfrei ab.
   - `test_openapi_snapshot_drift.py` bestätigt, dass kein Routen- oder Feld-Drift zwischen Python-Pydantic-Modellen und dem Snapshot vorliegt.
2. **Transport- und UI-Modelle (FR-001 / FR-003)**:
   - Reine Transportdaten werden via `PBStudio.UI.Generated` oder explizite `.FromTransport(...)`-Adapter in Domain-Modelle übersetzt.
   - WPF-spezifische `ObservableObject`-Klassen (`VideoClipModel`, `TimelineEntryModel`, `AudioClipModel`) bleiben sauber getrennt und kapseln UI-spezifische Eigenschaften (Formatierte Strings, Brush/Color-Bindings, Auswahllogik).
   - Ausnahmen wie `BrainExplainResponse` sind nachvollziehbar dokumentiert (Pydantic `anyOf: [string, null]` Inkompatibilität mit NSwag 14 Record-Generierung).
3. **Kompatibilität & Wire-Safety (FR-004)**:
   - System.Text.Json Deserialisierung mit `JsonNamingPolicy.SnakeCaseLower` verifiziert in 64 Tests.
