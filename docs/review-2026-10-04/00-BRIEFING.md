# Team-Briefing: Read-only Voll-Review PB Studio (2026-10-04)

Repo: `C:\Users\david\Documents\Pb_studio_AMD_version` · Branch `codex/full-audit-remediation` · HEAD `e51e798`
Auftrag des Nutzers: Projekt reviewen, toten Code und Redundanz finden, Refactoring vorbereiten.
**In dieser Phase wird NICHTS am Code geändert.** Jede Datei, jede Zeile prüfen. Keine Annahmen.

Du bist Reviewer für genau eine Zone. Der Teamleiter fügt alle Zonenberichte zusammen.

## Harte Regeln

1. **Keine Änderung an bestehenden Dateien.** Einzige erlaubte Schreibaktion: dein Zonenbericht
   unter `docs/review-2026-10-04/` (Dateiname steht in deinem Auftrag).
2. **Nicht ausführen:** pytest, uvicorn, Backend-/App-Start, `import backend.main` (auch nicht per
   `python -c`), `dotnet build/test/run`, Launcher/.bat/.ps1 des Projekts, Installationen,
   git-Schreibbefehle (add/commit/checkout/stash/reset/clean), Löschen/Verschieben von Dateien.
   Grund: Der Import von `backend.main` fasst echte Recovery-Daten unter `%LOCALAPPDATA%\PB_Studio`
   an und hat bereits einmal einen Daten-Rollback ausgelöst.
3. **Erlaubt:** Read, Grep, Glob, `git ls-files`, `git log`, `git grep`, `git blame` (read-only).
   Reiner Syntax-Check für Python nur so (schreibt nichts):
   `.venv\Scripts\python.exe -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" <datei>`
4. **Vollständig lesen.** Jede Datei deiner Zone von der ersten bis zur letzten Zeile; große Dateien
   abschnittsweise mit `offset`/`limit`. Nicht überfliegen, nicht aus Dateinamen schließen.
5. **Keine Annahmen.** „Tot / unbenutzt / redundant" nur mit Beleg: repo-weites Grep über
   `src/`, `backend/`, `PBStudio.UI/`, `PBStudio.UI.Tests/`, `Tests/`, `scripts/`, Root-Skripte,
   `config/`. Auch indirekte Nutzung prüfen: String-Dispatch, `getattr`, `__all__`, FastAPI-Dekoratoren,
   Pydantic-Felder (→ OpenAPI → C#-Records), DI-Registrierung in `App.xaml.cs`, XAML-`{Binding}`,
   `RelayCommand`/`ObservableProperty`-Generatoren, Reflection in Tests, `config.json`-Schlüssel.
   Nur von Tests benutzt ≠ produktiv benutzt — getrennt ausweisen.
   Nicht verifizierbar → Schweregrad `UNBEKANNT`, nicht raten.
6. `src/pb_studio/audio/separator.py` ist **LOCKED** — nur dokumentieren.
7. Uncommittete Dateien (Spec 00036: `SSEClient.cs`, `TerminalLoggerProvider.cs`,
   `scripts/record_app_session.py`, `LOG-AUFZEICHNUNG.bat`, zwei neue Tests) gehören zum Stand und
   werden mitgeprüft, wenn sie in deiner Zone liegen.

## Wonach gesucht wird

1. **Toter Code:** unbenutzte Funktionen, Klassen, Methoden, Parameter, Imports, Variablen, Felder,
   Config-Schlüssel, Schema-Felder; unerreichbare Zweige; auskommentierter Code; Producer ohne
   Consumer und Consumer ohne Producer; Dateien ohne Aufrufer.
2. **Redundanz:** kopierte Logik, parallele Implementierungen derselben Sache, divergierende
   Parametersätze für dieselbe Berechnung, doppelte Konstanten, doppelte Hilfsfunktionen.
3. **Korrektheit:** Syntaxfehler, Typfehler, falsche Signaturen/Aufrufe, offensichtliche
   Laufzeitfehler, Off-by-one, falsche Einheiten/Zeitbasen.
4. **Einfachheit / Wartbarkeit:** Funktionen > 150 Zeilen, tiefe Verschachtelung, God-Files,
   verschluckte Exceptions (`except Exception: pass`, leere `catch`), magische Zahlen,
   irreführende Namen, veraltete Kommentare/Docstrings, die dem Code widersprechen.
5. **Stabilität:** Races, fehlende Locks, Ressourcenlecks (Dateien, Sessions, Prozesse, Tasks),
   fehlende Fehlerpfade, nicht abbrechbare Arbeit.
6. **Performance:** Mehrfachberechnung, N+1, blockierendes I/O im async-Pfad, unnötige Kopien
   großer Arrays, unnötiges Neuladen von Modellen/Dateien.
7. **Projektregeln:** kein CUDA/NVENC/pynvml/ROCm; jede DirectML-`SessionOptions` braucht
   `enable_mem_pattern = False` **und** `enable_cpu_mem_arena = False`; Encoder nur `*_amf`;
   NumPy < 2.0-Kompatibilität.

## Berichtsformat (Markdown, deutsch, knapp, keine Floskeln)

```
# Zone NN – <Name>
## Abdeckung
| Datei | Zeilen | vollständig gelesen |
## Befunde
### ZNN-001 · <SCHWEREGRAD> · <Kategorie> · <Kurztitel>
- Ort: `pfad/datei.py:123` (ggf. mehrere)
- Was: …
- Beleg: <Grep-Muster + Trefferzahl/Fundstellen bzw. zitierte Zeilen>
- Auswirkung: …
- Abhängigkeiten: wer ruft auf / wer liest / was bricht bei Änderung (Tests, C#-Records, XAML, OpenAPI-Snapshot, Skripte)
- Empfehlung: …
- Aufwand: S | M | L · Änderungsrisiko: niedrig | mittel | hoch
## Refactoring-Kandidaten (priorisiert)
## Nicht geprüft / Unsicherheiten
```

Schweregrade: `KRITISCH` (Crash, Datenverlust, Sicherheit) · `HOCH` (Kernfunktion falsch) ·
`MITTEL` (Nebenfunktion, Wartbarkeit stark belastet) · `NIEDRIG` (Stil, Kleinkram) ·
`UNBEKANNT` (nicht verifizierbar).

Ehrlichkeit vor Vollständigkeitsanschein: Was du nicht gelesen oder nicht belegen konntest, steht
unter „Nicht geprüft / Unsicherheiten". Kein Befund ohne Datei und Zeile.

## Schlussantwort an den Teamleiter (max. 15 Zeilen)

Dateien/Zeilen gelesen · Befunde je Schweregrad · Top-5-Befunde mit `datei:zeile` · Lücken.
