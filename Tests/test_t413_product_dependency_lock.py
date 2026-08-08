from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_SCRIPT = ROOT / "scripts" / "lock_python_requirements.py"
SPEC = importlib.util.spec_from_file_location("lock_python_requirements", LOCK_SCRIPT)
assert SPEC is not None and SPEC.loader is not None
lock_python_requirements = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lock_python_requirements)


EXPECTED_PRODUCT_PINS = {
    "torch": "2.11.0+cpu",
    "torchvision": "0.26.0+cpu",
    "torchaudio": "2.11.0+cpu",
    "transformers": "5.5.4",
    "huggingface-hub": "1.5.0",
    "pillow": "12.3.0",
    "pip": "26.2",
    "pydantic-settings": "2.14.2",
    "setuptools": "81.0.0",
    "idna": "3.15",
    "msgpack": "1.2.1",
    "onnx": "1.22.0",
    "starlette": "1.3.1",
    "urllib3": "2.7.0",
    "tokenizers": "0.22.2",
}
TRANSITIVE_ONLY = {"idna", "msgpack", "onnx", "urllib3", "tokenizers"}


def test_product_lock_contains_approved_cp311_cpu_versions() -> None:
    direct = lock_python_requirements._read_pins(
        ROOT / "requirements-direct.txt", hashes_required=False
    )
    locked = lock_python_requirements._read_pins(
        ROOT / "requirements.txt", hashes_required=True
    )

    for package, expected in EXPECTED_PRODUCT_PINS.items():
        assert locked[package][1] == expected

    for package in EXPECTED_PRODUCT_PINS.keys() - TRANSITIVE_ONLY:
        assert direct[package][1] == EXPECTED_PRODUCT_PINS[package]
    assert TRANSITIVE_ONLY.isdisjoint(direct)
    assert lock_python_requirements.LOCK_PIP_VERSION == "26.2"
    lock_python_requirements._assert_cpu_torch_contract(locked)


def test_transitive_upgrade_controls_accept_exact_target_constraints() -> None:
    upgrades, constraints = lock_python_requirements._parse_upgrade_packages(
        ["idna==3.15", "msgpack"]
    )

    assert upgrades == {"idna", "msgpack"}
    assert constraints == ["idna==3.15"]
