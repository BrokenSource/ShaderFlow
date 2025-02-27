
# Fixme: Methods to use child class's overrides
# Warn: Must not use __future__ annotations
# pyright: reportInvalidTypeForm=false

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Optional

from attrs import define, field
from pydantic import Field

from Broken import BrokenModel, BrokenWorker
from Broken.Externals.FFmpeg import BrokenFFmpeg

if TYPE_CHECKING:
    from ShaderFlow.Scene import ShaderScene

# ------------------------------------------------------------------------------------------------ #

class VideoSettings(BrokenModel):
    """Mirrors exporting-worthy Scene.main() arguments"""
    width:   Optional[int]   = Field(None, ge=2, le=32768)
    height:  Optional[int]   = Field(None, ge=2, le=32768)
    ratio:   Optional[float] = Field(None, gt=0.0)
    bounds:  Optional[tuple[int, int]] = Field(None)
    scale:   float = Field(1.0,  gt=0.0)
    fps:     float = Field(60.0, gt=0.0)
    quality: float = Field(50.0, ge=0.0, le=100.0)
    ssaa:    float = Field(1.0,  ge=0.0, le=4.0)
    subsample: int = Field(2,    ge=1, le=4)
    time:    float = Field(10.0, ge=0.0)
    start:   float = Field(0.0,  ge=0.0)
    speed:   float = Field(1.0,  gt=0.0)
    loop:    int   = Field(1,    ge=1)
    batch:   str   = Field("0")
    buffers: int   = Field(2,    ge=1)
    noturbo: bool  = Field(False)
    format:  str   = Field("mp4")

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderServer:
    scene: 'ShaderScene' = field(repr=False)

    # -------------------------------------------|

    worker: BrokenWorker = field()

    @worker.default
    def _worker(self) -> BrokenWorker:
        class Worker(BrokenWorker):
            def main(self, tasks: Iterable) -> Iterable[bytes]:
                scene = self.scene()

                for task in tasks:
                    yield scene.render(**task)

        return Worker(size=0)

    # -------------------------------------------|

    @property
    def render(self) -> Callable:
        def _render(
            video: VideoSettings,
            ffmpeg: BrokenFFmpeg,
            config: self.scene.config_t(),
        ) -> bytes:
            try:
                self.scene.config = config
                self.scene.ffmpeg = ffmpeg

                with tempfile.NamedTemporaryFile(
                    suffix=("."+video.format),
                    delete=False,
                ) as temp:
                    return self.main(
                        **video.dict(),
                        output=Path(temp.name),
                        progress=False
                    )[0].read_bytes()
            finally:
                with contextlib.suppress(FileNotFoundError):
                    Path(temp.name).unlink()
        return _render
