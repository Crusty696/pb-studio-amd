# ChromaDB Vector-Datenbank auf AMD - Recherche

**Status:** ✅ Validiert  
**Priorität:** MITTEL (CPU-basiert, keine GPU-Migration nötig)

---

## Aktuelle Situation

- ChromaDB ist CPU-basiert
- Speichert CLIP-Embeddings als Vektoren
- Ermöglicht Similarity-Search
- Keine GPU-Abhängigkeit

---

## AMD-Lösung: Keine Migration nötig

### Warum keine Änderung?

ChromaDB nutzt:
- SQLite (CPU)
- NumPy (CPU)
- Optional: HNSW Index (CPU)

**Die GPU wird nur für Embedding-Generierung (CLIP) benötigt, nicht für ChromaDB selbst.**

### Architektur

```
[Video Frame] → [CLIP auf GPU] → [Embedding] → [ChromaDB auf CPU]
                  ↑ DirectML                      ↑ Keine Änderung
```

---

## Techstack mit Versionen

### Python-Pakete (kompatibel getestet)

| Paket | Version | Zweck |
|-------|---------|-------|
| chromadb | 0.5.23 | Vector-Datenbank |
| numpy | 1.26.4 | Array-Operationen |
| sqlite3 | Built-in | Storage Backend |

### Abhängigkeitsmatrix

| Paket A | Paket B | Kompatibel? |
|---------|---------|-------------|
| chromadb 0.5.23 | numpy 1.26.4 | ✅ Ja |
| chromadb 0.5.23 | onnxruntime-directml 1.23.0 | ✅ Ja (unabhängig) |

### Wichtig

ChromaDB hat eigene Embedding-Funktionen eingebaut, aber wir nutzen diese NICHT.
Stattdessen: CLIP ONNX → Embedding → ChromaDB (nur Speicherung)

---

## Installationsanweisungen

### Schritt 1: Environment (falls nicht vorhanden)

```powershell
python -m venv pb_studio_amd
pb_studio_amd\Scripts\activate
```

### Schritt 2: Pakete installieren

```powershell
pip install chromadb==0.5.23
```

### Schritt 3: Verifizieren

```powershell
python -c "import chromadb; print(f'ChromaDB {chromadb.__version__} OK')"
```

---

## Taskplan

| # | Task | Abhängigkeit | Geschätzte Zeit |
|---|------|--------------|-----------------|
| 1 | ChromaDB installieren | Environment | 5 min |
| 2 | Bestehende DB migrieren (falls vorhanden) | Task 1 | 30 min |
| 3 | CLIP-Integration testen | CLIP fertig | 1 h |
| 4 | Query-Performance testen | Task 3 | 30 min |

**Gesamtzeit:** ~2 Stunden

---

## Verwendung in PB Studio

### Collection erstellen

```python
import chromadb

# Persistenter Client
client = chromadb.PersistentClient(path="./chroma_db")

# Collection für Video-Frames
collection = client.get_or_create_collection(
    name="video_frames",
    metadata={"hnsw:space": "cosine"}  # Cosine Similarity
)
```

### Embeddings speichern

```python
def store_frame_embedding(frame_id, embedding, metadata):
    """
    Speichert CLIP-Embedding in ChromaDB.
    
    frame_id: Eindeutige Frame-ID
    embedding: NumPy Array von CLIP (512 oder 768 dim)
    metadata: Dict mit Frame-Infos (timestamp, video_path, etc.)
    """
    collection.add(
        ids=[frame_id],
        embeddings=[embedding.tolist()],
        metadatas=[metadata]
    )
```

### Similarity Search

```python
def find_similar_frames(query_embedding, n_results=10):
    """
    Findet ähnliche Frames basierend auf Embedding.
    """
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=n_results
    )
    return results
```

### Text-zu-Frame Suche

```python
def search_by_text(text_embedding, n_results=10):
    """
    Sucht Frames die zu Text-Beschreibung passen.
    text_embedding kommt von CLIP Text-Encoder.
    """
    results = collection.query(
        query_embeddings=[text_embedding.tolist()],
        n_results=n_results
    )
    return results
```

---

## Speicherbedarf

| Anzahl Embeddings | Disk | RAM | Status |
|-------------------|------|-----|--------|
| 10.000 | ~50 MB | ~100 MB | ✅ |
| 100.000 | ~500 MB | ~1 GB | ✅ |
| 1.000.000 | ~5 GB | ~8 GB | ✅ |

**Kein VRAM nötig** - reine CPU/Disk-Operationen

---

## Performance-Tipps

### Batch-Insert

```python
def store_batch(ids, embeddings, metadatas):
    """
    Batch-Insert ist schneller als einzeln.
    """
    collection.add(
        ids=ids,
        embeddings=[e.tolist() for e in embeddings],
        metadatas=metadatas
    )
```

### Index-Konfiguration für große Datenmengen

```python
collection = client.get_or_create_collection(
    name="video_frames",
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,  # Höher = bessere Qualität, langsamer Build
        "hnsw:search_ef": 100,        # Höher = bessere Qualität, langsamer Search
        "hnsw:M": 16                  # Verbindungen pro Knoten
    }
)
```

---

## Risikobewertung

| Risiko | Bewertung | Mitigation |
|--------|-----------|------------|
| Keine Änderung nötig | 🟢 Niedrig | - |
| Performance identisch | 🟢 Niedrig | - |
| DB-Migration | 🟢 Niedrig | Format ist portabel |

---

## Quellen

1. https://docs.trychroma.com/
2. https://github.com/chroma-core/chroma
3. https://www.trychroma.com/
