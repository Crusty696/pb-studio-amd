# T410 — Projektwechsel-E2E

Status: PASS
Datum: 2026-08-01
Ausgangs-SHA: `72d1bc67cc6ab85cf2e14dc4fb18624d7effdaaa`
Geprüfter Diff-Blob: `49b7da12d45dab5ab6642c2231699536f2e25bb8`

## Geschlossene Abweichungen

- Audio-Analyse, Audio-Stems und Audio-Löschpfade publizieren verspätete Fehler oder Abschlusszustände nur im erfassten Projektkontext.
- KI-Regie publiziert verspätete Pacing-Fehler nur im erfassten Projektkontext.
- Brain invalidiert laufende Feedback-, Statistik- und Learning-Anfragen bereits beim Start des Projektwechsels; Antworten aus A können B nicht überschreiben.

## Backend- und Persistenzbeleg

- 5/5 PASS: öffentliche Handler für Audio, Video, Pacing, Timeline und Brain werden in A bis an eine deterministische Worker-Barriere geführt und durch die reale `_activate_project()`-Sequenz nach B gewechselt.
- Nach Worker-Freigabe bleiben der vollständige B-AppState, die zentrale SQLite-Datenbank, die logische B-`state.db` und alle Nicht-SQLite-Projektdateien exakt unverändert.
- Brain nutzt reale A-/B-SQLite-Datenbanken, einen realen `BrainService`, echten Rebind, eine reale A-Lease und weist deren `run_write()` nach dem Wechsel als stale zurück.
- Alle Barrieren und Waits sind auf 3–3,5 Sekunden begrenzt; keine Retries oder unbeschränkten Schleifen.

## UI-Beleg

- 5/5 PASS: Audio, Video, KI-Regie, Timeline und Brain starten eine Operation in A und führen danach den echten `ProjectService.OpenProjectAsync(A→B)` aus.
- Jeder Lauf bestätigt `ProjectClosing → ProjectClosed → ProjectOpened` sowie das aktive B-Projekt.
- Späte A-Fehler oder A-Ergebnisse überschreiben weder B-Status noch B-gebundene UI-Werte.

## Autoritative Belege

- `T410-project-switch-e2e/T410-python-all-five-final.xml` — 5/5 PASS, SHA-256 `DC83E7BD2A88A270F4E1FF690B4FAF143358D2A2AAF3B8E2A56D3FBF646A418E`.
- `T410-project-switch-e2e/T410-ui-real-switch-final.trx` — 5/5 PASS, SHA-256 `369EAA3CD6E4C9BFB783C741BB67F16C34E57B7565006E9AD890B7A98E4147CE`.
- `T410-project-switch-e2e/receipt.json` — Runtime-, Quell- und Beleg-Hashes.
- Ein früher nativer Start erreichte wegen der noch laufenden T408-Release-App keinen Test; nach Beenden der eigenen PID 17660 ist der autoritative Lauf ohne Warnung oder Fehler bestanden.

## Unabhängiger Review

PASS: Alle fünf öffentlichen Backend-Pfade, realer Brain-Rebind/Lease-Retirement, vollständige B-Canaries, alle fünf UI-Pfade und der reale A→B-Lifecycle sind abgedeckt.
