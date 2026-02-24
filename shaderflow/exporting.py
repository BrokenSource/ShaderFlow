from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from subprocess import PIPE
from tempfile import TemporaryFile as SafePipe
from typing import TYPE_CHECKING, Any, Optional

import moderngl
import tqdm
import turbopipe
from attrs import Factory, define

from shaderflow import logger
from shaderflow.ffmpeg import FFmpeg

if TYPE_CHECKING:
    from shaderflow.scene import ShaderScene

class OutputType(str, Enum):
    PATH = "file"
    PIPE = "pipe"
    TCP  = "tcp"

@define
class ExportingHelper:
    scene: ShaderScene

    @property
    def ffmpeg(self) -> FFmpeg:
        return self.scene.ffmpeg

    # # Output type

    type: OutputType = None

    @property
    def pipe_output(self) -> bool:
        return (self.type is OutputType.PIPE)

    @property
    def path_output(self) -> bool:
        return (self.type is OutputType.PATH)

    @property
    def tcp_output(self) -> bool:
        return (self.type is OutputType.TCP)

    # # Progress

    frame: int = 0
    start: float = Factory(time.monotonic)
    relay: Optional[Callable[[int, int], None]] = None
    bar: Optional[tqdm.tqdm] = None

    def open_bar(self) -> None:
        self.bar = tqdm.tqdm(
            total=self.scene.total_frames,
            disable=((self.relay is False) or self.relay or self.scene.realtime),
            desc=f"Scene ({self.scene.name}) → Video",
            colour="#43BFEF",
            unit=" frames",
            dynamic_ncols=True,
            mininterval=1/30,
            maxinterval=0.5,
            smoothing=0.1,
            leave=False,
        )

    def update(self) -> None:
        if self.relay:
            self.relay(self.frame, self.scene.total_frames)
        if self.bar:
            self.bar.update(1)
        self.frame += 1

    @property
    def finished(self) -> bool:
        return (self.frame >= self.scene.total_frames)

    # # FFmpeg configuration

    def ffmpeg_clean(self) -> None:
        self.ffmpeg.clear(video_codec=False, audio_codec=False)

    def ffmpeg_sizes(self, width: int, height: int) -> None:
        self.ffmpeg.time = self.scene.runtime
        self.ffmpeg.pipe_input(
            pixel_format="rgb24",
            width=self.scene.width,
            height=self.scene.height,
            framerate=self.scene.fps,
        )
        self.ffmpeg.scale(width=width, height=height)
        self.ffmpeg.vflip()

    def ffmpeg_output(self, output: str) -> None:
        if (output in ("pipe", "-", bytes)):
            self.type = OutputType.PIPE
            self.ffmpeg.pipe_output()
        elif ("tcp://" in str(output)):
            raise NotImplementedError
        else:
            self.type = OutputType.PATH
            output = Path(output).expanduser().absolute()
            output = output or Path(f"({datetime.now().strftime('%Y-%m-%d %H-%M-%S')}) {self.scene.name}")
            output.parent.mkdir(parents=True, exist_ok=True)
            self.ffmpeg.output(path=output)

    def ffhook(self) -> None:
        for module in self.scene.modules:
            module.ffhook(self.ffmpeg)

    # # Process management

    process: subprocess.Popen = None
    stdout: SafePipe = None
    stderr: SafePipe = None
    fileno: int = None
    write: Any = None

    def popen(self) -> None:
        self.stderr, self.stdout = (SafePipe(mode="r+b"), SafePipe(mode="r+b"))
        self.process = self.ffmpeg.popen(stdin=PIPE, stdout=self.stdout, stderr=self.stderr)
        self.fileno  = self.process.stdin.fileno()
        self.write   = self.process.stdin.write

    # # Buffers and piping

    buffers: list[moderngl.Buffer] = Factory(list)

    def make_buffers(self, n: int=2) -> None:
        self.buffers = list(self.scene._final.texture.new_buffer() for _ in range(n))

    def release_buffers(self) -> None:
        for buffer in self.buffers:
            turbopipe.sync(buffer)
            buffer.release()

    def pipe(self, turbo: bool=False) -> None:
        """Write a new frame to FFmpeg"""
        if (self.process is None):
            return

        # Raise exception on FFmpeg error
        if (self.process.poll() is not None):
            self.stderr.seek(0)
            raise RuntimeError((
                "FFmpeg process closed unexpectedly with traceback:\n"
                f"{self.stderr.read().decode('utf-8')}"
            ))

        # Cycle through proxy buffers
        buffer = self.buffers[self.frame % len(self.buffers)]

        # Write to FFmpeg stdin
        if turbo:
            turbopipe.sync(buffer)
            self.scene.fbo.read_into(buffer)
            turbopipe.pipe(buffer, self.fileno)
        else:
            self.scene.fbo.read_into(buffer)
            self.write(buffer.read())

    # # Finish

    took: Optional[float] = None

    def finish(self) -> None:
        if self.scene.exporting:
            logger.info((
                "Waiting for FFmpeg process to finish encoding "
                "(Queued writes, codecs lookahead, buffers, etc)"
            ))
            self.release_buffers()
            self.process.stdin.close()
            self.process.wait()
            self.stdout.seek(0)
        if (self.bar is not None):
            self.bar.close()
        self.took = (time.monotonic() - self.start)

    def log_stats(self, output: Path) -> None:
        if self.scene.exporting:
            logger.info(f"Finished rendering ({output})")
        logger.info((
            f"• Stats: "
            f"(Took [cyan]{self.took:.2f}s[/]) at "
            f"([cyan]{(self.frame/self.took):.2f}fps[/] | "
            f"[cyan]{(self.scene.runtime/self.took):.2f}x[/] Realtime) with "
            f"({self.frame} Total Frames)"
        ))
