from pathlib import Path

from pb_studio.config_manager import ConfigManager
from pb_studio.data.database_core import DatabaseCore
from pb_studio.data.repositories.media_repository import MediaRepository
from pb_studio.services.media_service import MediaService


class _TempConfig:
    def __init__(self, db_path: Path):
        self._config = {"paths": {"db_path": str(db_path)}}

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def resolve_path(self, value: str) -> Path:
        return Path(value).resolve()


def _reset_db_singletons():
    DatabaseCore._instance = None
    DatabaseCore._local = type(DatabaseCore._local)()
    DatabaseCore._all_connections = []


def test_add_media_is_idempotent_per_project_and_path(tmp_path, monkeypatch):
    db_path = tmp_path / "media_idempotent.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    repo = MediaRepository()
    media_file = tmp_path / "clip.wav"
    media_file.write_bytes(b"abc123")

    first_id = repo.add_media(1, str(media_file), "hash-a", 1.0, {"clip_type": "audio"})
    second_id = repo.add_media(1, str(media_file), "hash-b", 2.5, {"clip_type": "audio", "name": "updated"})

    assert first_id == second_id
    rows = repo.get_by_project(1)
    assert len(rows) == 1
    assert rows[0]["file_hash"] == "hash-b"
    assert rows[0]["duration_sec"] == 2.5

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)


def test_media_service_reimport_skips_duplicate_rows_for_real_file(tmp_path, monkeypatch):
    db_path = tmp_path / "media_service.db"
    monkeypatch.setattr(ConfigManager, "_instance", _TempConfig(db_path), raising=False)
    _reset_db_singletons()

    media_file = tmp_path / "song.mp3"
    media_file.write_bytes(b"ID3" + b"x" * 512)

    service = MediaService()
    monkeypatch.setattr(service, "_get_metadata", lambda path: {"duration": 3.0, "format": "mp3"})

    first = service.import_files(1, [str(media_file)])
    second = service.import_files(1, [str(media_file)])
    rows = service.get_project_files(1)

    assert first == second
    assert len(rows) == 1
    assert Path(rows[0]["file_path"]).resolve() == media_file.resolve()

    DatabaseCore().shutdown()
    monkeypatch.setattr(ConfigManager, "_instance", None, raising=False)
