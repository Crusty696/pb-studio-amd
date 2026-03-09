"""
Moondream2 Vision-Language Model - PyTorch Implementation

This module provides image captioning and visual question answering
using Moondream2 directly via PyTorch/Transformers.

Model: vikhyatk/moondream2
"""

import logging
import os
import shutil
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

    def _get_local_snapshot_dir(self) -> Optional[Path]:
        """Return a local moondream snapshot if one is already cached."""
        if Path(self.model_id).exists():
            return Path(self.model_id)

        snapshot_root = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--vikhyatk--moondream2"
            / "snapshots"
        )
        if not snapshot_root.exists():
            return None

        snapshots = sorted(p for p in snapshot_root.iterdir() if p.is_dir())
        return snapshots[-1] if snapshots else None

    def _prepare_offline_runtime(self, snapshot_dir: Optional[Path]) -> Optional[Path]:
        """Configure local-only HuggingFace runtime and prewarm dynamic modules."""
        try:
            from pb_studio.config_manager import ConfigManager

            temp_dir = Path(ConfigManager().get("paths", {}).get("temp_dir", "./temp"))
        except Exception:
            temp_dir = Path("./temp")

        modules_root = temp_dir / "hf_modules"
        modules_root.mkdir(parents=True, exist_ok=True)

        os.environ["HF_MODULES_CACHE"] = str(modules_root.resolve())
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        if snapshot_dir is None or not snapshot_dir.exists():
            return snapshot_dir

        cache_pkg_dir = modules_root / "transformers_modules" / f"_{snapshot_dir.name}"
        cache_pkg_dir.mkdir(parents=True, exist_ok=True)

        for py_file in snapshot_dir.glob("*.py"):
            target = cache_pkg_dir / py_file.name
            if not target.exists() or py_file.stat().st_mtime > target.stat().st_mtime:
                shutil.copy2(py_file, target)

        init_file = cache_pkg_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="ascii")

        return snapshot_dir

    def _install_safe_generation_patch(self):
        """Force greedy decoding for moondream remote-code paths that sample unstable probabilities."""
        if self.model is None or getattr(self.model, "_pbstudio_safe_generation", False):
            return

        model = self.model

        def _safe_answer_question(
            image_embeds,
            question,
            tokenizer=None,
            chat_history="",
            result_queue=None,
            max_new_tokens=256,
            **kwargs
        ):
            del tokenizer, chat_history
            settings = kwargs.pop("settings", None) or {
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": max_new_tokens,
            }
            answer = model.query(image_embeds, question, settings=settings)["answer"].strip()
            if result_queue is not None:
                result_queue.put(answer)
            return answer

        def _safe_batch_answer(images, prompts, tokenizer=None, **kwargs):
            del tokenizer
            answers = []
            for image, prompt in zip(images, prompts):
                answers.append(_safe_answer_question(image, prompt, **kwargs))
            return answers

        model.answer_question = _safe_answer_question
        model.batch_answer = _safe_batch_answer
        model._pbstudio_safe_generation = True

    def load(self) -> bool:
        """Load the Moondream model."""
        if self._loaded:
            return True

        try:
            snapshot_dir = self._prepare_offline_runtime(self._get_local_snapshot_dir())
            model_source = str(snapshot_dir) if snapshot_dir is not None else self.model_id

            from transformers import AutoModelForCausalLM, AutoTokenizer
            from transformers.modeling_utils import PreTrainedModel
            import inspect
            import torch.nn.functional as F

            logger.info(f"Loading Moondream model: {model_source}")
            logger.info("This may take a moment (model is ~2GB)...")

            # transformers>=5 expects this attribute during finalize/tied-weight init,
            # but current moondream remote-code builds may not define it.
            if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
                PreTrainedModel.all_tied_weights_keys = {}

            # Some moondream remote-code revisions call scaled_dot_product_attention(..., enable_gqa=...)
            # but our local torch build may not expose that kwarg yet. Patch it compatibly.
            try:
                sdpa_params = inspect.signature(F.scaled_dot_product_attention).parameters
            except (TypeError, ValueError):
                sdpa_params = {}

            if "enable_gqa" not in sdpa_params:
                original_sdpa = F.scaled_dot_product_attention

                def _compat_sdpa(*args, **kwargs):
                    kwargs.pop("enable_gqa", None)
                    return original_sdpa(*args, **kwargs)

                F.scaled_dot_product_attention = _compat_sdpa

            self.tokenizer = AutoTokenizer.from_pretrained(
                model_source,
                trust_remote_code=True,
                local_files_only=snapshot_dir is not None,
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                model_source,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                local_files_only=snapshot_dir is not None,
            )
            self.model.to(self.device)
            self.model.eval()
            self._install_safe_generation_patch()

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
