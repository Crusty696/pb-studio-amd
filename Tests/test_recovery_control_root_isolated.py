"""The test suite never touches the real recovery control root (2026-09-30).

A pytest run while the app was open wrote a restore journal into the real
%LOCALAPPDATA%\\PB_Studio\\recovery-control\\v1 and tried to replace
data/pb_studio.db; the next app start rolled back to an old generation.
"""

from pathlib import Path

from backend.recovery_bootstrap import fixed_control_root

from conftest import PBSTUDIO_REAL_LOCALAPPDATA


def test_second_backend_process_does_not_touch_recovery(tmp_path):
    import subprocess
    import sys

    from backend.recovery_bootstrap import ensure_recovery_ready

    root = tmp_path / "PB_Studio" / "recovery-control" / "v1"
    root.mkdir(parents=True)
    ensure_recovery_ready(root)  # this process now owns the root

    probe = (
        "import sys; from pathlib import Path; "
        "from backend.recovery_bootstrap import ensure_recovery_ready, RecoveryBootstrapError\n"
        "try:\n    ensure_recovery_ready(Path(sys.argv[1]))\n"
        "except RecoveryBootstrapError as e:\n    print('LOCKED', e); sys.exit(3)\n"
        "print('ENTERED')"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe, str(root)],
        capture_output=True, text=True, timeout=120,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert done.returncode == 3, done.stdout + done.stderr
    assert "LOCKED" in done.stdout
    assert not (root / "journal.json").exists()


def test_control_root_is_outside_real_localappdata():
    root = fixed_control_root().resolve()
    assert "pbstudio-pytest-localappdata-" in str(root)
    if PBSTUDIO_REAL_LOCALAPPDATA:
        real_app_dir = (Path(PBSTUDIO_REAL_LOCALAPPDATA) / "PB_Studio").resolve()
        assert not root.is_relative_to(real_app_dir)
