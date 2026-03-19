from __future__ import annotations

import ctypes
from pathlib import Path
import platform
import pytest

import backend.config as config_module


class _Shell32Success:
    def __init__(self, documents_path: str):
        self.documents_path = documents_path

    def SHGetKnownFolderPath(self, guid_ptr, flags, token, out_ptr):  # noqa: N802 - Windows API name
        out_ptr._obj.value = self.documents_path
        return 0


class _WindllSuccess:
    def __init__(self, documents_path: str):
        self.shell32 = _Shell32Success(documents_path)


class _Shell32Failure:
    def SHGetKnownFolderPath(self, guid_ptr, flags, token, out_ptr):  # noqa: N802 - Windows API name
        raise OSError("known folder unavailable")


class _WindllFailure:
    shell32 = _Shell32Failure()


@pytest.mark.skipif("Linux" in platform.system(), reason="Platform specific pathlib issues on Linux runner")
def test_default_documents_dir_prefers_windows_known_folder(monkeypatch, tmp_path):
    expected = tmp_path / "Dokumente"
    expected.mkdir()

    monkeypatch.delenv("PBSTUDIO_PROJECT_DIR", raising=False)
    monkeypatch.setattr(config_module.os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", _WindllSuccess(str(expected)), raising=False)

    assert config_module._default_documents_dir() == expected


@pytest.mark.skipif("Linux" in platform.system(), reason="Platform specific pathlib issues on Linux runner")
def test_default_documents_dir_falls_back_to_localized_userprofile(monkeypatch, tmp_path):
    userprofile = tmp_path / "user"
    localized = userprofile / "Dokumente"
    localized.mkdir(parents=True)

    monkeypatch.delenv("PBSTUDIO_PROJECT_DIR", raising=False)
    monkeypatch.setattr(config_module.os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", _WindllFailure(), raising=False)
    monkeypatch.setenv("USERPROFILE", str(userprofile))

    assert config_module._default_documents_dir() == localized
