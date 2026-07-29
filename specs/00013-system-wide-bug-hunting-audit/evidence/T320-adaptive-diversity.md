# T320 — Adaptive diversity

Status: CONFIRMED

## Root cause and reference metrics

- Reference timeline: 4,816 cuts across exactly six clip IDs.
- Previous calculation: `int(6 * 0.8) = 4`, leaving only two candidates.
- A hard minimum blacklist size of three also over-constrained pools of three
  or four clips.
- Stale and repeated IDs could occupy multiple recent-history slots.

Reference distribution:

- clip_4: 951
- clip_2: 927
- clip_1: 911
- clip_5: 890
- clip_6: 755
- clip_3: 382
- Maximum consecutive identical clip: 1

## Contract

- Blacklist size is based on unique currently available IDs.
- Pools up to eight clips block at most 50 percent.
- Pools of at least three retain at least three selectable candidates.
- Global absolute blacklist cap remains 20.
- Stale IDs are pruned whenever the pool changes.
- Selection history is unique LRU state; reselecting an ID moves it to the
  newest position instead of consuming a duplicate slot.

For the confirmed six-clip pool, the new static calculation is:
`blacklist=3`, `selectable=3`.

## Static verification

- Python syntax and `git diff --check` — PASS
- Constant/import/reference scan — PASS
- Runtime selector distribution regressions remain deferred to T332.

## T328 follow-up

- Static regression design found duplicate legacy IDs could remain after
  available-ID pruning, violating the unique-LRU contract and consuming
  blacklist capacity twice.
- The selector now retains only the most recent occurrence of each available
  ID before applying the adaptive size limit.
- Python syntax and `git diff --check`: PASS. Runtime execution remains
  deferred to T332.
