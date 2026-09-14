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
| `clear_project_state()` wird **ohne `try/except`** gerufen — Setup **und** Teardown. Ein `None`-Guard existiert sehr wohl und muss erhalten bleiben | `Tests/conftest.py:109-110` und `:122-123` |
| Der Import ist bereits defensiv (`except ImportError` → `clear_project_state = None`) | `Tests/conftest.py:88-91` |
| `clear_project_state()` wirft heute nicht; sie loggt und löst fail-closed über `force_unbind_project_state()` (Aufruf auf `:108`) | `backend/_brain_singleton.py:74-122` |
| Produktions-Aufrufer ist genau einer: `close_project` | `backend/routers/project_router.py:904` (funktionslokaler Import `:901`) |
| Der Router prüft danach `current_project_state_identity()` und wirft dort `RuntimeError`, der auf `:907` gefangen und auf `:913` in `HTTPException(500)` übersetzt wird | `project_router.py:905`, `:913` |
| `import logging` fehlt in `conftest.py` — Modulimporte sind heute `os, httpx, pytest, tempfile, json, pathlib.Path, unittest.mock` | `Tests/conftest.py:11-18` |
| `conftest.py:22` setzt `os.environ["PBSTUDIO_OWNER_CAPABILITY"]` auf Modulebene | `Tests/conftest.py:22` |
| Die Suite sammelt **1552** Tests | `pytest Tests/ --collect-only` |

**Experimentell belegt (Wegwerf-Verzeichnis außerhalb des Repos):** eine autouse-Fixture, die im Setup wirft, erzeugt `ERROR at setup` für **jeden** Test — **0 Tests werden ausgeführt**. Wirft sie im Teardown, kommt zu jedem bestandenen Test ein `ERROR at teardown`. Da die heutige Fixture in **beiden** Phasen ruft, ergäbe ein Wurf aus `clear_project_state()` **1552 Setup-Errors bei 0 ausgeführten Tests**. Die Kernbehauptung ist damit gemessen, nicht plausibilisiert.

**Ebenfalls belegt — kein Importzyklus, keine DB-Berührung:** ein instrumentierter Frischimport von `backend._brain_singleton` ruft `sqlite3.connect` **null Mal**; `ConfigManager._instance` und `BrainService._instance` bleiben `None`. Die naheliegende Sorge (der Modulebenen-Import fasst die produktive DB an, bevor `conftest` sie umbiegt) ist **widerlegt**. Er zieht allerdings torch, librosa, cv2 und matplotlib mit — **2379 Module** — und verschiebt diese Kosten auf die conftest-Importzeit. Funktional harmlos, erwähnenswert.
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
        """Ein Wurf darf die Suite nicht reissen - aber er muss sichtbar sein.

        Der Patch geht auf das conftest-Modul-Global: die Hilfsfunktion loest
        den Namen ueber conftest.__dict__ auf. Ein Patch auf _brain_singleton
        waere hier wirkungslos.
        """

        def _explode() -> None:
            raise RuntimeError("unbind kaputt")

        monkeypatch.setattr(conftest, "clear_project_state", _explode)

        with caplog.at_level(logging.WARNING):
            with pytest.warns(conftest.BrainResetFailure):
                conftest._reset_brain_project_state("Setup")

        assert any(
            record.levelno >= logging.WARNING and "clear_project_state" in record.message
            for record in caplog.records
        ), "Der verschluckte Wurf wurde nicht ins Log geschrieben"

    def test_helper_is_a_no_op_when_the_import_failed(self, monkeypatch):
        """Der bestehende ImportError-Pfad bleibt erhalten.

        Kein raising=False: nach der Aenderung ist clear_project_state ein
        Modul-Global von conftest. Die strikte Form faengt einen Tippfehler
        im Attributnamen, die nachsichtige verdeckt ihn.
        """
        monkeypatch.setattr(conftest, "clear_project_state", None)
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

Notiere die exakte Ausgabe.

`importlib.import_module("conftest")` löst in diesem Repo auf — verifiziert: `Tests/` liegt in `sys.path` (kein `Tests/__init__.py`, importmode `prepend`), und es gibt genau **eine** `conftest.py` im Repo, also keine Namenskollision. Ein Fallback ist nicht nötig.

- [ ] **Step 3: Add the helper**

In `Tests/conftest.py`, **oberhalb** der Fixture `isolated_test_database` (also vor Zeile 82) einfügen:

```python
class BrainResetFailure(RuntimeWarning):
    """Der Brain-State konnte zwischen zwei Tests nicht geloest werden."""


def _reset_brain_project_state(phase: str) -> None:
    """Brain-State zwischen Tests loesen, ohne dass die Suite am Verhalten des
    Produktionscodes haengt.

    Audit 2026-08-29: isolated_test_database ist autouse und rief
    clear_project_state() ohne try/except in Setup UND Teardown. Solange das so
    war, konnte clear_project_state niemals zu einem Re-Raise weiterentwickelt
    werden - gemessen: ein Wurf im Setup erzeugt 1552 Fixture-Errors bei
    0 ausgefuehrten Tests. Die Testinfrastruktur diktierte das
    Produktionsverhalten.

    Der Fehlschlag wird gemeldet, nicht geschluckt. Die Logzeile allein
    genuegt dafuer NICHT: pytest.ini setzt weder log_cli noch log_file, und
    pytest zeigt den Captured-log-Abschnitt nur bei fehlschlagenden Tests - in
    einem gruenen Lauf waere sie unsichtbar. Erst warnings.warn taucht im
    warnings summary jedes Laufs auf. Ohne diese zweite Meldung waere die
    Kapselung eine Verschlechterung: sie wuerde eine laute Fehlerwand gegen
    stilles Schlucken tauschen und eine kaputte Testisolation unbemerkt
    gruen durchlaufen lassen.
    """
    if clear_project_state is None:
        return
    try:
        clear_project_state()
    except Exception as exc:
        logging.getLogger("conftest").warning(
            "clear_project_state() hat im %s geworfen - die Testisolation ist "
            "moeglicherweise unvollstaendig",
            phase,
            exc_info=True,
        )
        warnings.warn(
            f"clear_project_state() hat im {phase} geworfen ({exc!r}) - "
            "die Testisolation ist moeglicherweise unvollstaendig",
            BrainResetFailure,
            stacklevel=2,
        )
```

Der Import von `clear_project_state` liegt heute **innerhalb** der Fixture (`conftest.py:88-91`). Zieh ihn auf Modulebene, damit die Hilfsfunktion ihn sieht.

`import logging` und `import warnings` fehlen beide (Modulimporte heute: `conftest.py:11-18`) und sind zu den übrigen zu ergänzen.

**Position des `_brain_singleton`-Imports: unterhalb von `conftest.py:22`**, wo `os.environ["PBSTUDIO_OWNER_CAPABILITY"]` gesetzt wird — **nicht** am Dateianfang. Heute liest zwar nichts in der Importkette diese Variable, der Import wäre also zufällig unschädlich; die Reihenfolge trotzdem festschreiben, statt sich auf den Zufall zu verlassen.

```python
try:
    from backend._brain_singleton import clear_project_state
except ImportError:
    clear_project_state = None
```

Entferne den nun doppelten `try/except ImportError`-Block **innerhalb** der Fixture (`conftest.py:88-91`).

Auf Zyklen musst du nicht mehr prüfen — das ist bereits belegt (siehe Vorbedingungen): kein Zyklus, `sqlite3.connect` wird beim Import null Mal gerufen, `ConfigManager._instance` und `BrainService._instance` bleiben `None`. Verändert sich das Verhalten der `except ImportError`-Klausel: ein **Nicht**-`ImportError` (etwa ein `OSError` aus einem torch-DLL-Fehler) reißt künftig die conftest beim Sammeln statt jeden Test einzeln. Lauter, kein Rückschritt.

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

Das ist der eigentliche Zweck des Plans und mehr wert als die drei Unit-Tests.

**Ändere dafür KEINE Datei im Repo.** Im Arbeitsbaum liegen 25 fremde uncommittete Änderungen; eine Produktionsdatei zu mutieren und auf die spätere Wiederherstellung zu vertrauen, ist dort ein unnötiges Risiko — bricht der Lauf ab (Ctrl-C, Timeout), bleibt die Mutation stehen, und ein `git checkout --` als Rettung wäre in diesem Baum gefährlich.

Nutze stattdessen ein pytest-Plugin im Scratchpad. Lege `<scratchpad>/probe_raise.py` an:

```python
"""Laesst clear_project_state werfen, ohne eine Repo-Datei anzufassen."""

import backend._brain_singleton as bs


def _explode() -> None:
    raise RuntimeError("Entkopplungsprobe")


bs.clear_project_state = _explode
```

Run (Semikolon als Pfadtrenner unter Windows):

```
PYTHONPATH="src;<scratchpad>" .venv/Scripts/python.exe -m pytest \
  Tests/test_app_state.py Tests/test_project_persistence.py \
  Tests/test_timeline_survives_project_switch.py \
  -p probe_raise -q --basetemp=.pytest_tmp_t03x
```

Expected: **passed**, mit `BrainResetFailure`-Einträgen im **warnings summary** — **keine** Fixture-Errors. Achte auf die Formulierung: „Warnungen im Log" wäre falsch, die Logzeile ist in einem grünen Lauf unsichtbar (siehe Step 3).

Das Plugin wird nachweislich **vor** dem conftest-Import geladen, der Modulebenen-Import in `conftest.py` bindet also die werfende Fassung.

**Auseinanderhalten beim Auswerten:** Tests, die selbst `close_project` erreichen, können am **Produktionspfad** scheitern (der Router wirft dann sein HTTP 500). Das wäre kein Fixture-Fehler und kein Widerspruch zu diesem Plan — aber es ist ein anderer Befund und gehört getrennt berichtet.

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
      **Keine Zahl vorregistrieren.** Miss die Grundlinie und berichte das Delta gegen den letzten dokumentierten Lauf (7 failed / 1522 passed / 13 skipped / 0 errors, Stand `ddc4187`). Entscheidend ist: **kein neuer Fehler**, und die Zunahme bei `passed` muss sich vollständig aus den neuen Tests erklären lassen. Während des Laufs keine Datei ändern — ein solcher Lauf musste in dieser Session schon einmal verworfen werden.
- [ ] **Roadmap nachziehen:** Folgepunkt „`conftest.py` ruft `clear_project_state()` ungeschützt" abhaken und den Nachfolgevorgang notieren: *entscheiden, ob `clear_project_state` bei gescheitertem Fail-closed werfen soll*.
- [ ] **Obsidian-Vault:** `INDEX.md` und `log.md` ergänzen. Bei einer Full-Sync-Direktive zusätzlich `MEMORY.md` und `CLAUDE.md §3` (Iron Rule 12).
- [ ] **Push** und Remote-SHA gegen lokal verifizieren.

## Offene Anschlussfrage

Nach diesem Plan ist die Entscheidung frei — getroffen ist sie nicht. Für den Nachfolgevorgang die Ausgangslage:

- `clear_project_state()` meldet heute und löst fail-closed über `force_unbind_project_state()`. Der Rückgabewert `False` (Lock-Timeout, Verbindung bleibt offen) führt zu einem `logger.critical`, aber zu keinem Wurf.
- `close_project` prüft danach eigenständig `current_project_state_identity()` und wirft HTTP 500, wenn noch eine Bindung besteht. Der Nutzer bekommt also bereits ein Signal — außer im Timeout-Fall, in dem die Bindung gelöst, die Verbindung aber offen ist.
- Genau diese Lücke wäre der Kandidat für einen Wurf.
