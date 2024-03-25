import hashlib
from typing import Any

import numpy
import PIL
from attr import define
from PIL import Image
from ShaderFlow import SHADERFLOW

from Broken.Loaders.LoaderPIL import LoadableImage
from Broken.Loaders.LoaderPIL import LoaderImage
from Broken.Logging import log
from Broken.Spinner import BrokenSpinner


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

    def __call__(self,
        image: LoadableImage,
        normalized: bool=True,
        cache: bool=True,
    ) -> Image:
        """Alias for .estimate()"""
        return self.estimate(image, normalized, cache)

    def estimate(self,
        image: LoadableImage,
        normalized: bool=True,
        cache: bool=True,
    ) -> Image:
        """
        Estimate a Depth Map from an input image with a Monocular Depth Estimation model.

        Args:
            image:      The input image to estimate the depth map from, path, url, PIL
            normalized: Whether to normalize the depth map to (0, 1) based on the min and max values
            cache:      Whether to cache the depth map to the cache directory

        Returns:
            The estimated depth map as a PIL Image
        """

        # -----------------------------------------------------------------------------------------|
        # Caching

        # Load the image
        image = LoaderImage(image).convert("RGB")

        # Calculate hash of the image for caching
        image_hash = hashlib.md5(image.tobytes()).hexdigest()
        cache_path = SHADERFLOW.DIRECTORIES.CACHE/f"{image_hash}.jpeg"

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
            HUGGINGFACE_MODEL = ("LiheYoung/depth-anything-large-hf")
            self._processor = transformers.AutoImageProcessor.from_pretrained(HUGGINGFACE_MODEL)
            self._model = transformers.AutoModelForDepthEstimation.from_pretrained(HUGGINGFACE_MODEL)
            self._model.to(self.device)

        # Estimate Depth Map
        with BrokenSpinner(f"Estimating Depth Map for the input image (CUDA: {torch.cuda.is_available()})"):
            inputs = self._processor(images=image, return_tensors="pt")
            inputs = {key: value.to(self.device) for key, value in inputs.items()}

            # Inference the model
            with torch.no_grad():
                depth = self._model(**inputs).predicted_depth

        # -----------------------------------------------------------------------------------------|
        # Post-processing

        # Resize to the original size
        depth = torch.nn.functional.interpolate(
            depth.unsqueeze(1),
            size=image.size[::-1],
            mode="bicubic",
            align_corners=False,
        )

        # Normalize the depth map
        depth = depth.squeeze().cpu().numpy()
        depth = (depth - depth.min()) / ((depth.max() - depth.min()) or 1)

        # Convert array to PIL Image RGB24
        depth = PIL.Image.fromarray((255*depth).astype(numpy.uint8))

        # -----------------------------------------------------------------------------------------|
        # Caching

        # Save image to Cache
        if cache:
            log.success(f"Saving depth map to cache path ({cache_path})")
            depth.save(cache_path)

        return depth
