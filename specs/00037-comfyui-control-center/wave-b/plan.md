# Welle B Plan

1. T005 frozen WorkflowDTOs mit canonical content, Registrydatei atomar/gesperrt, CAS/Idempotenz, Parameter-/Graph-/Outputvalidator.
2. T006 policy prüft local-only/Secrets/Profil-/Graphbindung; fehlende echte Auditevidence kein qualified. Backend-SSE message/detail/source vor Publikation redigieren.
3. T045 scoped Tests, unabhängiger Review, vorhandene WelleA-Regression, compile und geschützte Hashes.

Konkrete Interfaceergänzung zu Master P: workflow_schemas.py kapselt immutable validierte DTOs separat von DiscoveryDTOs. Manifest enthält vollständige Node-Schemata und Referenzhashes, deren Hash gegen Discovery geprüft wird. ValidationIssue(code,path,expected,observed), ValidationReport mit discovery_generation/profile_binding/execution_ready. log_redaction.py ist reiner Helper ohne Backendimport. check_workflow_policy darf optional explizite audit/effective-Identität als Keywordkontext konsumieren; Manifest allein darf keine Laufzeitattestierung erzeugen. Details/API in Developer Guide nach Umsetzung.

Registrydatei ist neuer Workflowmetadatenstore, kein zweiter Medienkatalog. Pfad explizit vom späteren Besitzer, Tests temp. Keine produktive Migration/initiale Registryinstallation. Laufzeit-/QS-/Restoreintegration spätere Gates. Regelergänzungen dokumentieren keine neue externe Dienstesteuerung.
