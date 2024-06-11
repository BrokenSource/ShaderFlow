from __future__ import annotations

import functools
import multiprocessing
import os
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
        with BrokenSpinner(text="Importing PyTorch..."):
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
                depth = self._estimate(image)
            depth = (self.normalize(depth) * 2**16).astype(numpy.uint16)
            Image.fromarray(depth).save(cached_image)
        return self.normalize(self._post_processing(depth))

    @functools.wraps(estimate)
    @abstractmethod
    def _estimate(self):
        """The implementation shall return a normalized numpy f32 array of the depth map"""
        ...

    @abstractmethod
    def _post_processing(self, depth: numpy.ndarray) -> numpy.ndarray:
        """A step to apply post processing on the depth map if needed"""
        return depth

# -------------------------------------------------------------------------------------------------|

class DepthAnything(DepthEstimatorBase):
    flavor: Literal["small", "base", "large"] = Field(default="base")
    processor: Any = None
    model: Any = None

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
        return depth.squeeze(1).cpu().numpy()[0]

    def _post_processing(self, depth: numpy.ndarray) -> numpy.ndarray:
        from scipy.ndimage import gaussian_filter, maximum_filter
        depth = maximum_filter(input=depth, size=5)
        depth = gaussian_filter(input=depth, sigma=0.3)
        return depth

# -------------------------------------------------------------------------------------------------|

class DepthAnythingV2(DepthEstimatorBase):
    flavor: Literal["small", "base", "large", "giga"] = Field(default="base")
    model: Any = None

    def _load_model(self) -> None:

        # Download Depth-Anything-v2 from source
        import site
        source = Path(site.getsitepackages()[-1])/"DepthAnything"
        os.environ["PATH"] = f"{source}:{os.environ['PATH']}"
        try:
            import depth_anything_v2
        except ImportError:
            shell("git", "clone", "https://huggingface.co/spaces/LiheYoung/Depth-Anything-V2.git", source)
            (source/"depth_anything_v2").rename(source.parent/"depth_anything_v2")

        from depth_anything_v2.dpt import DepthAnythingV2
        from huggingface_hub import hf_hub_download

        # Load layers configuration dictionary
        self.model = DepthAnythingV2(**dict(
            small=dict(encoder='vits', features=64,  out_channels=[48, 96, 192, 384]),
            base =dict(encoder='vitb', features=128, out_channels=[96, 192, 384, 768]),
            large=dict(encoder='vitl', features=256, out_channels=[256, 512, 1024, 1024]),
            giga =dict(encoder='vitg', features=384, out_channels=[1536, 1536, 1536, 1536])
        ).get(self.flavor))

        # Download models based on flavor
        self.model.load_state_dict(torch.load(hf_hub_download(
            repo_id="LiheYoung/Depth-Anything-V2-Checkpoints",
            filename=f"depth_anything_v2_vit{self.flavor[0]}.pth",
            repo_type="model"
        ), map_location="cpu"))

        self.model = self.model.to(self.device).eval()

    def _estimate(self, image: numpy.ndarray) -> numpy.ndarray:
        with torch.no_grad():
            image, _ = self.model.image2tensor(image, 512)
            return self.model.forward(image)[:, None][0, 0].cpu().numpy()

    def _post_processing(self, depth: numpy.ndarray) -> numpy.ndarray:
        from scipy.ndimage import gaussian_filter, maximum_filter
        depth = maximum_filter(input=depth, size=5)
        depth = gaussian_filter(input=depth, sigma=0.9)
        return depth

# -------------------------------------------------------------------------------------------------|

class ZoeDepth(DepthEstimatorBase):
    flavor: Literal["n", "k", "nk"] = Field(default="n")
    model: Any = None

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

    def _post_processing(self, depth: numpy.ndarray) -> numpy.ndarray:
        return depth

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

    def _post_processing(self, depth: numpy.ndarray) -> numpy.ndarray:
        return depth

# -------------------------------------------------------------------------------------------------|
