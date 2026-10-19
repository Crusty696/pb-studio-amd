"""File boundaries reset BeatNet state without changing streaming semantics."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time

import numpy as np
import pytest
import torch

from pb_studio.audio import beatnet_compat as compat


class StatefulModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = torch.nn.LSTM(1, 3, 2, batch_first=True).double()
        self.hidden = torch.zeros(2, 1, 3, dtype=torch.float64)
        self.cell = self.hidden.clone()


class Estimator:
    def __init__(self, mode="offline", inference="DBN"):
        self.mode, self.inference_model = mode, inference
        self.model = StatefulModel()
        self.estimator = SimpleNamespace(counter=-1, path=[], particles=np.array([1, 2]))

    def process(self, source):
        prior = float(self.model.hidden.sum())
        self.model.hidden += 1
        self.model.cell += 2
        self.estimator.counter += 1
        self.estimator.path.append(source)
        self.estimator.particles += 1
        time.sleep(.01)
        if source == "fail":
            raise ValueError("decode failure")
        return prior, self.estimator.counter, len(self.estimator.path)


def test_unwrapped_estimator_reproduces_state_leak():
    estimator = Estimator()
    assert estimator.process("A") != estimator.process("A")


@pytest.mark.parametrize("mode,inference", [("offline", "DBN"), ("online", "DBN"), ("online", "PF"), ("realtime", "PF")])
def test_file_reset_repeated_and_interleaved(mode, inference):
    estimator = Estimator(mode, inference)
    compat.prepare_beatnet_file_state(estimator)
    outputs = [compat.process_beatnet_file(estimator, name) for name in ["A", "B", "A"]]
    assert all(value[0] == 0 for value in outputs)
    if inference == "PF":
        assert outputs == [(0., 0, 1)] * 3
    assert not estimator.model.hidden.any() and not estimator.model.cell.any()
    assert estimator.model.hidden.dtype == torch.float64
    assert estimator.model.hidden.device.type == "cpu"


def test_failure_cleans_state_and_next_file_is_fresh():
    estimator = Estimator(inference="PF")
    with pytest.raises(ValueError, match="decode failure"):
        compat.process_beatnet_file(estimator, "fail")
    assert not estimator.model.hidden.any() and not estimator.model.cell.any()
    assert compat.process_beatnet_file(estimator, "A") == (0., 0, 1)


def test_shared_estimator_serializes_reset_inference_and_cleanup():
    estimator = Estimator(inference="PF")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda value: compat.process_beatnet_file(estimator, value), range(8)))
    assert results == [(0., 0, 1)] * 8


def test_microphone_stream_state_is_not_reset():
    estimator = Estimator(mode="stream", inference="PF")
    first = compat.process_beatnet_file(estimator, "A")
    second = compat.process_beatnet_file(estimator, "B")
    assert first != second
    assert not hasattr(estimator, "_pb_file_state")


def test_real_beatnet_pf_decoder_snapshot_restores_file_state_without_rewinding_rng():
    from BeatNet.BeatNet import BeatNet

    estimator = BeatNet(1, mode="realtime", inference_model="PF", plot=[], thread=False, device="cpu")
    compat.prepare_beatnet_file_state(estimator)
    lock, baseline = estimator._pb_file_state
    before = {
        "counter": baseline.counter,
        "path": baseline.path.copy(),
        "particles": baseline.particles.copy(),
        "down_particles": baseline.down_particles.copy(),
    }
    rng_before = np.random.get_state()

    def corrupt_real_decoder(_audio_path):
        np.random.random()
        estimator.estimator.counter += 123
        estimator.estimator.path = np.append(estimator.estimator.path, [[42.0, 2.0]], axis=0)
        estimator.estimator.particles[:] = 0
        estimator.estimator.down_particles[:] = 0
        estimator.model.hidden += 1
        estimator.model.cell += 1
        return np.array([[42.0, 2.0]])

    estimator.process = corrupt_real_decoder
    result = compat.process_beatnet_file(estimator, "fixture.wav")
    rng_after = np.random.get_state()

    assert result.tolist() == [[42.0, 2.0]]
    assert estimator.estimator.counter == before["counter"]
    np.testing.assert_array_equal(estimator.estimator.path, before["path"])
    np.testing.assert_array_equal(estimator.estimator.particles, before["particles"])
    np.testing.assert_array_equal(estimator.estimator.down_particles, before["down_particles"])
    assert not estimator.model.hidden.any() and not estimator.model.cell.any()
    # One explicit draw advances global NumPy RNG once; reset code does not
    # restore or reseed it, preserving PF's stochastic contract.
    assert rng_before[2:] != rng_after[2:]
