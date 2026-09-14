# T016: Legacy-Aufbewahrung

Entscheidung 2026-09-06: Die sieben im bestehenden AST-Waechter erfassten
Symbole bleiben dauerhaft als Legacy gekennzeichnet erhalten. Keine Loeschung.
Reaktivierung bleibt eine eigene Code-/Architekturentscheidung mit Tests.

Inventar: AnalysisService, GenerationService, MediaService, VideoGenerator,
VRAMArbiter, VideoEmbedder, get_video_embedder. SmartDirector ist weiterhin
produktiv und nicht als vollstaendiges Modul stillgelegt.

Verifikation: Alle sieben parametrisierten Aufruferpruefungen sowie Modulmarker-
und SmartDirector-Gegenprobe aus
Tests/test_legacy_symbols_have_no_production_callers.py direkt ausgefuehrt:
9 bestanden. Methode: runpy und Aufruf der read-only AST-Testfunktionen,
ohne pytest-conftest und ohne Import von backend.main. Kein Vollsuite-Beleg.

Grund: Vorhandene isolierte Kompatibilitaetsimplementierungen verursachen
keine belegte aktive Funktionsstoerung. Loeschen ist fuer das Nutzerziel nicht
erforderlich; symbolgenaue Markierung und Waechter halten die Trennung sichtbar.
