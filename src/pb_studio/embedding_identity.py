"""Persisted SigLIP space identity; absent provenance is never current.

v2 uses the registered processor's mean/std (.5/.5). v1 used CLIP values.
Equal vector dimensions do not make these spaces interchangeable.
"""

CURRENT_MODEL_NAME = "siglip_vision"
CURRENT_MODEL_VERSION = "onnx-dml-v2"
EMBED_DIM = 1152


def current_video_embedding_identity() -> dict[str, str]:
    return {
        "embedding_model_name": CURRENT_MODEL_NAME,
        "embedding_model_version": CURRENT_MODEL_VERSION,
    }


def is_current_video_embedding(metadata) -> bool:
    return (
        isinstance(metadata, dict)
        and metadata.get("embedding_model_name") == CURRENT_MODEL_NAME
        and metadata.get("embedding_model_version") == CURRENT_MODEL_VERSION
    )
