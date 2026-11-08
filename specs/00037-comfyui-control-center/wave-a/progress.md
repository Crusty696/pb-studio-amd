# Welle A — Ausführungsjournal

2026-10-13: Nutzer genehmigt T001/T003/T004 und anteilige T045-Prüfungen. Keine Generierung, GPU-Läufe, Migrationen oder Installationen; fremde Aufträge unberührt.

T001: Scope genehmigt. Bestehende Dirtydateien laut Startvorbereitung erhalten. Branch codex/full-audit-remediation, keine main/master-Änderung. Arbeitsstand inkl. vorhandener Änderungen bleibt bewusst im bestehenden Checkout; neue Worktree würde diese geprüfte Arbeitsbasis nicht automatisch enthalten.

Ruling: Tests dieser Welle mit --noconftest und expliziter kleiner pytest-Konfiguration; globale Tests/conftest.py besitzt GPU-Adapter-Autouse. Keine Übernahme schwerer Backend-/GPUfixtures. Temp-Konfiguration und LOCALAPPDATA vor Import setzen. Kein produktiver Backendimport/-start.

T003/T004: in Arbeit. T002 und T005ff bleiben offen. T045 nur diese Welle; keine globalen Spec00037-Marker. Verwendete Skills: pb-master, Caveman, test-driven-development, verification-before-completion; Ausführungsledger entsprechend executing-plans, disjunkte Implementierung gemäß Projektdelegation.

Config TDD: ursprüngliche13Tests fail (fehlender Accessor/Validierung); zusätzlich invalid_set fail (ungültiger Wert wurde persistiert). Gezielte neue comfyui-Validierung vor Speicherung und Rollback des RAMwerts bei Speicherfehler, übrige set-Semantik erhalten. GREEN folgt nach gemeinsamem Schemalieferstand.

Quellreview-Livegrenze: GET /object_info startet laut gelesener Comfy-Quelle Assetscan. Kein Live-Inventarscan bei laufender Comfy-Arbeit. Realer Adapterbeleg auf inventory=False/system_stats beschränken, kompletten Transport isoliert prüfen. Welle A liefert Bibliotheksverträge, keine WPF-/Startupverdrahtung (T022ff).

Parentprüfung: Config16 + bestehende Hotreload6 =22passed. Worker initiale Client14/Capability10green. Unabhängiger Review findet JSONoverflow/Surrogates sowie unknown-vs-empty bei ausgefallenen Modellrollen. Worker korrigiert mit negativen Tests; noch kein QC-PASS. Protectedhashes unverändert.

Abschluss:53Tests+20Subtests bestanden,155Dateien compilefehlerfrei. Genau ein echter GETsystem_stats über neuen Adapter, keine anderen Serverrouten. Reviewer nach Korrekturen ohne Blocker. T001/T003/T004 und Welle-A-T045 abgeschlossen; Rootmarker bleiben abwesend.
