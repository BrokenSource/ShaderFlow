from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from subprocess import PIPE
from tempfile import TemporaryFile as SafePipe
from time import perf_counter
from typing import TYPE_CHECKING, Any, Optional

import moderngl
import tqdm
import turbopipe
from attr import Factory, define

from Broken import BrokenEnum, BrokenPath
from Broken.Externals.FFmpeg import BrokenFFmpeg

if TYPE_CHECKING:
    from ShaderFlow.Scene import ShaderScene

class OutputType(str, BrokenEnum):
    PATH = "file"
    PIPE = "pipe"
    TCP  = "tcp"

@define
class ExportingHelper:
    scene: ShaderScene

    @property
    def ffmpeg(self) -> BrokenFFmpeg:
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
    start: float = Factory(perf_counter)
    relay: Optional[Callable[[int, int], None]] = None
    bar: Optional[tqdm.tqdm] = None

    def open_bar(self) -> None:
        self.bar = tqdm.tqdm(
            total=self.scene.total_frames,
            disable=((self.relay is False) or self.relay or self.scene.realtime),
            desc=f"Scene #{self.scene.index} ({self.scene.scene_name}) → Video",
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
        self.ffmpeg.set_time(self.scene.runtime)
        self.ffmpeg.pipe_input(
            pixel_format=("rgba" if self.scene.alpha else "rgb24"),
            width=self.scene.width,
            height=self.scene.height,
            framerate=self.scene.fps,
        )
        self.ffmpeg.scale(width=width, height=height)
        self.ffmpeg.vflip()

    def ffmpeg_output(self, base: str, output: str, format: str, _started: str) -> None:
        if (output in ("pipe", "-", bytes)):
            self.type = OutputType.PIPE
            self.ffmpeg.pipe_output()
        elif ("tcp://" in str(output)):
            raise NotImplementedError
        else:
            self.type = OutputType.PATH
            output = BrokenPath.get(output)
            output = output or Path(f"({_started}) {self.scene.scene_name}")
            output = output if output.is_absolute() else (base/output)
            output = output.with_suffix("." + (format or output.suffix or 'mp4').replace(".", ""))
            output = self.scene.export_name(output)
            BrokenPath.mkdir(output.parent)
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
        turbopipe.sync(buffer)
        self.scene.fbo.read_into(buffer)

        # Write to FFmpeg stdin
        if turbo: turbopipe.pipe(buffer, self.fileno)
        else: self.write(buffer.read())

    # # Finish

    took: Optional[float] = None

    def finish(self) -> None:
        if self.scene.exporting:
            self.scene.log_info((
                "Waiting for FFmpeg process to finish encoding "
                "(Queued writes, codecs lookahead, buffers, etc)"
            ))
            self.release_buffers()
            self.process.stdin.close()
            self.process.wait()
            self.stdout.seek(0)
        if (self.bar is not None):
            self.bar.close()
        self.took = (perf_counter() - self.start)

    def log_stats(self, output: Path) -> None:
        self.scene.log_info(f"Finished rendering ({output})", echo=(self.scene.exporting))
        self.scene.log_info((
            f"• Stats: "
            f"(Took [cyan]{self.took:.2f}s[/]) at "
            f"([cyan]{(self.frame/self.took):.2f}fps[/] | "
            f"[cyan]{(self.scene.runtime/self.took):.2f}x[/] Realtime) with "
            f"({self.frame} Total Frames)"
        ))
