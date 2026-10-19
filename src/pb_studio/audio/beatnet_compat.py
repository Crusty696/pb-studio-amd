"""Instance-local madmom 0.16.1 DBN compatibility for NumPy 1.26.

The decoder below is adapted from DBNDownBeatTrackingProcessor.process:
https://github.com/CPJKU/madmom/blob/v0.16.1/madmom/features/downbeats.py
Only score selection and the removed np.int spelling differ. In particular,
meter candidates, thresholding, correction and first-maximum ties are retained.
No installed package, NumPy function or madmom class is modified.

Copyright (c) 2012-2014 Department of Computational Perception,
Johannes Kepler University, Linz, Austria and Austrian Research Institute for
Artificial Intelligence (OFAI), Vienna, Austria. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from importlib.metadata import version
from copy import deepcopy
from itertools import repeat
from threading import Lock
from types import MethodType

import numpy as np


_file_state_init_lock = Lock()


def prepare_beatnet_file_state(estimator):
    """Capture fresh decoder state once, before publishing a file estimator.

    BeatNet's ``online``, ``offline`` and ``realtime`` modes each process a
    whole file. Microphone ``stream`` mode keeps its frame history. PF remains
    stochastic: no process-wide random generator is reseeded.
    """
    if getattr(estimator, "mode", None) not in ("online", "offline", "realtime"):
        return estimator
    with _file_state_init_lock:
        if not hasattr(estimator, "_pb_file_state"):
            initial_decoder = (deepcopy(estimator.estimator)
                               if estimator.inference_model == "PF" else None)
            estimator._pb_file_state = (Lock(), initial_decoder)
    return estimator


def _reset_file_recurrent_state(estimator):
    model = estimator.model
    parameter = next(model.parameters())
    if parameter.device.type != "cpu":
        raise RuntimeError("PB BeatNet file analysis requires CPU")
    lstm = model.lstm
    layers = lstm.num_layers * (2 if lstm.bidirectional else 1)
    model.hidden = parameter.new_zeros((layers, 1, lstm.hidden_size))
    model.cell = parameter.new_zeros((layers, 1, lstm.hidden_size))


def process_beatnet_file(estimator, audio_path):
    """Analyze one independent file atomically, with no preceding-file history.

    Keep the loaded network/weights, reset its LSTM and replace a PF decoder
    with its original snapshot. Clear state even after inference failure. The
    lock belongs to the estimator, covering all callers sharing that instance.
    DBN Viterbi and LOG_SPECT already reset their file-local buffers upstream.
    """
    prepare_beatnet_file_state(estimator)
    if getattr(estimator, "mode", None) not in ("online", "offline", "realtime"):
        return estimator.process(audio_path)
    lock, initial_decoder = estimator._pb_file_state
    with lock:
        _reset_file_recurrent_state(estimator)
        if initial_decoder is not None:
            estimator.estimator = deepcopy(initial_decoder)
        try:
            output = estimator.process(audio_path)
            # Some decoders return an internal array. Detach before unlocking.
            return output.copy() if isinstance(output, np.ndarray) else deepcopy(output)
        finally:
            _reset_file_recurrent_state(estimator)
            if initial_decoder is not None:
                estimator.estimator = deepcopy(initial_decoder)


def _process_dbn_numpy126(self, activations, **kwargs):
    """Retain madmom's decoder, selecting scalar scores without ragged arrays."""
    from madmom.features.downbeats import _process_dbn

    first = 0
    if self.threshold:
        idx = np.nonzero(activations >= self.threshold)[0]
        # Preserve upstream's frame-zero-only threshold behavior as well.
        if idx.any():
            first = max(first, np.min(idx))
            last = min(len(activations), np.max(idx) + 1)
        else:
            last = first
        activations = activations[first:last]
    if not activations.any():
        return np.empty((0, 2))

    results = list(self.map(_process_dbn, zip(self.hmms, repeat(activations))))
    # A result is (state_path_array, scalar_log_probability), not a matrix.
    best = int(np.argmax([score for _, score in results]))
    path, _ = results[best]
    st = self.hmms[best].transition_model.state_space
    om = self.hmms[best].observation_model
    positions = st.state_positions[path]
    beat_numbers = positions.astype(int) + 1
    if self.correct:
        beats = np.empty(0, dtype=int)
        beat_range = om.pointers[path] >= 1
        idx = np.nonzero(np.diff(beat_range.astype(int)))[0] + 1
        if beat_range[0]:
            idx = np.r_[0, idx]
        if beat_range[-1]:
            idx = np.r_[idx, beat_range.size]
        if idx.any():
            for left, right in idx.reshape((-1, 2)):
                peak = np.argmax(activations[left:right]) // 2 + left
                beats = np.hstack((beats, peak))
    else:
        beats = np.nonzero(np.diff(beat_numbers))[0] + 1
    return np.vstack(((beats + first) / float(self.fps), beat_numbers[beats])).T


def adapt_beatnet_dbn(estimator):
    """Adapt this BeatNet instance only; PF and upstream classes stay intact.

    Fail visibly on an unreviewed DBN implementation instead of copying old
    decoding semantics into a future madmom version. Callers retain their
    existing logged initialization failure / librosa fallback behavior.
    """
    if estimator.inference_model != "DBN":
        return estimator
    from madmom.features.downbeats import DBNDownBeatTrackingProcessor

    if version("madmom") != "0.16.1":
        raise RuntimeError("BeatNet DBN adapter requires reviewed madmom 0.16.1")
    decoder = estimator.estimator
    if type(decoder) is not DBNDownBeatTrackingProcessor:
        raise TypeError("BeatNet DBN adapter requires DBNDownBeatTrackingProcessor")
    decoder.process = MethodType(_process_dbn_numpy126, decoder)
    return estimator
