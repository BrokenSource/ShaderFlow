from pathlib import Path
from typing import Iterable

import numpy as np
from attrs import define

from shaderflow.ffmpeg import FFmpeg
from shaderflow.module import ShaderModule
from shaderflow.texture import ShaderTexture


@define
class ShaderVideo(ShaderModule):
    name: str = "iVideo"

    path: Path = None
    """Path to the video file"""

    texture: ShaderTexture = None
    """Related texture module"""

    width: int = None
    """Content width, auto calculated when None"""

    height: int = None
    """Content height, auto calculated when None"""

    fps: float = None
    """Content framerate, auto calculated when None"""

    _reader: Iterable = None
    """Internal frames iterable"""

    _frames: int = 0
    """Number of frames read so far"""

    def __attrs_post_init__(self):
        ShaderModule.__attrs_post_init__(self)
        self._reader = FFmpeg.iter_video_frames(self.path)

        # Find base video specifications
        if not all((self.width, self.height)):
            self.width, self.height = FFmpeg.get_video_resolution(self.path)

        self.fps = (self.fps or FFmpeg.get_video_framerate(self.path))

        # Note: You can set .temporal
        self.texture = ShaderTexture(
            scene=self.scene,
            name=self.name,
            width=self.width,
            height=self.height,
            dtype=np.uint8,
            components=3,
        )

    def update(self) -> None:

        # Only write a new frame when due
        if self.scene.time > (self._frames / self.fps):
            frame = next(self._reader)
            frame = np.flip(frame, axis=0)
            frame = np.copy(frame, order='C')
            self.texture.roll()
            self.texture.write(frame)
            self._frames += 1
