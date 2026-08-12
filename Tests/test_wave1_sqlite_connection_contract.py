from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUSY_TIMEOUT_MS = 5000

def _productive_connection_sources() -> tuple[str, ...]:
    discovered: list[str] = []
    for root_name in ("backend", "src"):
        for path in sorted((ROOT / root_name).rglob("*.py")):
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
            if any(
                isinstance(node, ast.Call) and _is_sqlite_connect(node)
                for node in ast.walk(tree)
            ):
                discovered.append(path.relative_to(ROOT).as_posix())
    return tuple(discovered)


def _is_sqlite_connect(call: ast.Call) -> bool:
    function = call.func
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id == "sqlite3"
        and function.attr == "connect"
    )


def _connection_is_initialized(lines: list[str], call: ast.Call) -> bool:
    start = max(call.end_lineno or call.lineno, call.lineno) - 1
    window = "\n".join(lines[start : start + 12])
    normalized = re.sub(r"\s+", "", window).lower()
    return (
        "init_connection(" in window
        or "_configure_connection(" in window
        or f"pragmabusy_timeout={BUSY_TIMEOUT_MS}" in normalized
    )


def test_every_productive_sqlite_factory_applies_the_common_timeout_after_open():
    offenders: list[str] = []
    sources = _productive_connection_sources()
    assert len(sources) >= 13, "SQLite connection inventory unexpectedly shrank"
    for relative in sources:
        path = ROOT / relative
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and _is_sqlite_connect(node)]
        assert calls, f"SQLite connection inventory source has no factory: {relative}"
        for call in calls:
            if not _connection_is_initialized(lines, call):
                offenders.append(f"{relative}:{call.lineno}")

    assert offenders == [], (
        "Every productive sqlite3.connect must immediately use init_connection "
        f"or PRAGMA busy_timeout={BUSY_TIMEOUT_MS}; offenders: {offenders}"
    )


def test_common_initializer_and_database_core_use_exactly_5000_ms():
    initializer = (ROOT / "src/pb_studio/storage/sqlite_init.py").read_text(encoding="utf-8-sig")
    database_core = (ROOT / "src/pb_studio/data/database_core.py").read_text(encoding="utf-8-sig")
    normalized_initializer = re.sub(r"\s+", "", initializer).lower()
    normalized_database = re.sub(r"\s+", "", database_core).lower()

    assert f"pragmabusy_timeout={BUSY_TIMEOUT_MS}" in normalized_initializer
    assert f"pragmabusy_timeout={BUSY_TIMEOUT_MS}" in normalized_database
    assert "busy_timeout=30000" not in normalized_database
