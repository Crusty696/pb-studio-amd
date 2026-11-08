"""CPU-only SigLIP input contract; no sessions, model loading or app state.

The oracle is the installed Hugging Face processor using the local model's
processor configuration, independent of PB's preprocessing constants.
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest
from transformers.models.siglip.image_processing_pil_siglip import SiglipImageProcessorPil


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "t055_siglip_product", ROOT / "src/pb_studio/ai/siglip_wrapper.py"
)
product = importlib.util.module_from_spec(spec)
spec.loader.exec_module(product)


@pytest.fixture
def wrapper():
    # Bypass constructor/configuration and prohibit implicit model initialization.
    instance = object.__new__(product.SigLIPWrapper)
    instance._initialized = True
    return instance


@pytest.fixture
def reference_processor():
    config = json.loads(
        (ROOT / "models/siglip_tokenizer/preprocessor_config.json").read_text()
    )
    # Match the product's PIL backend; torchvision's bicubic resize has slightly
    # different rounding and is not a pixel-exact oracle for PIL interpolation.
    return SiglipImageProcessorPil(**config)


def patterned_image(mode="RGB"):
    y, x = np.indices((91, 137))
    pixels = np.stack(
        [(x * 7 + y * 3) % 256, (x * 13 + y) % 256, (y * 11) % 256],
        axis=-1,
    ).astype(np.uint8)
    return Image.fromarray(pixels).convert(mode)


@pytest.mark.parametrize("level,expected", [(0, -1.0), (255, 1.0)])
def test_black_and_white_follow_siglip_range(wrapper, level, expected):
    actual = wrapper.preprocess_image(Image.new("RGB", (31, 47), (level,) * 3))
    assert actual.shape == (1, 3, 384, 384)
    assert actual.dtype == np.float32
    np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=0)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L"])
def test_pattern_matches_local_huggingface_processor(wrapper, reference_processor, mode):
    image = patterned_image(mode)
    expected = reference_processor(images=image.convert("RGB"), return_tensors="np")[
        "pixel_values"
    ]
    actual = wrapper.preprocess_image(image)
    np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=0)


class CapturingSession:
    def __init__(self):
        self.inputs = []

    def get_inputs(self):
        return [SimpleNamespace(name="pixel_values")]

    def run(self, output_names, feed):
        values = feed["pixel_values"]
        self.inputs.append(values.copy())
        # Successful synthetic output prevents sequential fallback masking a bug.
        return [np.ones((len(values), 1152), dtype=np.float32)]


def test_batch_input_matches_independent_processor(wrapper, reference_processor):
    images = [
        Image.new("RGB", (31, 47), "black"),
        Image.new("RGB", (53, 29), "white"),
        patterned_image(),
        patterned_image("RGBA"),
    ]
    session = CapturingSession()
    wrapper.vision_session = session
    encoded = wrapper.encode_images_batch(images)
    assert encoded.shape == (4, 1152)
    assert len(session.inputs) == 1
    expected = reference_processor(
        images=[image.convert("RGB") for image in images], return_tensors="np"
    )["pixel_values"]
    assert session.inputs[0].dtype == np.float32
    np.testing.assert_allclose(session.inputs[0], expected, atol=1e-6, rtol=0)


def test_single_encode_passes_processor_tensor_to_session(wrapper, reference_processor):
    image = patterned_image()
    session = CapturingSession()
    wrapper.vision_session = session
    encoded = wrapper.encode_image(image)
    assert encoded.shape == (1152,)
    assert len(session.inputs) == 1
    expected = reference_processor(images=image, return_tensors="np")["pixel_values"]
    np.testing.assert_allclose(session.inputs[0], expected, atol=1e-6, rtol=0)
