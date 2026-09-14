# Requirements Matrix: DTO-Konsolidierung (Spec 00028)

Datum: 2026-09-12

| Anforderungs-ID | Anforderung | Implementierung | Verifikation | Status |
|---|---|---|---|---|
| FR-001 | Vollständiges Inventar aller handgeschriebenen Request-/Response-Typen mit Schema-Zuordnung | Dokumentiert in baseline.md und design-review.md; Trennung reiner DTOs von Observable-UI-Modellen | `Tests/test_openapi_snapshot_drift.py`, `TransportContractTests` | VERIFIZIERT |
| FR-002 | NSwag als Feld-/JSON-Wahrheitsquelle für schemafähige Transporttypen | `openapi.snapshot.json` ist 100% driftfrei mit FastAPI; `obj/Generated/ApiTypes.g.cs` enthält alle 45+ Schemas | `test_openapi_snapshot_drift.py` (4/4 passed) | VERIFIZIERT |
| FR-003 | ApiClient und Consumers verwenden generierte Typen oder explizite UI-Adapter | `SpectralDataModel.FromTransport`, `AudioAnalysisResult.FromTransport`, `VramHealthSingleResponse.ToMultiModelSnapshot`, `global using` für `ThumbstripResponse`, `ClipwaveResponse`, `BrainAxisContribution` | `TransportContractTests.AudioAdapter_PreservesGeneratedPartialResultAndEvidence`, `SpectralAdapter_PreservesEveryGeneratedField`, `SingleVramAdapter_ProducesOneModelSnapshotWithoutShapeDrift` | VERIFIZIERT |
| FR-004 | JSON-Namen, Nullability, SnakeCase-Mapping, Fehlerantworten kompatibel über Backend & WPF | `SnakeCaseLower` Naming-Policy in `ApiClient`; Deserialisierungstests für Fehler-, Teil- und Erfolgsantworten | `TransportContractTests.ResultDtos_DeserializeNegativeBackendTruth`, `VideoClipInfo_PreservesPartialStageTruth`, `ModelDtos_DeserializeBackendJsonTruth` | VERIFIZIERT |
| TR-001 | Keine Handänderung generierter Dateien; deterministischer Build aus Snapshot ohne Backend | `nswag.json` + `openapi.snapshot.json` im MSBuild-BeforeBuild-Target; kein manueller Eingriff in `ApiTypes.g.cs` | `dotnet build -c Release PBStudio.UI` (0 Fehler, 0 Warnungen) | VERIFIZIERT |
| TR-002 | Keine neue Paketabhängigkeit, DB-Migration oder unautorisierte Datei-Löschung | Alle Änderungen innerhalb bestehender Referenzen; keine Packages hinzugefügt | `PBStudio.UI.csproj` ungeändert bezüglich externer Packages | VERIFIZIERT |
