import multiprocessing
from typing import Any

import numpy
import PIL
import PIL.ImageFilter
from attr import define
from loguru import logger as log
from PIL import Image

import Broken
from Broken import BrokenSpinner, image_hash
from Broken.Loaders import LoadableImage, LoaderImage


@define
class Monocular:
    _model:     Any = None
    _processor: Any = None

    @property
    def device(self) -> str:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def estimate(self,
        image: LoadableImage,
        cache: bool=True,
    ) -> Image:
        """
        Estimate a Depth Map from an input image with a Monocular Depth Estimation model.

        Args:
            image: The input image to estimate the depth map from, path, url, PIL
            cache: Whether to cache the depth map to the cache directory

        Returns:
            The estimated depth map as a normalized PIL uint8 Image
        """

        # -----------------------------------------------------------------------------------------|
        # Caching

        # Load the image
        image = LoaderImage(image).convert("RGB")
        cache_path = Broken.PROJECT.DIRECTORIES.CACHE/f"{image_hash(image)}.depth.png"

        # If the depth map is cached, return it
        if (cache and cache_path.exists()):
            log.success(f"DepthMap already cached on ({cache_path})")
            return LoaderImage(cache_path).convert("L")
        log.info(f"DepthMap will be cached on ({cache_path})")

        # -----------------------------------------------------------------------------------------|
        # Estimating

        with BrokenSpinner("Importing PyTorch"):
            import torch
        with BrokenSpinner("Importing Transformers"):
            import transformers

        # Load the model
        if not all((self._model, self._processor)):
            HUGGINGFACE_MODEL = ("LiheYoung/depth-anything-base-hf")
            self._processor = transformers.AutoImageProcessor.from_pretrained(HUGGINGFACE_MODEL)
            self._model = transformers.AutoModelForDepthEstimation.from_pretrained(HUGGINGFACE_MODEL)
            self._model.to(self.device)

        # Estimate Depth Map
        with BrokenSpinner(f"Estimating Depth Map for the input image (CUDA: {torch.cuda.is_available()})"):
            inputs = self._processor(images=image, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

            # Optimization: We import torch with OMP_NUM_THREADS=1 because NumPy, so "revert" it
            torch.set_num_threads(max(4, multiprocessing.cpu_count()//2))

            # Inference the model
            with torch.no_grad():
                depth = self._model(**inputs).predicted_depth

        # -----------------------------------------------------------------------------------------|
        # Post-processing

        # Normalize image and "fatten" the edges, it's too accurate :^)
        depth = depth.squeeze(1).cpu().numpy()[0]
        depth = (depth - depth.min()) / ((depth.max() - depth.min()) or 1)
        depth = PIL.Image.fromarray((255*depth).astype(numpy.uint8))
        depth = depth.filter(PIL.ImageFilter.MaxFilter(5))
        # depth = depth.filter(PIL.ImageFilter.GaussianBlur(1.5))
        # depth = depth.resize(image.size, PIL.Image.LANCZOS)

        # -----------------------------------------------------------------------------------------|
        # Caching

        # Save image to Cache
        if cache:
            log.success(f"Saving depth map to cache path ({cache_path})")
            depth.save(cache_path)

        return depth
