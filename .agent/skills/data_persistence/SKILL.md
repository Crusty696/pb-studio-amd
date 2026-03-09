---
name: Data Persistence (SQLite & Vector)
description: Guidelines for managing data integirty using SQLite and FAISS, focusing on transaction safety and vector index management.
---

# Data Persistence Expert Skill

## Core Principles
- **Hybrid Storage:** Relational data in SQLite (`pb_studio.db`), Vector embeddings in FAISS (`.faiss`).
- **Transaction Integrity:** Never leave the DB in a broken state if an operation fails.
- **Thread Safety:** SQLite connections can be shared (`check_same_thread=False`) BUT explicit locking is often safer for writes.

## 1. SQLite Best Practices
- **Singleton Pattern:** Always use `DatabaseCore()` to get the connection.
- **WAL Mode:** Ensure Write-Ahead-Logging is enabled for concurrency (Reader doesn't block Writer).
- **Row Factory:** Use `sqlite3.Row` to access columns by name (`row['id']`).

```python
from src.pb_studio.data.database_core import DatabaseCore

def safe_insert(data):
    db = DatabaseCore()
    conn = db.get_connection()
    try:
        with conn: # Context manager automatically commits or rollbacks
            conn.execute("INSERT INTO projects ...", data)
    except sqlite3.Error as e:
        logger.error(f"DB Error: {e}")
        # Connection is already rolled back by the context manager
```

## 2. Vector Store (FAISS)
- **Dimensions:** Must match the model output exactly (e.g., 768 for SigLIP/Moondream).
- **Normalization:** Always L2-normalize embeddings *before* adding to the index for Cosine Similarity.
- **Persistence:** Call `save()` explicitly after batch updates. FAISS is in-memory!

## 3. Schema Migrations
- **No external tools:** We use simple SQL scripts or `CREATE TABLE IF NOT EXISTS`.
- **Alter Table:** If adding a column, catch the `OperationalError` if it already exists (lazy migration).

## 4. Performance
- **Batching:** Use `executemany` for inserting thousands of rows.
- **Indices:** Ensure `project_id` and foreign keys are indexed.
