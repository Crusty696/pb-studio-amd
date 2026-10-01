from pathlib import Path


ROOT = Path(__file__).parents[1]
MAIN_WINDOW_XAML = ROOT / "PBStudio.UI" / "MainWindow.xaml"
MAIN_WINDOW_CS = ROOT / "PBStudio.UI" / "MainWindow.xaml.cs"


def test_main_tabs_have_stable_automation_names():
    xaml = MAIN_WINDOW_XAML.read_text(encoding="utf-8")
    expected_tabs = (
        "PROJEKT", "AUDIO", "VIDEO", "KI-REGIE", "TIMELINE", "EXPORT",
        "HIRN", "SETTINGS", "PERFORMANCE", "MODELLE", "CHAT", "TERMINAL",
        "ANCHOR",
    )
    for header in expected_tabs:
        assert (
            f'Header="{header}"' in xaml
            and f'AutomationProperties.Name="{header}"' in xaml
        ), f"Tab {header} braucht einen stabilen UIA-Namen"


def test_ui_action_logger_resolves_original_control_not_bubbled_source():
    code = MAIN_WINDOW_CS.read_text(encoding="utf-8")
    assert "e.OriginalSource" in code
    assert "FindActionElement" in code
    assert "(ohne Namen)" not in code.split("OnUiButtonClicked", 1)[1].split("OnUiSelectionChanged", 1)[0]
