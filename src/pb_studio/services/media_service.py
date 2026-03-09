import hashlib
import logging
import subprocess
import json
import os
from pathlib import Path
from pb_studio.data.repositories.media_repository import MediaRepository
from pb_studio.video.encoder_utils import _get_ffprobe_path

logger = logging.getLogger(__name__)

class MediaService:
    def __init__(self):
        self.repo = MediaRepository()

    def import_files(self, project_id: int, file_paths: list) -> list:
        """
        Imports files.
        Returns list of (media_id, status) tuples.
        """
        results = []
        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists():
                results.append((-1, "not_found"))
                continue

            # 1. Calc Hash
            file_hash = self._calculate_hash(path)
            
            # 2. Check Duplicate (Global check? Or Project check? Let's check Global for now to save storage logic, but link to project)
            # Actually, user might want same file in different projects.
            # But the repository check I wrote `find_by_hash` finds ANY match.
            # Let's simple check: If duplicate exists, do we link it? Or just re-add?
            # For simplicity: Re-add for now, allowing duplicates across projects. 
            # Ideally: Many-to-Many relation Media <-> Project. But our Schema is 1-to-Many (Project has Media).
            # So we just re-add.
            
            # 3. Extract Metadata (Duration)
            meta = self._get_metadata(path)
            duration = meta.get("duration", 0.0)
            
            # 4. Save (file_hash kann None sein bei Fehler)
            mid = self.repo.add_media(project_id, str(path), file_hash or "", duration, meta)
            results.append((mid, "imported"))
            logger.info(f"Imported: {path.name} (ID: {mid})")
            
        return results

    def _calculate_hash(self, path: Path, chunk_size=8192) -> str:
        """MD5 Hash of file. Returns None bei Fehler statt leerem String."""
        md5 = hashlib.md5()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(chunk_size):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as e:
            logger.error(f"Hashing failed: {e}")
            return None

    def _get_metadata(self, path: Path) -> dict:
        """Uses ffprobe to get duration/codec."""
        try:
            # We assume ffprobe is in PATH or accessible (user installed via script)
            cmd = [
                _get_ffprobe_path(), 
                "-v", "quiet", 
                "-print_format", "json", 
                "-show_format", 
                "-show_streams", 
                str(path)
            ]
            
            # Since we're on Windows, might need shell=False, creationflags for no window
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo, timeout=30)
            if result.returncode != 0:
                logger.warning(f"FFprobe returned code {result.returncode}: {result.stderr[:200]}")
                return {"duration": 0.0}
            if not result.stdout.strip():
                logger.warning(f"FFprobe returned empty output for {path}")
                return {"duration": 0.0}
            data = json.loads(result.stdout)
            
            format_info = data.get("format", {})
            try:
                duration = float(format_info.get("duration", 0.0) or 0.0)
            except (ValueError, TypeError):
                duration = 0.0
            
            return {
                "duration": duration,
                "format": format_info.get("format_name"),
                "bitrate": format_info.get("bit_rate"),
                "full_data": data
            }
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {path}: {e}")
            return {"duration": 0.0}

    def get_project_files(self, project_id: int):
        return self.repo.get_by_project(project_id)
