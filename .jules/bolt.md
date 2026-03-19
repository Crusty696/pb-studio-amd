bolt-optimize-checkerboard-novelty-4639455432380006930
## 2025-03-14 - Vectorized checkerboard novelty in AudioAnalyzer
**Learning:** Nested python `for` loops extracting overlapping sliding windows from a matrix can be extremely slow and can be fully vectorized. Using `np.lib.stride_tricks.as_strided` allows creating zero-copy views of the sub-matrices, and `np.tensordot` can compute the novelty kernel projection across all windows simultaneously.
**Action:** Next time you need to apply a 2D kernel convolution over an image or matrix diagonal in Python, skip the explicit `for` loop and use `as_strided` and `tensordot` (or `einsum`) to offload the tight loop to optimized C/BLAS backends.
=======
## 2026-03-14 - FAISS Metadata Reconstruction Lookups
**Learning:** Performing a linear search over a FAISS `metadata.items()` dictionary to find the corresponding `faiss_id` for a given `scene_id` inside an inner loop causes O(N) lookup bottleneck per element. This occurs frequently when trying to use `IndexFlatIP.reconstruct()` and mapping your internal IDs back to FAISS IDs.
**Action:** When reconstructing FAISS embeddings or querying the vector index frequently, implement an inverted dictionary cache mapping `internal_id -> faiss_id` (e.g. `_inverted_metadata_cache`). Ensure to invalidate/rebuild this cache if the size of the original metadata dictionary changes to maintain O(1) performance.
main
