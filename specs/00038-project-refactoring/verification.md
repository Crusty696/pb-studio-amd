# Verifikation — 2026-10-30

## Ergebnis

T001–T004 und T006 implementiert. T005 und Gesamtrefaktorierung offen: sichtbare Bedienabnahme fehlt; weitere Architektur-Kandidaten siehe architecture-review.md. Keine .completed/.qc-passed-Marker und keine Releasefreigabe.

## Durchgefuehrte Pruefungen

- Release-Build PBStudio.UI: 0 Warnungen, 0 Fehler. Aktualisiert: PBStudio.UI/bin/Release/net9.0-windows/PBStudio.UI.dll und zugehoerige Buildausgaben.
- Vollstaendige native Suite nach allen Aenderungen: 91/91 bestanden.
- Audio-Refresh: zuerst 4 Dispatcherfehler reproduziert; nach isolierter Dispatcheranpassung 3 Identitaetsfehler und 1 bestandener Projektwechseltest; nach Abgleich 4/4, danach mit spaetem Dispatcher-Projektwechsel 5/5 bestanden.
- Unveraenderter Audio-Snapshot: 0 CollectionChanged-Ereignisse, bestehende Objekte und beide ausgewaehlten ListBox-Eintraege erhalten. Dies belegt weniger Listenarbeit, keine gemessene Gesamtbeschleunigung.
- Anchor-Vertrag: 6 Charakterisierungen gegen Original bestanden; neuer Import zuerst fehlgeschlagen, danach kompatibler Reexport und 7 Tests bestanden.
- API-/Anchor-/Wiring-Cluster: 139 bestanden, 2 uebersprungen. Acht Quelltextleser auf neue Dateigrenzen angepasst; Assertions per AST unveraendert.
- Timeline-Agent: 6 Originalcharakterisierungen bestanden, neuer Import zuerst fehlgeschlagen; 56 Regressionstests und abschliessend 15 Finalizer-/Probe-/Exporttests bestanden. Cache, ffprobe-Timeout/Fehlerkette und Finalizeralgorithmus erhalten.
- 170 Python-Quelldateien erfolgreich geparst; eigene Diffs ohne Whitespacefehler.
- Unabhaengiger statischer Review: keine belegte Regression. Zusaetzlich geforderter spaeter Projektwechseltest ergaenzt und bestanden.
- Pfade: 753 getrackte Code-/Skriptpfade sowie 20 neue Pfade ausschliesslich ASCII gemaess [A-Za-z0-9_./-]. Launcher-PowerShell-Parser: 0 Fehler. Keine PS1/BAT/CMD-Datei geaendert.
- Zusaetzliche Pfadregression: 16 Finalizer-/Probe-/Exporttests bestanden; bestehender Medienpfad mit Umlaut, Leerzeichen, &, Klammern bleibt genau ein subprocess-Argument, ohne shell=True. Beleg path-test-output.txt. Keine Datei mit solchem neuen Namen angelegt.

## Breiter Python-Lauf

Lauf mit isoliertem APPDATA/LOCALAPPDATA, PYTHONPATH=src, eigenem basetemp; Marker gpu/integration/slow ausgeschlossen. Erster Abschnitt: 1118 bestanden, 5 fehlgeschlagen, 2 uebersprungen, 9 abgewählt; Stop nach fuenf Fehlern. Rohbeleg: regression-output.txt.

Baselinekopie bewahrt alle Vorarbeiten und setzt ausschliesslich diese Python-Refaktorierungen zurueck. Guard prueft tatsaechliche Modulherkunft in der Kopie. Dieselben fuenf Fehler dort reproduziert: baseline-failures-output.txt. Vorbereitung brauchte vorhandenes FFmpeg-Buendel und importlib.import_module (backend.routers exportiert pacing_router auch als APIRouter-Attribut).

Ursache: alte positive Fixtures ohne bestehenden T056-Identitaetsvertrag, nicht diese Refaktorierung. T006 aktualisiert drei Testdateien; FAISS-Fake prueft query_identity und Metadaten, Resume/Preflight verwenden aktuelle Identitaet. Vier negative Resumevarianten pruefen fehlende/veraltete Identitaet in Analysecache und Vektormetadaten. 56 gezielte Tests bestanden. Keine Produktionsschutzregel abgeschwaecht.

T006-Befehl: .venv/Scripts/python.exe -m pytest Tests/test_clip_selector_provenance.py Tests/test_full_audit_video_contract.py Tests/test_pacing_analysis_preflight.py Tests/test_t056_embedding_identity.py --basetemp=.pytest_tmp_t006 -q; PYTHONPATH=src, isoliertes APPDATA/LOCALAPPDATA. 56 passed, 8 warnings, 20.76s, Exitcode 0 (Agent-Toolausgabe, keine separate Logdatei). Zweiter unabhaengiger statischer Review bestaetigt unveraenderte Ranking-/Fehlerassertions und zusaetzliche negative Abdeckung.

Noch nicht erreichter Teil ab test_pacing_analysis_preflight.py plus security/ separat fortgesetzt; keine Wiederholung der gesamten Suite. Ergebnis: 1138 bestanden, 3 fehlgeschlagen, 6 uebersprungen, 3 abgewählt, 811.15s. Dieser Prozess hatte die alten Fixtures vor T006 bereits geladen; zwei bekannte Preflightfehler darin sind deshalb Altbefunde. Dritter Fehler: test_pacing_video_data_flow.py erwartete nutzbare Embeddings ohne Identitaet. Beleg regression-remaining-output.txt.

Auch der sechste Fehler wurde ohne unsere Refaktorierung reproduziert (baseline-video-flow-output.txt). Fixture um aktuelle Identitaet ergaenzt und aktuelle/fehlende/veraltete Identitaet parametrisiert; ungueltige Identitaet darf weder has_embedding=True noch den Vektor an Pacing weiterreichen. 20 gezielte Tests bestanden (video-flow-test-output.txt), Produktionscode unveraendert.

Zusammen decken beide breiten Abschnitte alle 2267 ausgewaehlten urspruenglichen Python-Faelle ab; fuenf Preflightfaelle ueberlappten. Ohne Doppelzaehlung: 2253 bestanden, 6 veraltete positive Fixtures fehlgeschlagen, 8 uebersprungen; 9 Markerausschluesse. Alle sechs Fehler anschliessend gezielt korrigiert und in den 56-/20-Testlaeufen bestanden. Zusaetzliche Negativ-/Pfadfaelle ebenfalls geprueft. Kein einzelner komplett gruener Vollsuite-Lauf auf dem abschliessenden Stand behauptet.

## Isolierte Laufzeitpruefung

Nutzer hat isolierte Testkopie bestaetigt. temp/refactor-038-runtime enthaelt eigene Quellen, Releaseausgabe, FFmpeg/LHM, leeren Katalog, Projektverzeichnis und APPDATA/LOCALAPPDATA. .venv ist eine explizite Junction zur vorhandenen Abhaengigkeitsumgebung; keine Installation. Keine Produktionsdatenbank oder Originalmedien kopiert/migriert.

Offizieller unveraenderter Launcher gestartet. Backend aus Testkopie meldet /health status=ok und gpu_available=true. Dies ist kein GPU-Inferenztest. WPF-Start durch bestehendes Launcherproblem blockiert: Get-NetTCPConnection sieht den Socket 127.0.0.1:8765 mit OwningProcess, aber ohne State; Filter -State Listen liefert keine Objekte. Health 200 allein beendet Wait-ForBackend deshalb nicht.

PowerShell-5-Erstversuch hatte zusaetzlich einen ungeeigneten geerbten Modulpfad (Get-FileHash unbekannt); mit nativen Modulpfaden laeuft der Launcher bis zum Socketproblem. Logausgabe zeigt bestehende Encodingprobleme bei Umlauten; neue Pfade sind ASCII.

Separater WPF-Start mit gemeinsamem temporaerem Owner-Token wurde durch automatische Freigabepruefung mit "blocked by policy" abgewiesen; keine weitere Begruendung. Keine Umgehung. Eigene isolierte Launcher-/Backendprozesse danach anhand Prozesspfad und Eltern-PID geprueft und beendet. Keine sichtbare WPF-/Medienabnahme.

Produktions-config.json, WPF-settings.json, CURRENT, RUNTIME_DIRTY und journal.json vor/nach Test hashgleich (protected-hashes-before.json, protected-hashes-after.json). Produktions-Recovery unveraendert; normaler Start bleibt wegen moeglicher Wiederherstellung der Generation vom 25.09. ungeprueft. Kopierte und aktuelle Release-DLL hashgleich. Vom Nutzer vorgegebener Test-PowerShellSyntax.ps1 bestaetigt Launcher-Syntax; keine Ausfuehrungs-/Funktionsfreigabe daraus abgeleitet.

## Grenzen

Kein Produktionsbackend-Neustart, keine Datenmigration, keine Produktionsrender-/Modellabnahme mit Originalmedien, keine visuelle Gesamtfreigabe, keine Zeit-/RAM-/VRAM-Benchmarkbehauptung. Die automatisierten Tests besitzen eigene Medien-/DSP-/FFmpeg-Pruefungen; daraus wird keine Nutzerabnahme abgeleitet. pacing/__init__.py importiert die Engine weiterhin eager: Entkopplung von PacingService ist keine belegte Importzeitbeschleunigung. Fremde lokale Vorarbeiten bleiben erhalten; keine pauschale Commitaufnahme.
