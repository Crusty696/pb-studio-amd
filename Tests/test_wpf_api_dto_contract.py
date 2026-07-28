from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_handwritten_analysis_dtos_include_current_openapi_fields():
    api_client = (
        ROOT / "PBStudio.UI" / "Services" / "ApiClient.cs"
    ).read_text(encoding="utf-8")

    for field in (
        "SubtrackSegments",
        "TempoCurve",
        "OnsetTimes",
        "KickTimes",
        "SnareTimes",
        "HihatTimes",
        "EmbeddingSamples",
        "AudioKey",
        "TagSource",
        "MoodTags",
        "AvgBrightness",
        "AvgSaturation",
        "AvgColorTemp",
    ):
        assert field in api_client
