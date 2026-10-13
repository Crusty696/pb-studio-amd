# Welle B — Workflowverträge und lokale Policy

Nutzerauftrag „nächster Schritt“ nach abgeschlossener Welle A führt die dokumentierte Folgewelle B (T005→T006) mit anteiliger T045 fort. Frühere Grenzen unverändert: keine Generierung/GPU/Installation/Migration, keine laufenden ComfyUI-Aufträge anfassen. Kein Produktserverzugriff in dieser Welle vorgesehen.

Ziel: immutable Workflowrevisionen registrieren, Aktivierung separat dauerhaft per CAS verwalten, APIgraph/Parameter/Outputs statisch prüfen und lokale Policybeweise konservativ beurteilen. Produkt-Datenbank bleibt unverändert. Explizite neue Registrydatei ausschließlich in isolierten Tests initialisieren; keine globale automatische Registrierung.

Abnahme: isolierte Negativ-/Positivtests, Redaction vor Backend-SSEpublikation, Datei-/Parallel-/Replaygrenzen, unabhängiger Review, Regression WelleA. Static-valid ist weder Smoke noch qualifizierte Ausführung. Fehlende Runtime-/Egressbeweise bleiben unknown/unqualified.
