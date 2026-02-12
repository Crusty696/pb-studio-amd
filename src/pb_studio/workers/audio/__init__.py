"""
PB Studio Audio Pipeline Workers

Provides specialized workers for audio processing tasks:
- AudioImportWorker: Import and convert audio files
- AudioAnalyzeWorker: Beat detection and analysis
- AudioStemWorker: Stem separation
- AudioEmbeddingWorker: CLAP audio embeddings
"""

from .audio_import_worker import AudioImportWorker
from .audio_analyze_worker import AudioAnalyzeWorker
from .audio_stem_worker import AudioStemWorker
from .audio_embedding_worker import AudioEmbeddingWorker

__all__ = [
    'AudioImportWorker',
    'AudioAnalyzeWorker',
    'AudioStemWorker',
    'AudioEmbeddingWorker',
]
