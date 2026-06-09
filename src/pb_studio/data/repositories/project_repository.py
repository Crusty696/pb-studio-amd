import json
import logging
import sqlite3
import time
import functools
from typing import List, Optional, Dict, Callable
from pb_studio.data.database_core import DatabaseCore

logger = logging.getLogger(__name__)

# Exponential backoff schedule for transient SQLite lock contention.
_LOCK_RETRY_DELAYS = (0.05, 0.10, 0.20, 0.40, 0.80)


def _is_retryable_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("database is locked" in msg) or ("database table is locked" in msg)


def _retry_on_database_lock(func: Callable) -> Callable:
    """Decorator: retry method on transient database is locked errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_exc: Optional[sqlite3.OperationalError] = None
        max_attempts = len(_LOCK_RETRY_DELAYS) + 1  # 1 initial try + 5 retries
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as exc:
                if not _is_retryable_lock_error(exc):
                    raise
                last_exc = exc
                if attempt >= len(_LOCK_RETRY_DELAYS):
                    logger.error(
                        "ProjectRepository.%s: exhausted %d retries -- DB still locked: %s",
                        func.__name__,
                        len(_LOCK_RETRY_DELAYS),
                        exc,
                    )
                    raise
                delay = _LOCK_RETRY_DELAYS[attempt]
                logger.info(
                    "ProjectRepository.%s: database locked (attempt %d/%d); backing off %.3fs before retry",
                    func.__name__,
                    attempt + 1,
                    max_attempts,
                    delay,
                )
                time.sleep(delay)
    return wrapper


class ProjectRepository:
    def __init__(self):
        self.db = DatabaseCore()

    @_retry_on_database_lock
    def create_project(self, name: str, data: Dict = None) -> int:
        """Create a new project with proper transaction handling."""
        json_str = json.dumps(data) if data else "{}"
        
        try:
            with self.db.transaction(immediate=True) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO projects (name, json_data) VALUES (?, ?)", 
                    (name, json_str)
                )
                project_id = cursor.lastrowid
                logger.info(f"Created Project: {name} (ID: {project_id})")
                return project_id
                
        except Exception as e:
            logger.error(f"Failed to create project '{name}': {e}", exc_info=True)
            return -1

    def get_all(self) -> List[Dict]:
        """Get all projects ordered by last modified."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY last_modified DESC")
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            project = dict(row)
            # Parse JSON data
            if project.get("json_data"):
                try:
                    project["data"] = json.loads(project["json_data"])
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Invalid JSON in project {project['id']}: {e}")
                    project["data"] = {}
            else:
                project["data"] = {}
            result.append(project)
        
        return result

    def get_by_id(self, project_id: int) -> Optional[Dict]:
        """Get a single project by ID."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        project = dict(row)
        # Parse JSON on read
        if project.get("json_data"):
            try:
                project["data"] = json.loads(project["json_data"])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Invalid JSON in project {project_id}: {e}")
                project["data"] = {}
        else:
            project["data"] = {}
            
        return project

    @_retry_on_database_lock
    def update_project(self, project_id: int, name: str = None, data: Dict = None):
        """Update project name and/or data. Updates last_modified automatically."""
        if name is None and data is None:
            logger.warning("update_project called with no changes")
            return
        
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)

        if data is not None:
            updates.append("json_data = ?")
            params.append(json.dumps(data))
            
        updates.append("last_modified = CURRENT_TIMESTAMP")
        params.append(project_id)
        
        sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
        
        try:
            with self.db.transaction(immediate=True) as conn:
                conn.execute(sql, tuple(params))
                logger.info(f"Updated Project {project_id}")
                
        except Exception as e:
            logger.error(f"Update failed for Project {project_id}: {e}", exc_info=True)
            raise

    @_retry_on_database_lock
    def delete_project(self, project_id: int):
        """Delete a project. Cascade deletes all related media."""
        try:
            with self.db.transaction(immediate=True) as conn:
                # Foreign key cascade will delete related media and vector_map entries
                conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                logger.info(f"Deleted Project ID: {project_id}")
                
        except Exception as e:
            logger.error(f"Delete failed for Project {project_id}: {e}", exc_info=True)
            raise

    def get_default_project(self) -> Optional[Dict]:
        """Get the default project (ID: 1)."""
        return self.get_by_id(1)

    def rename_project(self, project_id: int, new_name: str):
        """Rename a project."""
        self.update_project(project_id, name=new_name)

