from pathlib import Path

from scripts.requirements.validate_obj77_reservations import validate_reservations


def test_only_four_external_authorizations_are_blocking(tmp_path: Path) -> None:
    receipt = tmp_path / "reservations.json"
    receipt.write_text(
        '{"schema_version":1,"intel":{"status":"missing"},"nvidia":{"status":"missing"},'
        '"lm_window":{"status":"not_authorized"},'
        '"stress_window":{"status":"not_reserved"}}',
        encoding="utf-8",
    )
    errors = validate_reservations(receipt)
    assert errors == [
        "intel.status must be reserved",
        "nvidia.status must be reserved",
        "lm_window.status must be authorized",
        "stress_window.status must be reserved",
    ]
