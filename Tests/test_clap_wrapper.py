"""
Unit tests for CLAP Audio Analyzer

Tests the CLAP wrapper functionality including:
- Model initialization
- Audio loading and preprocessing
- Embedding generation
- Classification
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pb_studio.ai.clap_wrapper import (
    CLAPAnalyzer,
    DEFAULT_MOOD_LABELS,
    INSTRUMENT_LABELS,
    GENRE_LABELS,
    CLAP_SAMPLE_RATE,
    CLAP_DURATION,
    CLAP_EMBEDDING_DIM
)


class TestCLAPAnalyzer:
    """Test suite for CLAPAnalyzer class"""

    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for testing"""
        # Patch at the source module where ConfigManager is imported from
        with patch('pb_studio.config_manager.ConfigManager') as mock:
            mock_instance = Mock()
            mock_instance.get.return_value = {"models_dir": "./test_models"}
            mock.return_value = mock_instance
            yield mock

    @pytest.fixture
    def analyzer_lazy(self, mock_config_manager):
        """Create analyzer with lazy loading"""
        return CLAPAnalyzer(lazy_load=True)

    def test_init_lazy_load(self, analyzer_lazy):
        """Test lazy initialization"""
        assert analyzer_lazy._initialized is False
        assert analyzer_lazy.audio_encoder_session is None
        assert analyzer_lazy.text_encoder_session is None
        assert analyzer_lazy.combined_session is None

    def test_session_options(self, analyzer_lazy):
        """Test DirectML session options configuration"""
        sess_options = analyzer_lazy._create_session_options()

        # KRITISCH (IRON RULE §2): enable_mem_pattern UND enable_cpu_mem_arena MUSS False sein
        assert sess_options.enable_mem_pattern is False
        assert sess_options.enable_cpu_mem_arena is False

    def test_providers_directml_only(self, analyzer_lazy):
        """IRC-1: Provider-Liste enthaelt NUR DmlExecutionProvider — kein CPU-Fallback.

        Vorher: ['DmlExecutionProvider', 'CPUExecutionProvider'] (silent CPU bei DML-Init-Fehler).
        Jetzt: ['DmlExecutionProvider'] (loud RuntimeError wenn DML nicht verfuegbar).
        IRON RULE 1: AMD DirectML ONLY."""
        with patch('pb_studio.ai.clap_wrapper.ort.get_available_providers') as mock_providers:
            # Test with DirectML available
            mock_providers.return_value = ['DmlExecutionProvider', 'CPUExecutionProvider']
            providers = analyzer_lazy._get_providers()

            assert providers == ['DmlExecutionProvider']
            assert 'CPUExecutionProvider' not in providers

    def test_providers_no_cpu_fallback_raises(self, analyzer_lazy):
        """IRC-1: Wenn DirectML nicht verfuegbar ist, MUSS RuntimeError fliegen.

        Vorher: silent CPU-Fallback (langsam + unsichtbar fuer VRAMBudgetManager).
        Jetzt: loud RuntimeError — IRON RULE 1: AMD DirectML ONLY."""
        with patch('pb_studio.ai.clap_wrapper.ort.get_available_providers') as mock_providers:
            mock_providers.return_value = ['CPUExecutionProvider']
            with pytest.raises(RuntimeError, match="DirectML"):
                analyzer_lazy._get_providers()

    def test_load_audio_resampling(self, analyzer_lazy):
        """Test audio loading and resampling"""
        # Mock librosa.load
        with patch('pb_studio.ai.clap_wrapper.librosa.load') as mock_load:
            # Simulate 5-second audio at target sample rate
            mock_audio = np.random.randn(CLAP_SAMPLE_RATE * 5)
            mock_load.return_value = (mock_audio, CLAP_SAMPLE_RATE)

            audio = analyzer_lazy.load_audio("test.mp3")

            # Should be padded to 10 seconds
            expected_length = int(CLAP_SAMPLE_RATE * CLAP_DURATION)
            assert len(audio) == expected_length
            assert audio.dtype == np.float32

    def test_load_audio_trimming(self, analyzer_lazy):
        """Test audio trimming for long files"""
        with patch('pb_studio.ai.clap_wrapper.librosa.load') as mock_load:
            # Simulate 15-second audio (too long)
            mock_audio = np.random.randn(CLAP_SAMPLE_RATE * 15)
            mock_load.return_value = (mock_audio, CLAP_SAMPLE_RATE)

            audio = analyzer_lazy.load_audio("test.mp3")

            # Should be trimmed to 10 seconds
            expected_length = int(CLAP_SAMPLE_RATE * CLAP_DURATION)
            assert len(audio) == expected_length

    def test_preprocess_audio(self, analyzer_lazy):
        """Test mel spectrogram preprocessing"""
        # Create dummy audio
        audio = np.random.randn(CLAP_SAMPLE_RATE * 10)

        mel_spec = analyzer_lazy.preprocess_audio(audio)

        # Check output shape [batch, channels, n_mels, time_frames]
        assert mel_spec.ndim == 4
        assert mel_spec.shape[0] == 1  # Batch size
        assert mel_spec.shape[1] == 1  # Channels
        assert mel_spec.dtype == np.float32

        # Check normalization (should be in [0, 1])
        assert mel_spec.min() >= 0.0
        assert mel_spec.max() <= 1.0

    def test_encode_audio_mock(self, analyzer_lazy):
        """Test audio encoding with mocked model"""
        # Mock model session
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [Mock(name="audio_input")]

        # Mock embedding output
        mock_embedding = np.random.randn(1, CLAP_EMBEDDING_DIM).astype(np.float32)
        mock_session.run.return_value = [mock_embedding]

        analyzer_lazy.audio_encoder_session = mock_session
        analyzer_lazy._initialized = True

        with patch.object(analyzer_lazy, 'load_audio') as mock_load:
            mock_load.return_value = np.random.randn(CLAP_SAMPLE_RATE * 10)

            with patch.object(analyzer_lazy, 'preprocess_audio') as mock_preprocess:
                mock_preprocess.return_value = np.random.randn(1, 1, 64, 1000)

                embedding = analyzer_lazy.encode_audio("test.mp3")

                assert embedding is not None
                assert embedding.shape == (CLAP_EMBEDDING_DIM,)
                assert embedding.dtype == np.float32

                # Check normalization (L2 norm should be ~1.0)
                norm = np.linalg.norm(embedding)
                assert 0.99 <= norm <= 1.01

    def test_classify_audio_mock(self, analyzer_lazy):
        """Test classification with mocked embeddings"""
        # Create mock embeddings
        audio_embedding = np.random.randn(CLAP_EMBEDDING_DIM).astype(np.float32)
        audio_embedding /= np.linalg.norm(audio_embedding)  # Normalize

        test_labels = ["happy", "sad", "energetic"]
        num_labels = len(test_labels)

        # Mock encode methods
        with patch.object(analyzer_lazy, 'encode_audio') as mock_encode_audio:
            mock_encode_audio.return_value = audio_embedding

            with patch.object(analyzer_lazy, 'encode_text') as mock_encode_text:
                # Create random text embeddings
                text_embeddings = np.random.randn(num_labels, CLAP_EMBEDDING_DIM).astype(np.float32)
                text_embeddings /= np.linalg.norm(text_embeddings, axis=1, keepdims=True)
                mock_encode_text.return_value = text_embeddings

                analyzer_lazy._initialized = True

                results = analyzer_lazy.classify_audio("test.mp3", test_labels, top_k=2)

                assert len(results) == 2  # top_k=2
                assert all(isinstance(label, str) for label, score in results)
                assert all(isinstance(score, float) for label, score in results)
                assert all(label in test_labels for label, score in results)

    def test_get_mood_tags(self, analyzer_lazy):
        """Test mood tag extraction"""
        with patch.object(analyzer_lazy, 'classify_audio') as mock_classify:
            mock_classify.return_value = [
                ("energetic", 0.95),
                ("uplifting", 0.87),
                ("happy", 0.75)
            ]

            moods = analyzer_lazy.get_mood_tags("test.mp3", top_k=3)

            assert len(moods) == 3
            assert moods == ["energetic", "uplifting", "happy"]
            mock_classify.assert_called_once()

    def test_get_instrument_tags(self, analyzer_lazy):
        """Test instrument detection"""
        with patch.object(analyzer_lazy, 'classify_audio') as mock_classify:
            mock_classify.return_value = [
                ("guitar", 0.88),
                ("drums", 0.76)
            ]

            instruments = analyzer_lazy.get_instrument_tags("test.mp3", top_k=2)

            assert len(instruments) == 2
            assert instruments == ["guitar", "drums"]

    def test_get_genre_tags(self, analyzer_lazy):
        """Test genre classification"""
        with patch.object(analyzer_lazy, 'classify_audio') as mock_classify:
            mock_classify.return_value = [
                ("rock", 0.92),
                ("pop", 0.65),
                ("electronic", 0.52)
            ]

            genres = analyzer_lazy.get_genre_tags("test.mp3", top_k=3)

            assert len(genres) == 3
            assert genres == ["rock", "pop", "electronic"]

    def test_analyze_comprehensive(self, analyzer_lazy):
        """Test comprehensive analysis"""
        with patch.object(analyzer_lazy, 'get_mood_tags') as mock_moods:
            mock_moods.return_value = ["energetic", "happy"]

            with patch.object(analyzer_lazy, 'get_instrument_tags') as mock_instruments:
                mock_instruments.return_value = ["guitar", "drums"]

                with patch.object(analyzer_lazy, 'get_genre_tags') as mock_genres:
                    mock_genres.return_value = ["rock"]

                    with patch.object(analyzer_lazy, 'encode_audio') as mock_encode:
                        mock_embedding = np.random.randn(CLAP_EMBEDDING_DIM)
                        mock_encode.return_value = mock_embedding

                        results = analyzer_lazy.analyze_audio_comprehensive("test.mp3")

                        assert "moods" in results
                        assert "instruments" in results
                        assert "genres" in results
                        assert "embedding" in results

                        assert results["moods"] == ["energetic", "happy"]
                        assert results["instruments"] == ["guitar", "drums"]
                        assert results["genres"] == ["rock"]
                        assert np.array_equal(results["embedding"], mock_embedding)

    def test_compute_similarity(self, analyzer_lazy):
        """Test audio similarity computation"""
        # Create two normalized embeddings
        emb1 = np.random.randn(CLAP_EMBEDDING_DIM).astype(np.float32)
        emb1 /= np.linalg.norm(emb1)

        emb2 = np.random.randn(CLAP_EMBEDDING_DIM).astype(np.float32)
        emb2 /= np.linalg.norm(emb2)

        with patch.object(analyzer_lazy, 'encode_audio') as mock_encode:
            mock_encode.side_effect = [emb1, emb2]

            similarity = analyzer_lazy.compute_similarity("test1.mp3", "test2.mp3")

            assert 0.0 <= similarity <= 1.0
            assert isinstance(similarity, float)

    def test_is_ready_property(self, analyzer_lazy):
        """Test is_ready property"""
        assert analyzer_lazy.is_ready is False

        # Set up split model
        analyzer_lazy.audio_encoder_session = Mock()
        analyzer_lazy.text_encoder_session = Mock()
        analyzer_lazy._initialized = True

        assert analyzer_lazy.is_ready is True

    def test_unload(self, analyzer_lazy):
        """Test model unloading"""
        analyzer_lazy.audio_encoder_session = Mock()
        analyzer_lazy.text_encoder_session = Mock()
        analyzer_lazy.combined_session = Mock()
        analyzer_lazy._initialized = True

        analyzer_lazy.unload()

        assert analyzer_lazy.audio_encoder_session is None
        assert analyzer_lazy.text_encoder_session is None
        assert analyzer_lazy.combined_session is None
        assert analyzer_lazy._initialized is False


class TestConstants:
    """Test module constants"""

    def test_mood_labels_coverage(self):
        """Test mood label diversity"""
        assert len(DEFAULT_MOOD_LABELS) >= 30
        assert "energetic" in DEFAULT_MOOD_LABELS
        assert "calm" in DEFAULT_MOOD_LABELS
        assert "happy" in DEFAULT_MOOD_LABELS

    def test_instrument_labels(self):
        """Test instrument label coverage"""
        assert len(INSTRUMENT_LABELS) >= 10
        assert "guitar" in INSTRUMENT_LABELS
        assert "piano" in INSTRUMENT_LABELS
        assert "drums" in INSTRUMENT_LABELS

    def test_genre_labels(self):
        """Test genre label coverage"""
        assert len(GENRE_LABELS) >= 15
        assert "rock" in GENRE_LABELS
        assert "jazz" in GENRE_LABELS
        assert "electronic" in GENRE_LABELS

    def test_audio_constants(self):
        """Test audio processing constants"""
        assert CLAP_SAMPLE_RATE == 48000
        assert CLAP_DURATION == 10.0
        assert CLAP_EMBEDDING_DIM == 512


# Integration tests (require actual model files)
@pytest.mark.skipif(
    not Path("./models/clap_audio_encoder.onnx").exists(),
    reason="CLAP model not available"
)
class TestCLAPIntegration:
    """Integration tests with actual CLAP model"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with real model"""
        return CLAPAnalyzer(lazy_load=False)

    def test_real_model_loading(self, analyzer):
        """Test loading actual ONNX model"""
        assert analyzer.is_ready
        assert analyzer.active_provider in ['DmlExecutionProvider', 'CPUExecutionProvider']

    @pytest.mark.skipif(
        not Path("./test_audio/sample.mp3").exists(),
        reason="Test audio not available"
    )
    def test_real_audio_encoding(self, analyzer):
        """Test encoding real audio file"""
        embedding = analyzer.encode_audio("./test_audio/sample.mp3")

        assert embedding is not None
        assert embedding.shape == (CLAP_EMBEDDING_DIM,)
        assert embedding.dtype == np.float32

        # Check normalization
        norm = np.linalg.norm(embedding)
        assert 0.99 <= norm <= 1.01
