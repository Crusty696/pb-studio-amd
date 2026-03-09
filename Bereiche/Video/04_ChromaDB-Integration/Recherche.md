# ChromaDB Integration - Recherche

**Stand:** 04.01.2026
**Bereich:** Video
**Risiko:** 🟢 Sehr Niedrig

---

## 1. Aktueller Stand

ChromaDB wird verwendet für:
- Speicherung von CLIP-Embeddings
- Ähnlichkeitssuche (Similarity Search)
- Szenen-Datenbank

---

## 2. GPU-Relevanz

**KEINE GPU-Abhängigkeit!**

ChromaDB läuft komplett auf CPU. Die Vektor-Operationen nutzen:
- NumPy
- hnswlib (CPU-basiert)

---

## 3. AMD Migration

### Erforderliche Änderungen: KEINE

ChromaDB funktioniert identisch auf AMD-Systemen.

### Paket:
```bash
pip install chromadb>=0.4.0
```

---

## 4. Hinweis: FAISS

Falls die Original-Version FAISS mit GPU nutzt:
- `faiss-gpu` → NICHT auf AMD verfügbar
- Alternative: `faiss-cpu` oder ChromaDB (empfohlen)

ChromaDB ist die bessere Wahl für AMD!

---

## 5. Validierung

| Aspekt | Status |
|--------|--------|
| CPU-basiert | ✅ |
| Keine GPU | ✅ |
| Keine Änderung | ✅ |

---

*Recherche: 04.01.2026*
