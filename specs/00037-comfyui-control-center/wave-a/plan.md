# Welle A Implementierungsplan

1. T001 Freigabe/Arbeitsbasis/Testsicherheit dokumentieren.
2. T003 typed Settings/Endpoint/Discoveryvertrag und begrenzten async GETclient; ConfigManager-Anbindung ohne Startupnetzwerk.
3. T004 conservative Node-/Modell-/Versionsprofile; qualifizierte Laufzeitbereitschaft bleibt false.
4. T045: isolierte Tests, Kompilierung, unabhängiger Review, realer minimaler GETnachweis ohne Inventarscan bei laufender Arbeit, Dokumentation und Schutzdatei-Hashes.

Codezonen: Worker comfyui/** und zwei spezifische Testdateien; Parent config_manager, Tests/test_comfyui_config.py, Dokumente. Keine Überschneidung. Abschließende Prüfung sequenziell. Bestehende Arbeitsbasis erhalten.
