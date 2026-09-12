# Echter Chat-Tokenstream bis WPF

**Status:** SPECIFIED, 2026-09-07. **Quelle:** Nutzerauftrag Punkt 14; specs/00023-backlog-completion.

## Ziel und Geltungsbereich
Den genannten Backlogpunkt vollständig im realen App-Pfad schließen. Die folgenden Designentscheidungen sind Vorschläge dieser Spezifikation, keine behaupteten früheren Beschlüsse. Keine Implementations- oder Live-Abnahme wird hier behauptet.

## Befund
`src/pb_studio/ai/chat_agent.py` ruft `self._llm.chat` auf und liefert vollständige `text`-Events. `lmstudio_client.py::chat_stream` existiert, vermischt aber `reasoning_content` mit `content` und aggregiert Toolfragmente. Bestehende Retry-, Projektbindung- und Bestätigungsgates müssen erhalten bleiben.
## Anforderungen
- FR-001: ChatAgent konsumiert den echten Providerstream und liefert Textdeltas vor Ende der Providerantwort. WPF ergänzt dieselbe Assistant-Nachricht schrittweise; kein nachträgliches Zerlegen fertiger Antworten.
- FR-002: Provider-Reasoning bleibt ein separater interner Kanal und erscheint weder als Antworttext noch als persistierte Benutzerantwort. Abschlussinhalt entspricht exakt der Verkettung akzeptierter Content-Deltas.
- FR-003: Tool-Call-ID, Name und JSON-Argumente über alle Fragmente pro Index vollständig assemblieren; parallele Calls bleiben getrennt. Dispatch erst nach gültigem terminalem Finish, JSON-Validierung und bestehenden Bestätigungs-/Projektgates; höchstens einmal.
- FR-004: Vor erstem veröffentlichtem Content darf bestehende begrenzte Provider-Fallbackkette greifen. Nach veröffentlichtem Content beendet ein Providerfehler den Versuch explizit als unvollständig; kein stilles Anhängen eines zweiten Versuchs. Expliziter Nutzer-Retry erzeugt eine neue Antwort.
- FR-005: Cancel, Timeout, Disconnect und Projektwechsel schließen Providerstream und bestätigen keine unvollständigen Tools. Genau ein terminales Event je normal abgeschlossenem SSE-Generator; doppelte Finish-/DONE-Signale duplizieren weder History noch Tools.
- FR-006: Abschluss-`text`/History und Deltapfad bleiben kompatibel: UI darf final_text nicht nochmals anhängen. Fehlerhafte SSE/EOF ohne Finish gilt als Fehler, nicht erfolgreicher leerer Abschluss.
- TR-001: Bestehende Request-/Tool-Timeouts und Modellstatus bleiben wirksam. WPF-Dispatcher bündelt Updates zeitlich, ohne Inhalt zu verlieren.
## Abnahme
Kontrollierter verzögerter SSE-Provider beweist frühes Delta; fragmentierte Tools, getrenntes Reasoning, UTF-8, Doppel-Finish, abruptes EOF, Cancel und Retry geprüft. Reales LM-Studio-Modell zeigt mindestens zwei sichtbare Textupdates vor Finish; Tool-Ausführung und Projektwechsel mit echtem Backend geprüft.

## Gates
Getrenntes Feature gemäß specs/00020-obj75-open-bug-fixes/residual-remediation-plan.md. Dessen OBJ-75-Release-Vorbedingung vor Implementierung anhand aktueller Marker prüfen; fehlendes Gate explizit beim Parent behandeln. Spec → Plan → Tasks → Implement → QC. Keine .completed/.qc-passed ohne reale Belege. Python 3.11/NumPy 1.26.4, DirectML/AMF und bestehende Recovery-Grenzen gelten.
