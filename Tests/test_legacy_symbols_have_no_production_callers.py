"""Als LEGACY gekennzeichnete Symbole duerfen keinen Produktionsaufrufer bekommen.

Zustandsaufnahme 2026-08-30 (E-3): mehrere Einheiten haben null
Produktions-Aufrufer, sind aber teils durch Tests geschuetzt und in der
Architekturdokumentation als aktiv beschrieben. Entscheidung des
Projektinhabers: erst kennzeichnen, spaeter loeschen.

Dieser Waechter haelt den Zustand fest. Er ist bewusst SYMBOLGENAU und nicht
modulweit: `SmartDirector` etwa ist LEBENDIG - `clip_selector._get_text_embedding`
(erreichbar ueber `select_clip`) holt darueber den SigLIP-Text-Encoder. Tot ist
allein seine `generate_timeline`-Orchestrierung.

Der Scan arbeitet ueber den AST und zaehlt nur echte Namens- und
Attributzugriffe. Erwaehnungen in Kommentaren und Docstrings zaehlen nicht -
`VideoGenerator` kommt in `advanced_pacing_engine` 13-mal in Prosa vor und
kein einziges Mal als Aufruf.

Wird eine Einheit reaktiviert, gehoert ihr Eintrag hier entfernt - und mit ihm
der LEGACY-Vermerk im Modul. Wird sie geloescht, ebenfalls.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# symbol -> (definierendes Modul, Begruendung)
LEGACY_SYMBOLS: dict[str, tuple[str, str]] = {
    "AnalysisService": (
        "src/pb_studio/services/analysis_service.py",
        "PyQt-Ära; einziger Importeur ist ui_legacy_archived",
    ),
    "GenerationService": (
        "src/pb_studio/services/generation_service.py",
        "PyQt-Ära; haelt als einzige den SyncMode-Planer und VideoGenerator am Leben",
    ),
    "MediaService": (
        "src/pb_studio/services/media_service.py",
        "PyQt-Ära; einziger Importeur ist ui_legacy_archived",
    ),
    "VideoGenerator": (
        "src/pb_studio/video/engine.py",
        "nur von GenerationService instanziiert; der reale Renderpfad ist RenderService",
    ),
    "VRAMArbiter": (
        "src/pb_studio/core/vram_arbiter.py",
        "0 Produktionsaufrufer; vram_budget_manager.py:364 haelt das im Kommentar fest",
    ),
    "VideoEmbedder": (
        "src/pb_studio/video/video_embedder.py",
        "abgeloest durch den registrierten SigLIP-ONNX-Pfad; nur die Konstanten werden gelesen",
    ),
    "get_video_embedder": (
        "src/pb_studio/video/video_embedder.py",
        "Zugang zum abgeloesten VideoEmbedder",
    ),
}

PRODUCTION_DIRS = ("src/pb_studio", "backend")
EXCLUDED_PARTS = ("ui_legacy_archived", "__pycache__", "archive")


def _production_files() -> list[Path]:
    out: list[Path] = []
    for rel in PRODUCTION_DIRS:
        for path in (ROOT / rel).rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            out.append(path)
    return out


def _referenced_names(path: Path) -> set[str]:
    """Nur echte Namens-/Attributzugriffe - keine Prosa."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - defensiv
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
    return names


@pytest.mark.parametrize("symbol", sorted(LEGACY_SYMBOLS))
def test_legacy_symbol_has_no_production_caller(symbol: str) -> None:
    owner, reason = LEGACY_SYMBOLS[symbol]
    owner_path = (ROOT / owner).resolve()
    assert owner_path.exists(), f"Definierendes Modul fehlt: {owner}"

    # Verweise ZWISCHEN Legacy-Modulen zaehlen nicht: GenerationService
    # instanziiert VideoGenerator, ist aber selbst tot. Beide verschwinden
    # gemeinsam oder gar nicht.
    legacy_owners = {
        (ROOT / owner_rel).resolve()
        for owner_rel, _ in LEGACY_SYMBOLS.values()
    }

    callers: list[str] = []
    for path in _production_files():
        if path.resolve() in legacy_owners:
            continue
        # Der Re-Export in einem Paket-__init__ ist kein Aufrufer.
        if path.name == "__init__.py":
            continue
        if symbol in _referenced_names(path):
            callers.append(str(path.relative_to(ROOT)))

    assert not callers, (
        f"{symbol} ist als LEGACY gefuehrt ({reason}), hat aber wieder "
        f"Produktionsaufrufer: {sorted(callers)}.\n"
        "Entweder den Aufruf zuruecknehmen oder den Eintrag hier UND den "
        "LEGACY-Vermerk im Modul entfernen."
    )


def test_every_legacy_module_carries_the_marker() -> None:
    """Der Vermerk im Quelltext und diese Liste duerfen nicht auseinanderlaufen."""
    missing: list[str] = []
    for symbol, (owner, _reason) in LEGACY_SYMBOLS.items():
        # Bewusst der MODUL-Docstring, nicht der Rohtext: beim ersten Versuch
        # landete der Vermerk in vier Dateien in einem Methoden-Docstring,
        # weil die Module gar keinen eigenen haben. Ein Rohtext-Vergleich
        # haette das durchgewunken.
        source = (ROOT / owner).read_text(encoding="utf-8")
        doc = ast.get_docstring(ast.parse(source)) or ""
        if "LEGACY — kein Produktionsaufrufer" not in doc:
            missing.append(owner)
    assert not missing, (
        "Diese Module stehen in LEGACY_SYMBOLS, tragen den Vermerk aber nicht: "
        f"{sorted(set(missing))}"
    )


def test_smart_director_is_not_marked_legacy() -> None:
    """Gegenprobe gegen zu breites Kennzeichnen.

    SmartDirector wird produktiv genutzt: clip_selector._get_text_embedding
    holt darueber den SigLIP-Text-Encoder, erreichbar ueber select_clip.
    Nur generate_timeline ist unerreichbar - das ist ein Methodenbefund, kein
    Modulbefund.
    """
    assert "SmartDirector" not in LEGACY_SYMBOLS
    text = (ROOT / "src/pb_studio/pacing/clip_selector.py").read_text(encoding="utf-8")
    assert "from ..ai.smart_director import SmartDirector" in text
