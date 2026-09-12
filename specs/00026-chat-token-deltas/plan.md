# Plan: Echter Chat-Tokenstream bis WPF

**Status:** PLANNED, 2026-09-07. **Basis:** spec.md.

## Voraussetzungen und Clarify
Spec gelesen; Umfang durch FR/TR-IDs begrenzt. Konkrete vorgeschlagene Entscheidungen stehen in spec.md. Kein Nutzerwunsch wird als bereits getestet ausgegeben. Vor Implementation prüft Parent das vorgelagerte OBJ-75-Gate sowie neue Architektur-/API-Entscheidungen; keine stillschweigende Umgehung.

## Architektur und Umsetzung
Providerparser liefert getrennte Content-/Reasoning-/Tool- und Finishfelder. ChatAgent erhält einen streamingfähigen gemeinsamen Attempt-Pfad für alle bisherigen Modell-/Tool-Fallbacks, einschließlich finaler Zusammenfassung. Attempt-Zustand merkt ob Content veröffentlicht wurde; Retry danach nicht automatisch. Toolaggregation und Dispatch sind getrennt, Finish einmalig. SSE text_delta wird additiv, finales text bleibt Abschluss-Snapshot. UI verarbeitet Deltas in derselben Nachricht und ersetzt beim Abschluss mit verifiziertem final_text statt erneut anzuhängen.

## Dateien und Ownership
src/pb_studio/ai/lmstudio_client.py; src/pb_studio/ai/chat_agent.py; backend/routers/chat_router.py; PBStudio.UI/ViewModels/ChatViewModel.cs; zugehöriger SSE-Consumer. Der Implementierer besitzt nur ausdrücklich vom Parent zugewiesene Dateien. Tests erhalten eigene eindeutige Pfade; bestehende Änderungen anderer Agenten bleiben erhalten. Shared-Zonen und C#-Builds sequenziell, keine parallele Vollsuite.

## Verifikation
Verzögerter Fake-Provider, Fragment-/Finish-/Fehlerfälle, alte Retry-/Tooltests, echte LM-Studio/WPF-Probe. Zuerst sinnvolle Regressionen, dann fokussierte Tests. Parent führt finale Python-Vollsuite und C#-Builds gemäß tatsächlich betroffenen Bereichen sowie sichtbare Live-QC aus. Test- und Live-Belege getrennt mit Laufzeit, Versionen und Resultaten speichern.

## Risiken und Rückkehrpfad
Unvollständige Consumer-Inventare, Nebenläufigkeit und Wire-Compatibility explizit prüfen. Änderungen in klaren Feature-Diffs reviewen; keine Produktionsdatenmigration. Bei Livefehlern Originalkonfiguration/Runtime geordnet wiederherstellen, Fehlerbeleg erhalten und Gate offen lassen. Rollback bedeutet gezielten Review des Feature-Diffs, niemals blindes Reset fremder Änderungen.

## Fertigstellung
Tasks erst nach belegter Umsetzung abhaken. .completed erst nach vollständiger Implementation, qc-report.md und .qc-passed erst nach bestandener tatsächlicher QC. Brain-Log durch Parent aktualisieren.

