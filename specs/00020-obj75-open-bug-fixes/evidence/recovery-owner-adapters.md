# T050/T051 Owner Adapter Receipt

**Result:** PASS

## Integrated owners

The process-wide barrier now covers Catalog transactions, project JSON/lifecycle,
Chat history, Brain feedback, embedding cache, Projector publish, FAISS mutation
and writer publish, Audio/Video media and analysis, Stem workers, Render queue and
final output. Snapshot acquisition rejects new foreign writes, drains active
owners and permits only same-thread flush/recovery callbacks.

One generation registers:

- backend Config and optionally locked WPF Settings;
- Catalog SQLite plus FAISS index/metadata/tombstones;
- every catalog project root: project/timeline/anchors/chat/State and sidecars;
- Brain DBs, empty terminal outbox, receipts, embeddings and Projector NPZ;
- validated application-owned Stem marker/WAV artifacts;
- original media and committed Render outputs only as external hash receipts.

Startup validates CURRENT before router imports. Runtime creates the initial
full generation before new work and a fresh full generation after render drain
on clean shutdown. Pytest lifespans explicitly skip automatic live snapshots.

## Semantic contracts

`Tests/test_recovery_owner_adapters.py`: `6 passed, 4 warnings in 6.75s`.

The suite proves one complete shared generation, Brain half-operation rejection,
Catalog/FAISS identity rejection, invalid Config rejection, optional missing
media degradation and restart without replay. The combined Project/Chat/Data
cluster independently passed `89/89`; Audio/Video/Render/Vector/Config passed
`146/146`.
