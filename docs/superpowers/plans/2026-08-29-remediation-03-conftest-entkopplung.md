# conftest-Entkopplung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Testinfrastruktur darf nicht länger diktieren, ob `clear_project_state()` werfen darf.

**Architecture:** `Tests/conftest.py` ruft `clear_project_state()` in einer `autouse`-Fixture ungeschützt in Setup **und** Teardown. Jeder der ~1540 Tests läuft dadurch zweimal durch diese Funktion. Solange das so ist, verwandelt jeder Wurf aus dem Produktionscode die gesamte Suite in Fixture-Errors — die Funktion ist damit dauerhaft auf „melden statt werfen" festgenagelt, unabhängig davon, was fachlich richtig wäre. Der Plan kapselt beide Aufrufe in eine Hilfsfunktion, die Fehler sichtbar meldet ohne die Suite zu reißen, und sichert die Entkopplung mit zwei Tests ab.

**Tech Stack:** pytest (autouse-Fixture), `backend/_brain_singleton.py`, `ast` für den Wiring-Guard.

---

## Vorbedingungen — am Quelltext verifiziert

Gegen HEAD (`ddc4187`) geprüft. Prüfe selbst nach, bevor du änderst.

| Fakt | Beleg |
|---|---|
| `isolated_test_database` ist `autouse=True` und läuft damit vor **jedem** Test | `Tests/conftest.py:82-83` |
| `clear_project_state()` wird ungeschützt gerufen — Setup **und** Teardown | `Tests/conftest.py:109-110` und `:122-123` |
| Der Import ist bereits defensiv (`except ImportError` → `clear_project_state = None`) | `Tests/conftest.py:88-91` |
| `clear_project_state()` wirft heute nicht; sie loggt und löst fail-closed über `force_unbind_project_state()` | `backend/_brain_singleton.py:74-99` |
| Produktions-Aufrufer ist genau einer: `close_project` | `backend/routers/project_router.py:901/904` |
| Der Router prüft danach eigenständig `current_project_state_identity()` und wirft HTTP 500 | `project_router.py:905` |
| `Tests/test_project_close_anchor_contracts.py:33` patcht `clear_project_state` zum Werfen und prüft den 500-Pfad | dort |

**Randbedingungen:**
- Interpreter `.venv/Scripts/python.exe`, immer `PYTHONPATH=src`.
- pytest **immer** mit eigenem `--basetemp=.pytest_tmp_t03x`. `--basetemp` nie aus `pytest.ini` entfernen.
- ~25 fremde uncommittete `patch.py`-Änderungen im Baum: nicht anfassen.
- Commit-Message per Bash-Heredoc mit `git commit -F -`.

## Was dieser Plan bewusst NICHT tut

Er ändert **nicht**, ob `clear_project_state()` wirft. Diese fachliche Entscheidung bleibt offen und gehört in einen eigenen Vorgang. Dieser Plan entfernt nur die Fessel, die eine solche Entscheidung heute unmöglich macht. Das ist Absicht: eine Verhaltensänderung im Produktionscode und die Entkopplung der Testinfrastruktur in einem Schritt zu vermischen, macht beide schwer zu bewerten.

## File Structure

| Datei | Verantwortung | Änderung |
|---|---|---|
| `Tests/conftest.py` | Testisolation für alle Tests | Hilfsfunktion `_reset_brain_project_state(phase)`, beide Aufrufstellen darüber |
| `Tests/test_conftest_brain_reset_is_decoupled.py` | Beweist Verhalten **und** Verdrahtung der Hilfsfunktion | neu |

---

## Task 1: Aufrufe kapseln und Entkopplung absichern

**Files:**
- Create: `Tests/test_conftest_brain_reset_is_decoupled.py`
- Modify: `Tests/conftest.py` (Hilfsfunktion oberhalb der Fixture, Aufrufstellen `:109-110` und `:122-123`)

- [ ] **Step 1: Write the failing test**

Create `Tests/test_conftest_brain_reset_is_decoupled.py`:

```python
"""Die Testinfrastruktur darf das Produktionsverhalten nicht diktieren.

Audit 2026-08-29: conftest.isolated_test_database ist autouse und ruft
clear_project_state() ungeschuetzt in Setup und Teardown. Jeder Wurf aus dem
Produktionscode wuerde damit ~1540 Tests in Fixture-Errors verwandeln - die
Funktion ist dauerhaft auf "melden statt werfen" festgenagelt, egal was
fachlich richtig waere.

Zwei Zusicherungen:
1. Verhalten - die Kapselung schluckt den Wurf und meldet ihn.
2. Verdrahtung - die Fixture ruft clear_project_state NICHT mehr direkt.
"""

import ast
import importlib
import logging
import pathlib

import pytest

conftest = importlib.import_module("conftest")

CONFTEST_PATH = pathlib.Path(__file__).resolve().parent / "conftest.py"


class TestResetHelperBehaviour:
    def test_helper_survives_a_raising_clear_project_state(self, monkeypatch, caplog):
        """Ein Wurf darf die Suite nicht reissen - aber er muss im Log stehen."""
        from backend import _brain_singleton

        def _explode() -> None:
            raise RuntimeError("unbind kaputt")

        monkeypatch.setattr(_brain_singleton, "clear_project_state", _explode)
        monkeypatch.setattr(conftest, "clear_project_state", _explode, raising=False)

        with caplog.at_level(logging.WARNING):
            conftest._reset_brain_project_state("Setup")

        assert any(
            record.levelno >= logging.WARNING and "clear_project_state" in record.message
            for record in caplog.records
        ), "Der verschluckte Wurf wurde nicht gemeldet"

    def test_helper_is_a_no_op_when_the_import_failed(self, monkeypatch):
        """Der bestehende ImportError-Pfad bleibt erhalten."""
        monkeypatch.setattr(conftest, "clear_project_state", None, raising=False)
        conftest._reset_brain_project_state("Teardown")


class TestResetHelperWiring:
    def test_fixture_does_not_call_clear_project_state_directly(self):
        """Wiring-Guard: die Fixture muss ueber die Kapselung gehen.

        Grenze dieses Guards, damit sie benannt ist: er prueft den Quelltext,
        nicht die Laufzeit. Wer den Aufruf in einen nie erreichten Zweig legt,
        bleibt gruen.
        """
        tree = ast.parse(CONFTEST_PATH.read_text(encoding="utf-8"))

        fixture = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "isolated_test_database"
            ),
            None,
        )
        assert fixture is not None, "Fixture isolated_test_database nicht gefunden"

        called = {
            node.func.id
            for node in ast.walk(fixture)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "clear_project_state" not in called, (
            "isolated_test_database ruft clear_project_state direkt - damit "
            "diktiert die Testinfrastruktur wieder, ob die Funktion werfen darf"
        )
        assert "_reset_brain_project_state" in called, (
            "die Fixture geht nicht ueber _reset_brain_project_state"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_conftest_brain_reset_is_decoupled.py -v --basetemp=.pytest_tmp_t03x`

Expected:
- `test_helper_survives_a_raising_clear_project_state` und `test_helper_is_a_no_op_when_the_import_failed` FAIL mit `AttributeError: module 'conftest' has no attribute '_reset_brain_project_state'`
- `test_fixture_does_not_call_clear_project_state_directly` FAIL mit `isolated_test_database ruft clear_project_state direkt`

Notiere die exakte Ausgabe. **Falls `importlib.import_module("conftest")` nicht auflöst** (Rootdir-Auflösung), melde es und nutze stattdessen `pytest.importorskip` oder den Pfadimport über `importlib.util` — aber schwäche die Zusicherungen nicht ab.

- [ ] **Step 3: Add the helper**

In `Tests/conftest.py`, **oberhalb** der Fixture `isolated_test_database` (also vor Zeile 82) einfügen:

```python
def _reset_brain_project_state(phase: str) -> None:
    """Brain-State zwischen Tests loesen, ohne dass die Suite am Verhalten des
    Produktionscodes haengt.

    Audit 2026-08-29: isolated_test_database ist autouse und rief
    clear_project_state() ungeschuetzt in Setup UND Teardown. Solange das so
    war, konnte clear_project_state niemals zu einem Re-Raise weiterentwickelt
    werden - ein Wurf haette jeden der ~1540 Tests in einen Fixture-Error
    verwandelt statt in eine aussagekraeftige Testmeldung. Die
    Testinfrastruktur diktierte damit das Produktionsverhalten.

    Der Fehlschlag wird gemeldet, nicht geschluckt: eine unvollstaendige
    Testisolation ist ein Befund, kein Grund den Lauf abzubrechen.
    """
    if clear_project_state is None:
        return
    try:
        clear_project_state()
    except Exception:
        logging.getLogger(__name__).warning(
            "clear_project_state() hat im %s geworfen - die Testisolation ist "
            "moeglicherweise unvollstaendig",
            phase,
            exc_info=True,
        )
```

Der Import von `clear_project_state` liegt heute **innerhalb** der Fixture (`conftest.py:88-91`). Zieh ihn auf Modulebene, damit die Hilfsfunktion ihn sieht — an den Anfang der Datei, zu den übrigen Modulimporten:

```python
import logging

try:
    from backend._brain_singleton import clear_project_state
except ImportError:
    clear_project_state = None
```

Entferne den nun doppelten `try/except ImportError`-Block **innerhalb** der Fixture (`conftest.py:88-91`).

**Prüfe vorher**, ob `import logging` in `conftest.py` bereits vorhanden ist — dann nicht doppelt hinzufügen. Und prüfe, ob der Import auf Modulebene nicht einen Zyklus erzeugt: `backend._brain_singleton` importiert `pb_studio.brain.brain_service`, das beim Sammeln der Tests ohnehin geladen wird. Falls doch ein Problem auftritt, melde es, statt den Import wieder in die Funktion zu schieben — dann gehört die Hilfsfunktion selbst zum lazy Import umgebaut.

- [ ] **Step 4: Route both call sites through the helper**

In `Tests/conftest.py` beide Stellen ersetzen.

Setup (heute `:109-110`):

```python
    if clear_project_state:
        clear_project_state()
```

wird zu:

```python
    _reset_brain_project_state("Setup")
```

Teardown (heute `:122-123`), identischer Ersatz:

```python
    _reset_brain_project_state("Teardown")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_conftest_brain_reset_is_decoupled.py -v --basetemp=.pytest_tmp_t03x`

Expected: 3 passed.

- [ ] **Step 6: Beweise die Entkopplung am echten Produktionscode**

Das ist der eigentliche Zweck des Plans und mehr wert als die drei Unit-Tests. Patche `clear_project_state` **temporär** zum Werfen und lass einen breiten Ausschnitt der Suite laufen.

Ändere `backend/_brain_singleton.py` testweise so, dass `clear_project_state` als erste Zeile `raise RuntimeError("Entkopplungsprobe")` ausführt. Dann:

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_app_state.py Tests/test_project_persistence.py Tests/test_timeline_survives_project_switch.py -q --basetemp=.pytest_tmp_t03x`

Expected: **passed**, mit Warnungen im Log — **keine** Fixture-Errors.

Stelle `backend/_brain_singleton.py` danach **byte-exakt** wieder her und weise das mit `git diff backend/_brain_singleton.py` (leer) nach. Berichte beide Ausgaben.

Gegenprobe zur Gegenprobe: derselbe Lauf **vor** deiner Änderung hätte Fixture-Errors erzeugt. Wenn du das zeigen willst, mach es auf einem `git stash`-freien Weg über einen Wegwerf-Worktree — nicht durch weitere Änderungen am Arbeitsbaum, in dem 25 fremde Dateien liegen.

- [ ] **Step 7: Regression**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_silent_persistence_failures.py Tests/test_project_close_anchor_contracts.py Tests/test_project_brain_binding.py Tests/test_conftest_brain_reset_is_decoupled.py -q --basetemp=.pytest_tmp_t03x`

Expected: alle passed. `test_project_close_anchor_contracts.py` ist der wichtigste hier — er patcht `clear_project_state` selbst zum Werfen und prüft den HTTP-500-Pfad des Routers. Dieser Vertrag muss unverändert gelten.

- [ ] **Step 8: Commit**

```bash
git add Tests/conftest.py Tests/test_conftest_brain_reset_is_decoupled.py
git commit -F - <<'EOF'
fix(tests): conftest diktiert nicht mehr, ob clear_project_state werfen darf

isolated_test_database ist autouse und rief clear_project_state() ungeschuetzt
in Setup und Teardown. Jeder der ~1540 Tests lief zweimal durch diese Funktion.
Solange das so war, haette jeder Wurf aus dem Produktionscode die gesamte Suite
in Fixture-Errors verwandelt - die Funktion war damit dauerhaft auf "melden
statt werfen" festgenagelt, unabhaengig davon was fachlich richtig ist.

Beide Aufrufe gehen jetzt ueber _reset_brain_project_state(phase), die den
Fehlschlag mit exc_info meldet, ohne den Lauf zu reissen. Der Import wandert
auf Modulebene, der doppelte ImportError-Block in der Fixture entfaellt.

Abgesichert durch drei Tests: Verhalten bei Wurf, No-Op-Pfad bei fehlendem
Import, und ein AST-Wiring-Guard, dass die Fixture nicht wieder direkt ruft.
Der Wiring-Guard prueft den Quelltext, nicht die Laufzeit - diese Grenze steht
im Test.

Bewusst NICHT geaendert: ob clear_project_state wirft. Das ist eine fachliche
Entscheidung und gehoert in einen eigenen Vorgang. Dieser Commit entfernt nur
die Fessel, die sie heute unmoeglich macht.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Abschluss

- [ ] **Vollsuite sequenziell:** `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/ -q --basetemp=.pytest_tmp_final04`
      Erwartung: **7 failed / 1526+ passed / 0 errors**, keine neuen Fehler. Während des Laufs keine Datei ändern.
- [ ] **Roadmap nachziehen:** Folgepunkt „`conftest.py` ruft `clear_project_state()` ungeschützt" abhaken und den Nachfolgevorgang notieren: *entscheiden, ob `clear_project_state` bei gescheitertem Fail-closed werfen soll*.
- [ ] **Obsidian-Vault:** `INDEX.md` und `log.md` ergänzen.
- [ ] **Push** und Remote-SHA verifizieren.

## Offene Anschlussfrage

Nach diesem Plan ist die Entscheidung frei — getroffen ist sie nicht. Für den Nachfolgevorgang die Ausgangslage:

- `clear_project_state()` meldet heute und löst fail-closed über `force_unbind_project_state()`. Der Rückgabewert `False` (Lock-Timeout, Verbindung bleibt offen) führt zu einem `logger.critical`, aber zu keinem Wurf.
- `close_project` prüft danach eigenständig `current_project_state_identity()` und wirft HTTP 500, wenn noch eine Bindung besteht. Der Nutzer bekommt also bereits ein Signal — außer im Timeout-Fall, in dem die Bindung gelöst, die Verbindung aber offen ist.
- Genau diese Lücke wäre der Kandidat für einen Wurf.
