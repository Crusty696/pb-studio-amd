from __future__ import annotations

import numpy as np
import pytest

from pb_studio.audio.structure_analyzer import StructureAnalyzer


def _scalar_checkerboard_reference(
    recurrence: np.ndarray,
    kernel_size: int,
) -> np.ndarray:
    """Reference for the established diagonal-window implementation."""
    n = recurrence.shape[0]
    half_kernel = kernel_size // 2
    kernel = np.ones((kernel_size, kernel_size))
    kernel[:half_kernel, :half_kernel] = -1
    kernel[half_kernel:, half_kernel:] = -1
    novelty = np.zeros(n)

    for center in range(half_kernel, n - half_kernel):
        start = center - half_kernel
        end = center + half_kernel
        window = recurrence[start:end, start:end]
        if window.shape == kernel.shape:
            novelty[center] = np.abs(np.sum(window * kernel))

    return novelty


@pytest.mark.parametrize("kernel_size", [2, 4, 6, 8])
def test_checkerboard_novelty_matches_scalar_reference_for_even_kernels(
    kernel_size: int,
) -> None:
    recurrence = np.random.default_rng(74).normal(size=(17, 17))

    actual = StructureAnalyzer()._checkerboard_novelty(
        recurrence,
        kernel_size,
    )

    np.testing.assert_array_equal(
        actual,
        _scalar_checkerboard_reference(recurrence, kernel_size),
    )


@pytest.mark.parametrize("kernel_size", [1, 3, 5])
def test_checkerboard_novelty_matches_scalar_reference_for_odd_small_kernels(
    kernel_size: int,
) -> None:
    recurrence = np.random.default_rng(75).normal(size=(12, 12))

    actual = StructureAnalyzer()._checkerboard_novelty(
        recurrence,
        kernel_size,
    )

    np.testing.assert_array_equal(
        actual,
        _scalar_checkerboard_reference(recurrence, kernel_size),
    )
    np.testing.assert_array_equal(actual, np.zeros(recurrence.shape[0]))


@pytest.mark.parametrize(
    ("matrix_size", "kernel_size"),
    [(3, 4), (4, 4), (5, 8), (12, 13)],
)
def test_checkerboard_novelty_returns_zeros_without_a_complete_window(
    matrix_size: int,
    kernel_size: int,
) -> None:
    recurrence = np.ones((matrix_size, matrix_size), dtype=np.float32)

    actual = StructureAnalyzer()._checkerboard_novelty(
        recurrence,
        kernel_size,
    )

    np.testing.assert_array_equal(actual, np.zeros(matrix_size))
