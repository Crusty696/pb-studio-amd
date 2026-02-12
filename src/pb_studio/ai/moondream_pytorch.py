"""
Moondream2 Vision-Language Model - PyTorch Implementation

This module provides image captioning and visual question answering
using Moondream2 directly via PyTorch/Transformers.

Model: vikhyatk/moondream2
"""

import logging
import torch
from PIL import Image
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger(__name__)


class MoondreamPyTorch:
    """
    Moondream2 Vision-Language Model using PyTorch.

    Provides:
    - Image captioning (describe what's in an image)
    - Visual question answering (answer questions about images)
    - Scene understanding

    Note: Runs on CPU for AMD systems. The model is ~2GB.
    """

    def __init__(self, model_id: str = "vikhyatk/moondream2", device: str = "cpu"):
        """
        Initialize Moondream.

        Args:
            model_id: HuggingFace model ID
            device: Device to run on ('cpu' for AMD systems)
        """
        self.model_id = model_id
        self.device = device
        self.model = None
        self.tokenizer = None
        self._loaded = False

        logger.info(f"MoondreamPyTorch initialized (device: {device})")

    def load(self) -> bool:
        """Load the Moondream model."""
        if self._loaded:
            return True

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info(f"Loading Moondream model: {self.model_id}")
            logger.info("This may take a moment (model is ~2GB)...")

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=True
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                trust_remote_code=True,
                torch_dtype=torch.float32
            )
            self.model.to(self.device)
            self.model.eval()

            self._loaded = True
            logger.info("[OK] Moondream model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load Moondream: {e}")
            return False

    def unload(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            self._loaded = False
            # AMD-only build - kein CUDA verfuegbar
            import gc
            gc.collect()
            logger.info("Moondream model unloaded")

    def _load_image(self, image_input: Union[str, Path, Image.Image]) -> Image.Image:
        """Load image from path or return PIL Image."""
        if isinstance(image_input, Image.Image):
            return image_input
        return Image.open(str(image_input)).convert("RGB")

    def caption(self, image: Union[str, Path, Image.Image]) -> str:
        """
        Generate a caption for an image.

        Args:
            image: Path to image or PIL Image

        Returns:
            Text description of the image
        """
        if not self._loaded and not self.load():
            return ""

        try:
            pil_image = self._load_image(image)

            with torch.no_grad():
                # Moondream's answer method for captioning
                caption = self.model.answer_question(
                    self.model.encode_image(pil_image),
                    "Describe this image in detail.",
                    self.tokenizer
                )

            return caption.strip()

        except Exception as e:
            logger.error(f"Caption generation failed: {e}")
            return ""

    def answer_question(
        self,
        image: Union[str, Path, Image.Image],
        question: str
    ) -> str:
        """
        Answer a question about an image.

        Args:
            image: Path to image or PIL Image
            question: Question to answer

        Returns:
            Answer text
        """
        if not self._loaded and not self.load():
            return ""

        try:
            pil_image = self._load_image(image)

            with torch.no_grad():
                encoded_image = self.model.encode_image(pil_image)
                answer = self.model.answer_question(
                    encoded_image,
                    question,
                    self.tokenizer
                )

            return answer.strip()

        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return ""

    def analyze_scene(self, image: Union[str, Path, Image.Image]) -> Dict[str, Any]:
        """
        Comprehensive scene analysis.

        Args:
            image: Path to image or PIL Image

        Returns:
            Dictionary with scene analysis results
        """
        if not self._loaded and not self.load():
            return {}

        try:
            pil_image = self._load_image(image)
            encoded_image = self.model.encode_image(pil_image)

            with torch.no_grad():
                # Get various aspects of the scene
                description = self.model.answer_question(
                    encoded_image,
                    "Describe this image in detail.",
                    self.tokenizer
                )

                mood = self.model.answer_question(
                    encoded_image,
                    "What is the mood or atmosphere of this image? Answer in 2-3 words.",
                    self.tokenizer
                )

                subjects = self.model.answer_question(
                    encoded_image,
                    "What are the main subjects or objects in this image? List them briefly.",
                    self.tokenizer
                )

                colors = self.model.answer_question(
                    encoded_image,
                    "What are the dominant colors in this image?",
                    self.tokenizer
                )

                motion = self.model.answer_question(
                    encoded_image,
                    "Is there any motion or action in this image? Describe briefly.",
                    self.tokenizer
                )

            return {
                "description": description.strip(),
                "mood": mood.strip(),
                "subjects": subjects.strip(),
                "colors": colors.strip(),
                "motion": motion.strip()
            }

        except Exception as e:
            logger.error(f"Scene analysis failed: {e}")
            return {}

    def get_tags(
        self,
        image: Union[str, Path, Image.Image],
        max_tags: int = 10
    ) -> List[str]:
        """
        Generate semantic tags for an image.

        Args:
            image: Path to image or PIL Image
            max_tags: Maximum number of tags

        Returns:
            List of semantic tags
        """
        if not self._loaded and not self.load():
            return []

        try:
            pil_image = self._load_image(image)

            with torch.no_grad():
                encoded_image = self.model.encode_image(pil_image)
                response = self.model.answer_question(
                    encoded_image,
                    f"List up to {max_tags} keywords or tags that describe this image. "
                    "Separate them with commas. Include objects, mood, colors, and style.",
                    self.tokenizer
                )

            # Parse tags from response
            tags = [tag.strip() for tag in response.split(",")]
            tags = [t for t in tags if t and len(t) < 50]  # Filter empty/long

            return tags[:max_tags]

        except Exception as e:
            logger.error(f"Tag generation failed: {e}")
            return []

    def batch_caption(
        self,
        images: List[Union[str, Path, Image.Image]]
    ) -> List[str]:
        """
        Generate captions for multiple images.

        Args:
            images: List of image paths or PIL Images

        Returns:
            List of captions
        """
        return [self.caption(img) for img in images]


# Convenience function
def get_moondream() -> MoondreamPyTorch:
    """Get a shared Moondream instance."""
    if not hasattr(get_moondream, '_instance'):
        get_moondream._instance = MoondreamPyTorch()
    return get_moondream._instance
