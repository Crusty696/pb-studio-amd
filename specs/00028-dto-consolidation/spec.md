# C#-Transporttypen auf NSwag konsolidieren

**Status:** SPECIFIED, 2026-09-07. **Quelle:** Nutzerauftrag Punkt 10; specs/00023-backlog-completion.

## Ziel und Geltungsbereich
Den genannten Backlogpunkt vollständig im realen App-Pfad schließen. Die folgenden Designentscheidungen sind Vorschläge dieser Spezifikation, keine behaupteten früheren Beschlüsse. Keine Implementations- oder Live-Abnahme wird hier behauptet.

## Befund
`PBStudio.UI/nswag.json` erzeugt Records im Namespace `PBStudio.UI.Generated` aus `openapi.snapshot.json` nach `obj/Generated/ApiTypes.g.cs`, ohne generierten HTTP-Client. `IApiClient.cs` verwendet manuelle Modeltypen und bereits `Generated.SpectralData`. Historischer Plan `docs/superpowers/plans/2026-05-19-nswag-openapi-codegen.md` sieht schrittweise DTO-Migration vor; aktuelle Konfiguration ist maßgeblich.
## Anforderungen
- FR-001: Vollständiges Inventar aller handgeschriebenen Request-/Response-Transporttypen und Endpunkte mit eindeutiger Zuordnung zum generierten Schema. Reine Observable-/Darstellungsmodelle bleiben getrennte UI-Modelle.
- FR-002: Alle schemafähigen Transporttypen verwenden NSwag als einzige Feld-/JSON-Wahrheitsquelle. Fehlende Backend-response_model-Verträge werden explizit ergänzt und Snapshot regeneriert, statt manuelle DTO-Duplikate dauerhaft zu behalten.
- FR-003: ApiClient und Consumers übernehmen generierte Typen mit expliziten UI-Adaptern dort, wo Darstellung oder Observable-Verhalten erforderlich ist. Adapter duplizieren keinen vollständigen Drahtvertrag. Jeder verbleibende manuelle Typ benötigt konkrete Begründung als UI-/nicht-OpenAPI-Vertrag.
- FR-004: JSON-Namen, Enumwerte, Nullability, ausgelassene optionale Felder, Zeitstempel, Collections, Defaultwerte und Fehlerantworten bleiben über Backend und WPF kompatibel. Bestehende Cancellation-/Error-/SSE-Logik bleibt erhalten.
- TR-001: Keine Handänderung generierter Dateien; deterministischer Build aus eingechecktem Snapshot ohne laufendes Backend. Öffentliche `IApiClient`-Signaturänderungen vor Umsetzung im Mapping konkret benennen und innerhalb des autorisierten Featureauftrags reviewen.
- TR-002: Keine neue Paketabhängigkeit, DB-Migration oder automatische Entfernung handgeschriebener Dateien ohne geprüfte Referenzfreiheit und ausdrückliche Löschfreigabe. Referenzfreie Dateien können bis Freigabe außerhalb der Kompilierung archiviert bleiben.
## Abnahme
Endpoint-/DTO-Matrix besitzt keine unerklärten Transport-Duplikate. Reale Backend-JSON-Fixtures decken jedes migrierte Vertragscluster ab; Deserialisierung und Request-Serialisierung sowie ViewModel-Adapter getestet. C#-Tests, reproduzierbarer Release-Build, Snapshot-Driftprüfung und sichtbare Hauptflows mit echtem Backend bestehen.

## Gates
Getrenntes Feature gemäß specs/00020-obj75-open-bug-fixes/residual-remediation-plan.md. Dessen OBJ-75-Release-Vorbedingung vor Implementierung anhand aktueller Marker prüfen; fehlendes Gate explizit beim Parent behandeln. Spec → Plan → Tasks → Implement → QC. Keine .completed/.qc-passed ohne reale Belege. Python 3.11/NumPy 1.26.4, DirectML/AMF und bestehende Recovery-Grenzen gelten.
