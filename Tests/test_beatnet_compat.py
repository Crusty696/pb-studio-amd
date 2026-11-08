"""Regression of madmom's ragged (path, score) selection, no media/GPU needed."""

from types import SimpleNamespace

import numpy as np
import pytest

from pb_studio.audio import beat_detector
from pb_studio.audio import beatnet_compat as compat

pytestmark = pytest.mark.skipif(
    not beat_detector.BEATNET_AVAILABLE, reason="Optional BeatNet/madmom absent"
)


def _decoder(scores=(-30., -20., -10.), *, correct=False, threshold=0.):
    from madmom.features.downbeats import DBNDownBeatTrackingProcessor

    decoder = DBNDownBeatTrackingProcessor.__new__(DBNDownBeatTrackingProcessor)
    decoder.hmms = [
        SimpleNamespace(
            transition_model=SimpleNamespace(state_space=SimpleNamespace(
                state_positions=np.arange(8) % meter
            )),
            observation_model=SimpleNamespace(pointers=np.array([1, 1, 0, 1, 1, 0, 1, 1])),
        )
        for meter in (2, 3, 4)
    ]
    decoder.correct, decoder.threshold, decoder.fps = correct, threshold, 10.
    decoder.beats_per_bar = np.array([2, 3, 4])

    def decode_map(fn, pairs):
        pairs = list(pairs)
        assert [pair[0] for pair in pairs] == decoder.hmms
        size = len(pairs[0][1])
        return [(np.arange(size), score) for score in scores]

    decoder.map = decode_map
    return decoder


def _adapt(decoder, mode="offline"):
    estimator = SimpleNamespace(inference_model="DBN", mode=mode, estimator=decoder)
    return compat.adapt_beatnet_dbn(estimator).estimator


def test_installed_original_reproduces_ragged_error_then_local_adapter_succeeds():
    decoder = _decoder()
    activations = np.full((8, 2), .3)
    original = type(decoder).process
    original_asarray = np.asarray
    with pytest.raises(ValueError, match="inhomogeneous|setting an array element"):
        decoder(activations)
    actual = _adapt(decoder)(activations)
    np.testing.assert_array_equal(actual[:, 1], [2, 3, 4, 1, 2, 3, 4])
    assert type(decoder).process is original
    assert np.asarray is original_asarray
    with pytest.raises(ValueError, match="inhomogeneous|setting an array element"):
        _decoder()(activations)  # another instance remains untouched


@pytest.mark.parametrize("scores,meter", [
    ((-1, -2, -3), 2), ((-3, -1, -2), 3), ((-3, -2, -1), 4),
    ((-1, -1, -1), 2), ((-3, -1, -1), 3),
])
def test_best_scalar_score_and_first_tie_preserve_meter(scores, meter):
    output = _adapt(_decoder(scores))(np.full((8, 2), .3), ignored=True)
    np.testing.assert_allclose(output[:, 0], np.arange(1, 8) / 10.)
    np.testing.assert_array_equal(output[:, 1], np.arange(1, 8) % meter + 1)


@pytest.mark.parametrize("activations,threshold", [
    (np.empty((0, 2)), 0.), (np.zeros((8, 2)), 0.),
    (np.full((8, 2), .1), .5),
    (np.array([[.8, .8], [0., 0.]]), .5),
])
def test_empty_silent_and_thresholded_inputs_preserve_upstream(activations, threshold):
    decoder = _decoder(threshold=threshold)
    upstream = decoder(activations)
    actual = _adapt(decoder)(activations)
    np.testing.assert_array_equal(actual, upstream)
    assert actual.shape == (0, 2)


def test_threshold_offset_is_retained():
    values = np.array([[0, 0], [0, 0], [.6, .1], [.7, .1], [.6, .1], [0, 0]])
    actual = _adapt(_decoder(threshold=.5))(values)
    np.testing.assert_allclose(actual, [[.3, 2], [.4, 3]])


def test_corrected_peaks_include_first_and_last_beat_regions():
    values = np.array([[.1, .2], [.8, .2], [.1, .1], [.7, .2],
                       [.1, .2], [.1, .1], [.1, .2], [.1, .9]])
    actual = _adapt(_decoder(correct=True))(values)
    np.testing.assert_allclose(actual, [[.1, 2], [.3, 4], [.7, 4]])


def test_actual_hmm_decoding_runs_with_three_meter_candidates():
    from madmom.features.downbeats import DBNDownBeatTrackingProcessor
    decoder = DBNDownBeatTrackingProcessor([2, 3, 4], fps=10, min_bpm=120,
                                          max_bpm=120, num_tempi=1)
    activations = np.full((80, 2), .01)
    activations[::5, 0] = .8
    activations[::20, 0] = .01
    activations[::20, 1] = .9
    output = _adapt(decoder)(activations)
    assert output.shape[1] == 2 and len(output) > 0
    assert np.isfinite(output).all()
    assert np.all(np.diff(output[:, 0]) > 0)


def test_pf_is_untouched_and_unreviewed_dbn_fails(monkeypatch):
    pf = SimpleNamespace(inference_model="PF", estimator=object())
    assert compat.adapt_beatnet_dbn(pf) is pf
    monkeypatch.setattr(compat, "version", lambda name: "future-version")
    with pytest.raises(RuntimeError, match="reviewed madmom"):
        _adapt(_decoder())


def test_unknown_decoder_type_fails_without_rewriting_it():
    decoder = SimpleNamespace(process=lambda value: value)
    with pytest.raises(TypeError, match="DBNDownBeatTrackingProcessor"):
        _adapt(decoder)


@pytest.mark.parametrize("mode,inference", [("offline", "DBN"), ("online", "DBN"), ("online", "PF")])
def test_detector_initialization_adapts_only_dbn_and_keeps_cpu(monkeypatch, mode, inference):
    decoder = _decoder() if inference == "DBN" else object()
    estimator = SimpleNamespace(inference_model=inference, estimator=decoder)
    calls = []
    def factory(*args, **kwargs):
        calls.append((args, kwargs))
        return estimator
    monkeypatch.setattr(beat_detector, "BeatNet", factory)
    detector = beat_detector.BeatDetector(mode=mode, inference_model=inference)
    assert detector._init_estimator()
    assert detector._init_estimator() and len(calls) == 1
    assert calls[0][1]["device"] == "cpu"
    if inference == "DBN":
        assert decoder.process.__func__ is compat._process_dbn_numpy126
    else:
        assert estimator.estimator is decoder


def test_failed_adaptation_is_not_cached_and_existing_fallback_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(beat_detector, "BeatNet", lambda *args, **kwargs:
                        SimpleNamespace(inference_model="DBN", estimator=object()))
    monkeypatch.setattr(beat_detector.librosa, "get_duration", lambda **kwargs: 30.)
    detector = beat_detector.BeatDetector(mode="offline", inference_model="DBN")
    monkeypatch.setattr(detector, "_detect_beats_librosa", lambda *args, **kwargs: [1., 2.])
    assert detector.detect_beats_with_downbeats("unused.wav") == ([1., 2.], [])
    assert detector._estimator is None
    assert "Initialisierung fehlgeschlagen" in caplog.text


def test_analyzer_uses_same_adapter_and_cpu(monkeypatch):
    from pb_studio.audio.analyzer import AudioAnalyzer
    from pb_studio import config_manager
    monkeypatch.setattr(config_manager, "ConfigManager", lambda: SimpleNamespace(ffmpeg_path="ffmpeg"))
    decoder = _decoder()
    def factory(*args, **kwargs):
        assert kwargs["device"] == "cpu"
        return SimpleNamespace(inference_model="DBN", estimator=decoder)
    monkeypatch.setattr(beat_detector, "BeatNet", factory)
    analyzer = AudioAnalyzer()
    assert analyzer.model_loaded
    assert analyzer.estimator.estimator.process.__func__ is compat._process_dbn_numpy126
