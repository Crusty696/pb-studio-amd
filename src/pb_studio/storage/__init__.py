"""Storage layer for embeddings + brain-store.

Plan Phase 2/3: sqlite-vec virtual tables + 3 brain-store SQLite files.
Repository pattern: sqlite-vec / sqlite3 used ONLY in this package.
Other modules consume the repository APIs.
"""

from .sqlite_init import init_connection, checkpoint, PRAGMA_INIT
from .migration_runner import migrate

__all__ = ["init_connection", "checkpoint", "PRAGMA_INIT", "migrate"]
