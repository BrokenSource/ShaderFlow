import contextlib
import itertools
import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import Field

from Broken import BrokenModel, FrozenHash
from Broken.Externals.FFmpeg import BrokenFFmpeg


class Config(BrokenModel, FrozenHash):
    class VideoSettings(BrokenModel):
        """Mirrors exporting-worthy Scene.main() arguments"""
        width:   Optional[int]   = Field(None, ge=2, le=16384)
        height:  Optional[int]   = Field(None, ge=2, le=16384)
        ratio:   Optional[float] = Field(None, gt=0.0)
        bounds:  Optional[tuple[int, int]] = Field(None)
        scale:   float = Field(1.0,  gt=0.0)
        fps:     float = Field(60.0, gt=0.0)
        quality: float = Field(50.0, ge=0.0, le=100.0)
        ssaa:    float = Field(1.0,  ge=0.0, le=2.0)
        time:    float = Field(10.0, ge=0.0)
        start:   float = Field(0.0,  ge=0.0)
        speed:   float = Field(1.0,  gt=0.0)
        loop:    int   = Field(1,    ge=1)
        batch:   str   = Field("0")
        buffers: int   = Field(2,    ge=1)
        noturbo: bool  = Field(False)
        format:  str   = Field("mp4")

    video: VideoSettings = Field(default_factory=VideoSettings)
    ffmpeg: BrokenFFmpeg = Field(default_factory=BrokenFFmpeg)


def render(self, config: Optional[Config]=None) -> bytes:
    """Render a video file with the current configuration"""
    self.config = (config or self.config)

    try:
        with tempfile.NamedTemporaryFile(
            suffix=("."+self.config.video.format),
            delete=False,
        ) as temp:
            video: bytes = self.main(
                **self.config.video.dict(),
                output=Path(temp.name),
                progress=False
            )[0].read_bytes()
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp.name)

    return video

@classmethod
def worker(cls):
    scene = cls(backend="headless")

    for endurance in itertools.count(1):
        ...
