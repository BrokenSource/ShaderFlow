from __future__ import annotations

import functools
import multiprocessing
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Literal, Optional

import numpy
import PIL
import PIL.ImageFilter
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

import Broken
from Broken import (
    BrokenEnum,
    BrokenResolution,
    BrokenSpinner,
    BrokenTorch,
    SameTracker,
    image_hash,
    log,
    shell,
)
from Broken.Loaders import LoadableImage, LoaderImage

if TYPE_CHECKING:
    import diffusers
    import torch

# -------------------------------------------------------------------------------------------------|

class DepthEstimatorBase(BaseModel, ABC):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True
    )

    flavor: str = Field(default="any")

    lock: Optional[Lock] = Field(default_factory=Lock, exclude=True)
    """Calling PyTorch in a multi-threaded environment isn't safe, so lock before any inference"""

    cache_path: Path = Field(default=Broken.PROJECT.DIRECTORIES.CACHE/"DepthEstimator", exclude=True)
    """Path where the depth map will be cached. Broken.PROJECT is the current working project"""

    @property
    def device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def normalize(self, array: numpy.ndarray) -> numpy.ndarray:
        return (array - array.min()) / ((array.max() - array.min()) or 1)

    def load_torch(self) -> None:
        global torch
        BrokenTorch.manage(Broken.PROJECT.PACKAGE)
        import torch

    loaded: SameTracker = Field(default_factory=SameTracker, exclude=True)
    """Keeps track of the current loaded model name, to avoid reloading"""

    def load_model(self) -> None:
        if self.loaded(self.flavor):
            return
        self._load_model()

    @functools.wraps(load_model)
    @abstractmethod
    def _load_model(self) -> None:
        ...

    def estimate(self,
        image: LoadableImage,
        cache: bool=True
    ) -> numpy.ndarray:

        # Load image and find expected cache path
        image = numpy.array(LoaderImage(image).convert("RGB"))
        cached_image = self.cache_path/f"{image_hash(image)}-{self.__class__.__name__}-{self.flavor}.png"
        cached_image.parent.mkdir(parents=True, exist_ok=True)

        # Load cached estimation if found
        if (cache and cached_image.exists()):
            depth = numpy.array(Image.open(cached_image))
        else:
            self.load_torch()
            self.load_model()
            with self.lock, BrokenSpinner(f"Estimating Depthmap (Torch: {self.device})"):
                torch.set_num_threads(max(4, multiprocessing.cpu_count()//2))
                depth = (self._estimate(image) * 2**16).astype(numpy.uint16)

        Image.fromarray(depth).save(cached_image)
        return depth / 2**16

    @functools.wraps(estimate)
    @abstractmethod
    def _estimate(self):
        """The implementation shall return a normalized numpy f32 array of the depth map"""
        ...

# -------------------------------------------------------------------------------------------------|

class DepthAnything(DepthEstimatorBase):
    model: Any = None
    processor: Any = None
    flavor: Literal["small", "base", "large"] = Field(default="base")

    def _load_model(self) -> None:
        import transformers
        HUGGINGFACE_MODEL = (f"LiheYoung/depth-anything-{self.flavor}-hf")
        self.processor = transformers.AutoImageProcessor.from_pretrained(HUGGINGFACE_MODEL)
        self.model = transformers.AutoModelForDepthEstimation.from_pretrained(HUGGINGFACE_MODEL)
        self.model.to(self.device)

    def _estimate(self, image: numpy.ndarray) -> numpy.ndarray:
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.no_grad():
            depth = self.model(**inputs).predicted_depth

        # Normalize image and "fatten" the edges, it's too accurate :^)
        depth = depth.squeeze(1).cpu().numpy()[0]
        depth = self.normalize(depth)
        depth = PIL.Image.fromarray(depth)
        depth = depth.filter(PIL.ImageFilter.MaxFilter(5))
        return numpy.array(depth).astype(numpy.float32)

# -------------------------------------------------------------------------------------------------|

class ZoeDepth(DepthEstimatorBase):
    model: Any = None
    flavor: Literal["n", "k", "nk"] = Field(default="n")

    def _load_model(self) -> None:
        try:
            import timm
        except ImportError:
            shell(sys.executable, "-m", "pip", "install", "timm==0.6.7", "--no-deps")

        self.model = torch.hub.load(
            "isl-org/ZoeDepth", f"ZoeD_{self.flavor.upper()}",
            pretrained=True, trust_repo=True
        ).to(self.device)

    # Downscale for the largest component to be 512 pixels (Zoe precision), invert for 0=infinity
    def _estimate(self, image: numpy.ndarray) -> numpy.ndarray:
        depth = Image.fromarray(1 - self.normalize(self.model.infer_pil(image)))
        new = BrokenResolution.fit(old=depth.size, max=(512, 512), ar=depth.size[0]/depth.size[1])
        return numpy.array(depth.resize(new, resample=Image.LANCZOS)).astype(numpy.float32)

# -------------------------------------------------------------------------------------------------|

class Marigold(DepthEstimatorBase):
    model: Any = None

    def _load_model(self) -> None:
        try:
            import accelerate
            import diffusers
            import matplotlib
        except ImportError:
            shell(sys.executable, "-m", "pip", "install",
                "diffusers", "accelerate", "matplotlib")

        from diffusers import DiffusionPipeline

        self.model = DiffusionPipeline.from_pretrained(
            "prs-eth/marigold-v1-0",
            custom_pipeline="marigold_depth_estimation",
            torch_dtype=torch.float16,
            variant="fp16",
        ).to(self.device)

    def _estimate(self, image: numpy.ndarray) -> numpy.ndarray:
        return (1 - self.model(
            Image.fromarray(image),
            denoising_steps=10,
            ensemble_size=10,
            match_input_res=False,
            show_progress_bar=True,
            color_map=None,
            processing_res=792,
        ).depth_np)

# -------------------------------------------------------------------------------------------------|