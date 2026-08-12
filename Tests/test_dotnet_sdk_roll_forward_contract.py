"""The .NET 9 build contract must accept stable servicing SDK updates."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import generate_release_provenance


ROOT = Path(__file__).resolve().parents[1]


def test_global_json_allows_current_and_future_stable_dotnet_9_sdks() -> None:
    sdk = json.loads((ROOT / "global.json").read_text(encoding="utf-8"))["sdk"]

    assert sdk == {
        "version": "9.0.300",
        "rollForward": "latestFeature",
        "allowPrerelease": False,
    }


def test_release_provenance_accepts_only_stable_dotnet_9_roll_forward() -> None:
    policy = {
        "version": "9.0.300",
        "rollForward": "latestFeature",
        "allowPrerelease": False,
    }

    for selected in ("9.0.300", "9.0.317", "9.0.318", "9.0.400"):
        assert generate_release_provenance._dotnet_sdk_matches_policy(
            selected, policy
        )

    for selected in ("8.0.419", "10.0.100", "9.0.200", "9.0.400-preview.1"):
        assert not generate_release_provenance._dotnet_sdk_matches_policy(
            selected, policy
        )


def test_ci_uses_the_latest_stable_dotnet_9_sdk() -> None:
    workflows = [
        (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        for name in ("ci.yml", "security.yml")
    ]
    combined = "\n".join(workflows)

    assert 'dotnet-version: "9.0.316"' not in combined
    assert combined.count('dotnet-version: "9.0.x"') == 3
