from __future__ import annotations

import contextlib
import gc
import importlib
import inspect
import math
import sys
from abc import abstractmethod
from collections import deque
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional, Self, Union

import glfw
import moderngl
import numpy as np
from attrs import Factory, define, field
from imgui_bundle import imgui
from moderngl_window.context.base import BaseWindow as ModernglWindow
from moderngl_window.integrations.imgui_bundle import ModernglWindowRenderer
from PIL import Image
from pytimeparse2 import parse as timeparse
from typer import Option

from broken.enumx import BrokenEnum
from broken.envy import Environment
from broken.externals.ffmpeg import BrokenFFmpeg
from broken.loaders import LoadBytes, LoadString
from broken.model import BrokenModel
from broken.path import BrokenPath
from broken.project import PROJECT
from broken.resolution import BrokenResolution
from broken.scheduler import BrokenScheduler, SchedulerTask
from broken.system import Host
from broken.typerx import BrokenTyper
from broken.utils import (
    BrokenRelay,
    clamp,
    denum,
    hyphen_range,
    overrides,
)
from broken.vectron import Vectron
from broken.worker import BrokenWorker
from shaderflow import SHADERFLOW, logger
from shaderflow.camera import ShaderCamera
from shaderflow.dynamics import DynamicNumber
from shaderflow.exceptions import ShaderBatchStop
from shaderflow.exporting import ExportingHelper
from shaderflow.frametimer import ShaderFrametimer
from shaderflow.keyboard import ShaderKeyboard
from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.shader import ShaderProgram
from shaderflow.variable import ShaderVariable, Uniform

# ---------------------------------------------------------------------------- #

class WindowBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

    @classmethod
    def infer(cls) -> Self:

        # Optional external user override
        if (option := Environment.get("WINDOW_BACKEND")):
            if (value := cls.get(option)) is None:
                raise ValueError(f"Invalid window backend '{option}', options are {cls.values()}")
            return value

        # Infer headless if exporting the scene via cli
        if ("main" in sys.argv) and (args := sys.argv[sys.argv.index("main"):]):
            if any(x in args for x in ("--render", "-r", "--output", "-o")):
                return cls.Headless

        return cls.GLFW

# ---------------------------------------------------------------------------- #

@define
class ShaderScene(ShaderModule):

    # -------------------------------------------|
    # Metadata

    class Metadata(BrokenModel):
        name: str = None
        description: str = None
        author: str = "Unknown"
        version: str = "0.0.0"
        license: str = "Unknown"

    metadata: Metadata = Factory(Metadata)

    @property
    def scene_name(self) -> str:
        return (self.metadata.name or type(self).__name__)

    # -------------------------------------------|
    # Common configuration

    class Config(BrokenModel):
        """A class that contains all specific configurations of the scene"""

    @classmethod
    def config_t(cls) -> type[Config]:
        """Child-last defined Config class"""
        return cls.Config

    config: Config = field()

    @config.default
    def _config(self) -> Config:
        return self.config_t()()

    # -------------------------------------------|
    # ShaderModules

    modules: deque[ShaderModule] = Factory(deque)
    """List of all Modules on the Scene, in order of addition (including the Scene itself)"""

    ffmpeg: BrokenFFmpeg = Factory(BrokenFFmpeg)
    """FFmpeg configuration for exporting (encoding) videos"""

    frametimer: ShaderFrametimer = None
    """Automatically added frametimer module of the Scene"""

    keyboard: ShaderKeyboard = None
    """Automatically added keyboard module of the Scene"""

    camera: ShaderCamera = None
    """Automatically added camera module of the Scene"""

    # -------------------------------------------|
    # Fractional SSAA

    shader: ShaderProgram = None
    """The main ShaderObject of the Scene, the visible content of the Window"""

    alpha: bool = False
    """Makes the final texture have an alpha channel"""

    _final: ShaderProgram = None
    """Internal ShaderObject used for a Fractional Super-Sampling Anti-Aliasing (SSAA). This shader
    samples the texture from the user's final self.shader, which is rendered at SSAA resolution"""

    @property
    def fbo(self) -> moderngl.Framebuffer:
        """The final framebuffer with the current frame"""
        return self._final.texture.fbo

    subsample: int = field(default=2, converter=lambda x: int(max(1, x)))
    """The kernel size of the final SSAA downsample"""

    quality: float = field(default=50.0, converter=lambda x: clamp(float(x), 0.0, 100.0))
    """Visual quality level (0-100%), if implemented on the Shader/Scene"""

    # -------------------------------------------|
    # Commands

    cli: BrokenTyper = Factory(lambda: BrokenTyper(chain=True))
    """This Scene's BrokenTyper instance for the CLI. Commands are added by any module in the
    `self.commands` method. The `self.main` is always added to it"""

    scene_panel: str = "🔥 Scene commands"

    def __post__(self):
        self.cli.description = (self.cli.description or type(self).__doc__)
        self.ffmpeg.typer_vcodecs(self.cli)
        self.ffmpeg.typer_acodecs(self.cli)
        self.cli._panel = self.scene_panel
        self.cli.command(self.main)

    def initialize(self):

        # Can only initialize once, block batch exporing
        # or external management from running it again
        if (self.window is not None):
            return

        logger.info(f"Initializing scene [bold blue]'{self.scene_name}'[/] with backend {self.backend}")

        # Some ImGUI operations must only be done once to avoid memory leaks
        if (_imfirst := (imgui.get_current_context() is None)):
            imgui.create_context()
        self.imguio = imgui.get_io()
        self.imguio.set_ini_filename(str(PROJECT.DIRECTORIES.CONFIG/"imgui.ini"))
        self.imguio.font_global_scale = Environment.float("IMGUI_FONT_SCALE", 1.0)

        # Default modules
        self.frametimer = ShaderFrametimer(scene=self)
        self.keyboard = ShaderKeyboard(scene=self)
        self.camera = ShaderCamera(scene=self)
        self.init_window()

        # Create the SSAA Workaround engines
        self._final = ShaderProgram(scene=self, name="iFinal")
        self._final.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"final.glsl")
        self._final.texture.components = (3 + int(self.alpha))
        self._final.texture.dtype = np.uint8
        self._final.texture.final = True
        self._final.texture.track = 1.0
        self.shader = ShaderProgram(scene=self, name="iScreen")
        self.shader.texture.repeat(False)
        self.shader.texture.track = 1.0
        self.build()

    def __del__(self):

        # Release OpenGL items and windows
        for module in self.modules:
            module.destroy()
        with contextlib.suppress(AttributeError):
            self.opengl.release()
        with contextlib.suppress(AttributeError):
            self.window.destroy()

        # Deeper cyclic references
        gc.collect()

    # ---------------------------------------------------------------------------------------------|
    # Temporal

    time: float = field(default=0.0, converter=float)
    """Current virtual time of the scene. Everything should depend on it for flexibility"""

    start: float = field(default=0.0, converter=float)
    """Start time offset added to self.time"""

    speed: float = Factory(lambda: DynamicNumber(value=1, frequency=3))
    """Time scale factor, used for `dt`, which integrates to `time`"""

    runtime: float = field(default=10.0, converter=float)
    """Total duration of the scene, set by user or longest module"""

    fps: float = field(default=60.0, converter=float)
    """Target frames per second rendering speed"""

    dt: float = field(default=0.0, converter=float)
    """Virtual delta time since last frame, time scaled by `speed`. Use `self.rdt` for real delta"""

    rdt: float = field(default=0.0, converter=float)
    """Real life, physical delta time since last frame. Use `self.dt` for virtual scaled version"""

    @property
    def tau(self) -> float:
        """Normalized time value relative to runtime between 0 and 1"""
        return (self.time / self.runtime) % 1.0

    @property
    def cycle(self) -> float:
        """A number from 0 to 2pi that ends on the runtime ('normalized angular time')"""
        return (self.tau * math.tau)

    @property
    def frametime(self) -> float:
        """Ideal time between two frames. This value is coupled with `fps`"""
        return (1.0 / self.fps)

    @frametime.setter
    def frametime(self, value: float):
        self.fps = (1.0 / value)

    @property
    def frame(self) -> int:
        """Current frame index being rendered. This value is coupled with 'time' and 'fps'"""
        return round(self.time * self.fps)

    @frame.setter
    def frame(self, value: int):
        self.time = (value / self.fps)

    @property
    def total_frames(self) -> int:
        return max(1, round(self.runtime * self.fps))

    # Total Duration

    @property
    def duration(self) -> float:
        return self.runtime

    @property
    def max_duration(self) -> float:
        """The longest module duration"""
        return max((module.duration or 0.0) for module in self.modules)

    def set_duration(self, override: float=None) -> float:
        """Either force the duration, find the longest module or use base duration"""
        self.runtime  = (override or self.max_duration)
        self.runtime /= self.speed.value
        return self.runtime

    # ---------------------------------------------------------------------------------------------|
    # Window properties

    def _window_proxy(self, attribute, value) -> Any:
        name: str = attribute.name

        if (name == "exclusive"):
            name = "mouse_exclusivity"

        with contextlib.suppress(AttributeError):
            logger.debug(f"Changing Window attribute '{name}' to '{value}'")
            setattr(self.window, name, value)

        return value

    title: str = field(default="ShaderFlow", on_setattr=_window_proxy)
    """Realtime window 'title' property"""

    resizable: bool = field(default=True, on_setattr=_window_proxy)
    """Realtime window 'is resizable' property"""

    fullscreen: bool = field(default=False, on_setattr=_window_proxy)
    """Realtime window 'is fullscreen' property"""

    exclusive: bool = field(default=False, on_setattr=_window_proxy)
    """Realtime window 'mouse exclusivity' property"""

    visible: bool = field(default=False, on_setattr=_window_proxy)
    """Realtime window 'is visible' property"""

    @property
    def hidden(self) -> bool:
        """Realtime window 'is hidden' property"""
        return (not self.visible)

    @hidden.setter
    def hidden(self, value: bool):
        self.visible = (not value)

    # # Video modes and monitor

    monitor: int = field(default=Environment.int("MONITOR", 0), converter=int)
    """Monitor index to base the window parameters on"""

    @property
    def glfw_monitor(self) -> Optional[glfw._GLFWmonitor]:
        if (monitors := glfw.get_monitors()):
            return monitors[self.monitor]

    @property
    def glfw_video_mode(self) -> Optional[dict]:
        if (monitor := self.glfw_monitor):
            return glfw.get_video_mode(monitor)

    @property
    def monitor_framerate(self) -> float:
        """Note: Defaults to 60 if no monitor is found or non-real time"""
        if (not self.realtime):
            return 60.0
        if (mode := self.glfw_video_mode):
            return mode.refresh_rate or 60.0
        return 60.0

    @property
    def monitor_size(self) -> Optional[tuple[int, int]]:
        if self.exporting:
            return None
        if (mode := self.glfw_video_mode):
            return (mode.size.width, mode.size.height)

    @property
    def monitor_width(self) -> Optional[int]:
        if (resolution := self.monitor_size):
            return resolution[0]

    @property
    def monitor_height(self) -> Optional[int]:
        if (resolution := self.monitor_size):
            return resolution[1]

    # ---------------------------------------------------------------------------------------------|
    # Resolution

    @property
    def components(self) -> int:
        return self._final.texture.components

    # # Scale

    _scale: float = field(default=1.0, converter=lambda x: max(0.01, x))

    @property
    def scale(self) -> float:
        """Resolution scale factor, the `self.width` and `self.height` are multiplied by this"""
        return self._scale

    @scale.setter
    def scale(self, value: float):
        logger.debug(f"Changing Resolution Scale to ({value})")
        self.resize(scale=value)

    # # Width

    _width: int = field(default=1920)

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int):
        self.resize(width=(value*self._scale))

    # # Height

    _height: int = field(default=1080)

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int):
        self.resize(height=(value*self._scale))

    # # SSAA

    _ssaa: float = field(default=1.0, converter=lambda x: max(0.01, float(x)))

    @property
    def ssaa(self) -> float:
        """(Fractional) Super Sampling Anti-Aliasing (SSAA) factor [^1]

        Render in a virtual resolution of this multiplier, then resample to the original resolution
        - Values higher than 1 improves the image quality, maximum visual quality at 2
        - Significant GPU cost of O(N^2): quadruples the GPU use at 2, or 25% at 0.5

        [^1]: https://en.wikipedia.org/wiki/Supersampling (Uniform grid distribution)
        """
        return self._ssaa

    @ssaa.setter
    def ssaa(self, value: float):
        logger.debug(f"Changing Fractional SSAA to {value}")
        self._ssaa = value
        self.relay(ShaderMessage.Shader.RecreateTextures)

    # # Resolution (With, Height)

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)

    @resolution.setter
    def resolution(self, value: tuple[int, int]):
        self.resize(*value)

    @property
    def render_resolution(self) -> tuple[int, int]:
        """Internal true rendering resolution with SSAA applied"""
        return (int(self.width*self.ssaa), int(self.height*self.ssaa))

    # # Aspect Ratio

    _aspect_ratio: float = None

    @property
    def aspect_ratio(self) -> float:
        """Either the forced `self._aspect_ratio` or dynamic from `self.width/self.height`. When set
        and resizing, the logic of `BrokenResolution.fit` is applied to enforce ratios"""
        return self._aspect_ratio or (self.width/self.height)

    @aspect_ratio.setter
    def aspect_ratio(self, value: Union[float, str]):
        logger.debug(f"Changing Aspect Ratio to {value}")

        # The aspect ratio can be sent as a fraction or "none", "false"
        if isinstance(value, str):
            value = eval(value.replace(":", "/").capitalize())

        # Optimization: Only change if different
        if (self._aspect_ratio == value):
            return

        self._aspect_ratio = value

        if (self.backend == WindowBackend.GLFW):
            glfw.set_window_aspect_ratio(self.window._window,
                *Vectron.limited_ratio(self._aspect_ratio, upper=2**16)) or \
                (glfw.DONT_CARE, glfw.DONT_CARE)

    def resize(self,
        width: Union[int, float]=None,
        height: Union[int, float]=None,
        *,
        ratio: Union[float, str]=None,
        bounds: tuple[int, int]=None,
        scale: float=None,
        ssaa: float=None,
    ) -> tuple[int, int]:

        # Maybe update auxiliary properties
        self.aspect_ratio = overrides(self._aspect_ratio, ratio)
        self._scale = overrides(self._scale, scale)
        self._ssaa = overrides(self._ssaa, ssaa)

        # The parameters aren't trivial. The idea is to fit resolution from the scale-less components,
        # so scaling isn't carried over, then to apply scaling (self.resolution)
        resolution = BrokenResolution.fit(
            old=(self._width, self._height),
            new=(width, height),
            max=(bounds or self.monitor_size),
            ar=self._aspect_ratio,
            scale=self._scale,
        )

        # Optimization: Only resize if target is different
        if (resolution != (self.width, self.height)):
            self._width, self._height = resolution
            self.window.size = self.resolution
            self.relay(ShaderMessage.Shader.RecreateTextures)
            logger.info(f"Resized Window to {self.resolution}")

        return self.resolution

    # ---------------------------------------------------------------------------------------------|
    # Window, OpenGL, Backend

    backend: WindowBackend = Factory(WindowBackend.infer)
    """The ModernGL Window Backend. **Cannot be changed after creation**. Can also be set with the
    environment variable `WINDOW_BACKEND=<backend>`, where `backend = {glfw, headless}`"""

    opengl: moderngl.Context = None
    """ModernGL Context of this Scene. The thread accessing this MUST own or ENTER its context for
    creating, changing, deleting objects; more often than not, it's the Main thread"""

    window: ModernglWindow = None
    """ModernGL Window instance at `site-packages/moderngl_window.context.<self.backend>.Window`"""

    imgui: ModernglWindowRenderer = None
    """ModernGL Imgui integration class bound to the Window"""

    imguio: Any = None
    """Imgui IO object"""

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""
        if self.window:
            raise RuntimeError("The window backend cannot be initialized twice")

        # Linux: Use EGL for creating a OpenGL context, allows true headless with GPU acceleration
        # Note: (https://forums.developer.nvidia.com/t/81412) (https://brokensrc.dev/get/docker/)
        backend = ("egl" if Host.OnLinux and Environment.flag("WINDOW_EGL", 1) else None)

        # Dynamically import and instantiate the ModernGL Window class
        module = f"moderngl_window.context.{denum(self.backend).lower()}"
        self.window = importlib.import_module(module).Window(
            size=self.resolution,
            title=self.title,
            resizable=self.resizable,
            visible=self.visible,
            fullscreen=self.fullscreen,
            backend=backend,
            vsync=False,
        )
        ShaderKeyboard.set_keymap(self.window.keys)
        self.imgui  = ModernglWindowRenderer(self.window)
        self.opengl = self.window.ctx

        # Bind window events to relay
        self.window.resize_func               = (self.__window_resize__)
        self.window.close_func                = (self.__window_close__)
        self.window.iconify_func              = (self.__window_iconify__)
        self.window.key_event_func            = (self.__window_key_event__)
        self.window.mouse_position_event_func = (self.__window_mouse_position_event__)
        self.window.mouse_press_event_func    = (self.__window_mouse_press_event__)
        self.window.mouse_release_event_func  = (self.__window_mouse_release_event__)
        self.window.mouse_drag_event_func     = (self.__window_mouse_drag_event__)
        self.window.mouse_scroll_event_func   = (self.__window_mouse_scroll_event__)
        self.window.unicode_char_entered_func = (self.__window_unicode_char_entered__)
        self.window.files_dropped_event_func  = (self.__window_files_dropped_event__)

        if (self.backend == WindowBackend.GLFW):
            if (icon := PROJECT.RESOURCES.ICON_PNG).exists() and (not Host.Wayland):
                BrokenWorker.thread(self.window.set_icon, icon_path=icon)
            glfw.set_cursor_enter_callback(self.window._window, (self.__window_mouse_enter_event__))
            glfw.set_drop_callback(self.window._window, (self.__window_files_dropped_event__))
            ShaderKeyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
            ShaderKeyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
            ShaderKeyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT

        logger.info(f"OpenGL Renderer: {self.opengl.info['GL_RENDERER']}")

    def screenshot(self) -> np.ndarray:
        """Take a screenshot of the screen and return a numpy array with the data"""
        data = self.fbo.read(viewport=(0, 0, self.width, self.height))
        data = np.ndarray((self.height, self.width, self.components), dtype=np.uint8, buffer=data)
        return np.flipud(data)

    # ---------------------------------------------------------------------------------------------|
    # User actions

    @property
    def directory(self) -> Path:
        """Path of the current Scene file Python script. This works by searching up the call stack
        for the first context whose filename isn't the local __file__ (of ShaderFlow.Scene)"""
        # Idea: Maybe `type(self).mro()[0]` could help
        for frame in inspect.stack():
            if (frame.filename != __file__):
                return Path(frame.filename).parent

    def read_file(self, file: Path, *, bytes: bool=False) -> Union[str, bytes]:
        """Read a file relative to the current Scene Python script"""
        file = (self.directory/file)
        logger.info(f"Reading file ({file})")
        return LoadBytes(file) if bytes else LoadString(file)

    # ---------------------------------------------------------------------------------------------|
    # Main event loop

    scheduler: BrokenScheduler = Factory(BrokenScheduler)
    """Scheduler for the Scene, handles all the tasks and their execution"""

    vsync: SchedulerTask = None
    """Task for the Scene's main event loop, the rendering of the next frame"""

    _quit: bool = False

    def quit(self) -> None:
        self._quit = True

    on_frame: BrokenRelay = Factory(BrokenRelay)
    """Hook for after a frame is rendered"""

    def next(self, dt: float=0.0) -> None:
        """Integrate time, update all modules and render the next frame"""

        # Fixme: Windows: https://github.com/glfw/glfw/pull/1426
        # Immediately swap the buffer with previous frame for vsync
        if (not self.exporting):
            self.window.swap_buffers()

        # Note: Updates in reverse order of addition (child -> parent -> root)
        # Note: Updates non-engine first, as the pipeline might change
        for module in self.modules:
            if not isinstance(module, ShaderProgram):
                module.update()
        for module in reversed(self.modules):
            if isinstance(module, ShaderProgram):
                module.update()

        self._render_ui()
        self.on_frame()

        # Temporal logic is run afterwards, so frame zero is t=0
        self.speed.next(dt=abs(dt))
        self.vsync.fps = self.fps
        self.dt    = dt * self.speed
        self.rdt   = dt
        self.time += self.dt

    realtime: bool = True
    """'Realtime' mode: Running with a window and user interaction"""

    exporting: bool = False
    """Is this Scene exporting to a video file?"""

    freewheel: bool = False
    """'Not realtime' mode: Either Exporting, Rendering or Benchmarking"""

    headless: bool = False
    """Running Headlessly, without a window and user interaction"""

    loops: int = field(default=1, converter=int)
    """Number of times to loop the exported video. One 1 keeps original, two 2 doubles the length.
    Ideally have seamless transitions on the shader based on self.tau and/or/no audio input"""

    index: int = 0
    """Current Batch exporting video index"""

    @abstractmethod
    def export_name(self, path: Path) -> Path:
        """Change the video file name being exported based on the current batch index. By default,
        the name is unchanged in single export, else the stem is appended with the batch index"""
        if (self.index > 0):
            return path.with_stem(f"{path.stem}_{self.index}")
        return path

    def main(self,
        width:      Annotated[int,   Option("--width",      "-w",                 help="[bold red   ](🔴 Basic  )[/] Width  of the rendering resolution [medium_purple3](None to keep or find by --ar aspect ratio)[/] [dim](1920 on init)[/]")]=None,
        height:     Annotated[int,   Option("--height",     "-h",                 help="[bold red   ](🔴 Basic  )[/] Height of the rendering resolution [medium_purple3](None to keep or find by --ar aspect ratio)[/] [dim](1080 on init)[/]")]=None,
        fps:        Annotated[float, Option("--fps",        "-f",                 help="[bold red   ](🔴 Basic  )[/] Target frames per second [medium_purple3](Defaults to the monitor framerate on realtime else 60)[/]")]=None,
        scale:      Annotated[float, Option("--scale",      "-x",                 help="[bold red   ](🔴 Basic  )[/] Post-multiply width and height by a scale factor [medium_purple3](None to keep)[/] [dim](1.0 on init)[/]")]=None,
        ratio:      Annotated[str,   Option("--ratio",    "--ar",                 help="[bold red   ](🔴 Basic  )[/] Force resolution aspect ratio [green](Examples: '16:9', '16/9', '1.777')[/] [medium_purple3](None for dynamic)[/]")]=None,
        frameskip:  Annotated[bool,  Option("--frameskip",        " /--rigorous", help="[bold red   ](🔴 Window )[/] [dim]Frames are skipped if the rendering is behind schedule [medium_purple3](Limits maximum dt to 1/fps)[/]")]=True,
        fullscreen: Annotated[bool,  Option("--fullscreen",       " /--windowed", help="[bold red   ](🔴 Window )[/] [dim]Start the realtime window in fullscreen mode [medium_purple3](Toggle with F11)[/]")]=False,
        maximize:   Annotated[bool,  Option("--maximize",   "-M",                 help="[bold red   ](🔴 Window )[/] [dim]Start the realtime window in maximized mode")]=False,
        quality:    Annotated[float, Option("--quality",    "-q",                 help="[bold yellow](🟡 Quality)[/] Global quality level [green](0-100%)[/] [yellow](If implemented on the scene/shader)[/] [medium_purple3](None to keep, default 50%)[/]")]=None,
        ssaa:       Annotated[float, Option("--ssaa",       "-s",                 help="[bold yellow](🟡 Quality)[/] Super sampling anti aliasing factor [green](0-4)[/] [yellow](N^2 GPU cost)[/] [medium_purple3](None to keep, default 1)[/]")]=None,
        subsample:  Annotated[int,   Option("--subsample",                        help="[bold yellow](🟡 Quality)[/] Subpixel downsample kernel size for the final SSAA [green](1-4)[/] [medium_purple3](None to keep, default 2)[/]")]=None,
        render:     Annotated[bool,  Option("--render",     "-r", " /--realtime", help="[bold green ](🟢 Export )[/] Export the Scene to a video file defined on --output [dim](Implicit if present)[/]")]=False,
        time:       Annotated[str,   Option("--time",       "-t",                 help="[bold green ](🟢 Export )[/] Total length of the exported video [dim](Loop duration)[/] [medium_purple3](None to keep, default 10 or longest module)[/]")]=None,
        output:     Annotated[str,   Option("--output",     "-o",                 help="[bold green ](🟢 Export )[/] Output video file name [green]('absolute', 'relative', 'plain' path)[/] [dim]($base/$(plain or $scene-$date))[/]")]=None,
        format:     Annotated[str,   Option("--format",     "-F",                 help="[bold green ](🟢 Export )[/] Output video container [green]('mp4', 'mkv', 'webm', 'avi, '...')[/] [yellow](--output one is prioritized)[/]")]=None,
        base:       Annotated[Path,  Option("--base",       "-D",                 help="[bold green ](🟢 Export )[/] Export base directory [medium_purple3](If plain name)[/]")]=PROJECT.DIRECTORIES.DATA,
        start:      Annotated[float, Option("--start",      "-T",                 help="[bold green ](🟢 Export )[/] Start time offset of the exported video [yellow](Time is shifted by this)[/] [medium_purple3](None to keep)[/] [dim](0 on init)[/]")]=None,
        speed:      Annotated[float, Option("--speed",                            help="[bold green ](🟢 Export )[/] Time speed factor of the scene [yellow](Duration is stretched by 1/speed)[/] [medium_purple3](None to keep)[/] [dim](1 on init)[/]")]=None,
        batch:      Annotated[str,   Option("--batch",      "-b",                 help="[bold green ](🟢 Export )[/] Hyphenated indices range to export multiple videos, if implemented [medium_purple3](1,5-7,10 or 'all')[/medium_purple3]")]="0",
        loops:      Annotated[int,   Option("--loops",      "-l",                 help="[bold blue  ](🔵 Special)[/] Exported videos loop copies [yellow](Final duration is multiplied by this)[/] [dim](1 on init)[/]")]=None,
        freewheel:  Annotated[bool,  Option("--freewheel",        " /--vsync",    help="[bold blue  ](🔵 Special)[/] Unlock the Scene's event loop framerate, implicit when exporting")]=False,
        raw:        Annotated[bool,  Option("--raw",                              help="[bold blue  ](🔵 Special)[/] Send raw OpenGL frames before GPU SSAA to FFmpeg [dim](CPU Downsampling)[/]")]=False,
        open:       Annotated[bool,  Option("--open",                             help="[bold blue  ](🔵 Special)[/] Open the directory where the video was saved after finishing rendering")]=False,
        precise:    Annotated[bool,  Option("--precise",          " /--relaxed",  help="[bold blue  ](🔵 Special)[/] [dim]Use a precise but higher CPU overhead frametime sleep function on realtime mode")]=True,
        turbo:      Annotated[bool,  Option("--turbo",            " /--no-turbo", help="[bold blue  ](🔵 Turbo  )[/] [dim]Enables [steel_blue1][link=https://github.com/BrokenSource/TurboPipe]TurboPipe[/link][/steel_blue1] fast exporting [medium_purple3](disabling may fix segfaults in some systems)[/]")]=Environment.flag("TURBOPIPE", 1),
        buffers:    Annotated[int,   Option("--buffers",    "-B",                 help="[bold blue  ](🔵 Turbo  )[/] [dim]Maximum number of pre-rendered frames to be piped into FFmpeg[/dim]")]=3,
        # Special: Not part of the cli
        progress:   Annotated[Optional[Callable[[int, int], None]], BrokenTyper.exclude()]=None,
        bounds:     Annotated[Optional[tuple[int, int]], BrokenTyper.exclude()]=None,
        # Batch exporting internal use
        _initial:   Annotated[tuple[int, int], BrokenTyper.exclude()]=None,
        _index:     Annotated[int,  BrokenTyper.exclude()]=None,
        _started:   Annotated[str,  BrokenTyper.exclude()]=None,
        _outputs:   Annotated[Path, BrokenTyper.exclude()]=None,
    ) -> Optional[list[Union[Path, bytes]]]:
        """
        Main event loop of the scene
        """

        # -----------------------------------------------------------------------------------------|
        # Batch exporting implementation

        if (_index is None):
            self.initialize()

            # One-shot internal reference variables
            _started = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            _initial = self.resolution
            _outputs = list()

            for _index in hyphen_range(batch):
                try:
                    self._quit = False
                    ShaderScene.main(**locals())
                except ShaderBatchStop:
                    logger.info(f"Batch exporting stopped at index {_index}")
                    break

            if (self.exporting and open):
                BrokenPath.explore(_outputs[0].parent)

            # Revert to the original resolution
            self._width, self._height = _initial
            return _outputs

        # -----------------------------------------------------------------------------------------|

        self.exporting  = (render or bool(output))
        self.freewheel  = (self.exporting or freewheel)
        self.headless   = (self.freewheel)
        self.realtime   = (not self.headless)
        self.title      = (f"ShaderFlow • {self.scene_name}")
        self.fps        = overrides(self.monitor_framerate, fps)
        self.subsample  = overrides(self.subsample, subsample)
        self.quality    = overrides(self.quality, quality)
        self.start      = overrides(self.start, start)
        self.loops      = overrides(self.loops, loops)
        self.fullscreen = (fullscreen)
        self.index      = _index
        self.time       = 0
        self.speed.set(speed or self.speed.value)
        self.relay(ShaderMessage.Shader.Compile)
        self._width, self._height = _initial
        self.scheduler.clear()

        # Set module defaults or overrides
        for module in self.modules:
            module.setup()

        # Try parsing a time, else eval a math expression if a string is given or keep as is
        self.set_duration((timeparse(time) or eval(time)) if isinstance(time, str) else time)

        # Calculate the final resolution
        _width, _height = self.resize(
            width=width, height=height,
            ratio=ratio, scale=scale,
            bounds=bounds,
        )

        # After resizing to avoid wrong base size
        self.ssaa = overrides(self.ssaa, ssaa)

        # Optimization: Save bandwidth by piping native frames
        if self.freewheel and (raw or self.ssaa < 1):
            self.resize(*self.render_resolution, scale=1, ssaa=1)

        # Status tracker and refactored exporting utilities
        export = ExportingHelper(self, relay=progress)

        # Configure FFmpeg and Popen it
        if (self.exporting):
            export.ffmpeg_clean()
            export.ffmpeg_sizes(width=_width, height=_height)
            export.ffmpeg_output(base=base, output=output, format=format, _started=_started)
            export.make_buffers(buffers)
            export.ffhook()
            export.popen()
        if (self.freewheel):
            export.open_bar()

        # Some scenes might take a while to setup
        self.visible = (not self.headless)

        if (maximize and (self.backend == WindowBackend.GLFW)):
            glfw.maximize_window(self.window._window)

        # Add self.next to the event loop
        self.vsync = self.scheduler.new(
            task=self.next,
            frequency=self.fps,
            freewheel=self.freewheel,
            frameskip=frameskip,
            precise=precise,
        )

        while (task := self.scheduler.next()):
            if (task is not self.vsync):
                continue
            if (self._quit):
                break
            if (self.realtime):
                continue
            export.pipe(turbo=turbo)
            export.update()

            if (export.finished):
                export.finish()
                if (export.path_output):
                    output = self.ffmpeg.outputs[0].path
                    output = BrokenFFmpeg.loop(output, times=self.loops)
                    _outputs.append(output)
                if (export.pipe_output):
                    _outputs.append(export.stdout.read())
                export.log_stats(output=output)
                break

    # ---------------------------------------------------------------------------------------------|
    # Module

    def handle(self, message: ShaderMessage) -> None:

        if isinstance(message, ShaderMessage.Window.Close):
            logger.info("Received Window Close Event")
            self.hidden = True
            self._quit = True

        elif isinstance(message, ShaderMessage.Keyboard.KeyDown):
            if (message.key == ShaderKeyboard.Keys.O):
                logger.info("(O  ) Resetting the scene")
                for module in self.modules:
                    module.setup()
                self.time = 0

            elif (message.key == ShaderKeyboard.Keys.R):
                logger.info("(R  ) Reloading shaders")
                self.relay(ShaderMessage.Shader.Compile)

            elif (message.key == ShaderKeyboard.Keys.TAB):
                logger.info("(TAB) Toggling menu")
                self.render_ui = (not self.render_ui)

            elif (message.key == ShaderKeyboard.Keys.F1):
                logger.info("(F1 ) Toggling exclusive mode")
                self.exclusive = (not self.exclusive)

            elif (message.key == ShaderKeyboard.Keys.F2):
                from datetime import datetime
                image = Image.fromarray(self.screenshot())
                time  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                path  = PROJECT.DIRECTORIES.SCREENSHOTS/f"({time}) {self.scene_name}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"(F2 ) Saving screenshot to ({path})")
                BrokenWorker.thread(image.save, fp=path)

            elif (message.key == ShaderKeyboard.Keys.F11):
                logger.info("(F11) Toggling fullscreen")
                self.fullscreen = (not self.fullscreen)

        elif isinstance(message, (ShaderMessage.Mouse.Drag, ShaderMessage.Mouse.Position)):
            self.mouse_gluv = (message.u, message.v)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",   "iLayer",       None) # Special
        yield Uniform("float", "iTime",        self.time + self.start)
        yield Uniform("float", "iTau",         self.tau)
        yield Uniform("float", "iDuration",    self.duration)
        yield Uniform("float", "iDeltatime",   self.dt)
        yield Uniform("vec2",  "iResolution",  self.resolution)
        yield Uniform("float", "iWantAspect",  self.aspect_ratio)
        yield Uniform("float", "iQuality",     self.quality/100)
        yield Uniform("float", "iSSAA",        self.ssaa)
        yield Uniform("float", "iFramerate",   self.fps)
        yield Uniform("int",   "iFrame",       self.frame)
        yield Uniform("bool",  "iRealtime",    self.realtime)
        yield Uniform("vec2",  "iMouse",       self.mouse_gluv)
        yield Uniform("bool",  "iMouseInside", self.mouse_inside)
        for i in range(1, 3):
            yield Uniform("bool", f"iMouse{i}", self.mouse_buttons[i])

    # ---------------------------------------------------------------------------------------------|
    # Internal window events

    def __window_resize__(self, width: int, height: int) -> None:

        # Don't listen to resizes when exporting, as the final resolution might be
        # greater than the monitor and the window will resize down to fit
        if self.exporting:
            return
        self.imgui.resize(width, height)
        self._width, self._height = width, height
        self.relay(ShaderMessage.Shader.RecreateTextures)

    def __window_close__(self) -> None:
        self.relay(ShaderMessage.Window.Close())

    def __window_iconify__(self, state: bool) -> None:
        self.relay(ShaderMessage.Window.Iconify(state=state))

    def __window_files_dropped_event__(self, window, files: list[str]) -> None:
        self.relay(ShaderMessage.Window.FileDrop(files=files))

    # # Keyboard related events

    def __window_key_event__(self, key: int, action: int, modifiers: int) -> None:
        self.imgui.key_event(key, action, modifiers)
        if self.imguio.want_capture_keyboard and self.render_ui:
            return
        if action == ShaderKeyboard.Keys.ACTION_PRESS:
            self.relay(ShaderMessage.Keyboard.KeyDown(key=key, modifiers=modifiers))
        elif action == ShaderKeyboard.Keys.ACTION_RELEASE:
            self.relay(ShaderMessage.Keyboard.KeyUp(key=key, modifiers=modifiers))
        self.relay(ShaderMessage.Keyboard.Press(key=key, action=action, modifiers=modifiers))

    def __window_unicode_char_entered__(self, char: str) -> None:
        if self.imguio.want_capture_keyboard and self.render_ui:
            return
        self.relay(ShaderMessage.Keyboard.Unicode(char=char))

    # # Mouse related events

    mouse_gluv: tuple[float, float] = Factory(lambda: (0, 0))

    def __xy2uv__(self, x: int=0, y: int=0) -> dict[str, float]:
        """Convert a XY pixel coordinate into a Center-UV normalized coordinate"""
        return dict(
            u=2*(x/self.width  - 0.5),
            v=2*(y/self.height - 0.5)*(-1),
            x=x, y=y,
        )

    def __dxdy2dudv__(self, dx: int=0, dy: int=0) -> dict[str, float]:
        """Convert a dx dy pixel coordinate into a Center-UV normalized coordinate"""
        return dict(
            du=2*(dx/self.width)*(self.width/self.height),
            dv=2*(dy/self.height)*(-1),
            dx=dx, dy=dy,
        )

    mouse_buttons: dict[int, bool] = Factory(lambda: {k: False for k in range(1, 6)})

    def __window_mouse_press_event__(self, x: int, y: int, button: int) -> None:
        self.imgui.mouse_press_event(x, y, button)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.mouse_buttons[button] = True
        self.relay(ShaderMessage.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event__(self, x: int, y: int, button: int) -> None:
        self.imgui.mouse_release_event(x, y, button)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.mouse_buttons[button] = False
        self.relay(ShaderMessage.Mouse.Release(
            **self.__xy2uv__(x, y),
            button=button
        ))

    mouse_inside: bool = False

    def __window_mouse_enter_event__(self, window, inside: bool) -> None:
        self.mouse_inside = inside
        self.relay(ShaderMessage.Mouse.Enter(state=inside))

    def __window_mouse_scroll_event__(self, dx: int, dy: int) -> None:
        self.imgui.mouse_scroll_event(dx, dy)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        elif self.keyboard(ShaderKeyboard.Keys.LEFT_ALT):
            self.speed.target += (dy)*0.2
            return
        self.relay(ShaderMessage.Mouse.Scroll(
            **self.__dxdy2dudv__(dx=dx, dy=dy)
        ))

    def __window_mouse_position_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.imgui.mouse_position_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.relay(ShaderMessage.Mouse.Position(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    _mouse_drag_time_factor: float = 4
    """How much seconds to scroll in time when the mouse moves the full window height"""

    def __window_mouse_drag_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.imgui.mouse_drag_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse and self.render_ui:
            return

        # Rotate the camera on Shift
        if self.keyboard(ShaderKeyboard.Keys.LEFT_CTRL):
            cx, cy = (x-self.width/2), (y-self.height/2)
            angle = math.atan2(cy+dy, cx+dx) - math.atan2(cy, cx)
            if (abs(angle) > math.pi): angle -= 2*math.pi
            self.camera.rotate(self.camera.forward, degrees=math.degrees(angle))
            return

        elif self.exclusive:
            self.camera.apply_zoom(dy/500)
            self.camera.rotate(self.camera.forward, degrees=-dx/10)
            return

        # Time Travel on Alt
        elif self.keyboard(ShaderKeyboard.Keys.LEFT_ALT):
            self.time -= self._mouse_drag_time_factor * (dy/self.height)
            return

        self.relay(ShaderMessage.Mouse.Drag(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    # ---------------------------------------------------------------------------------------------|
    # Todo: Move UI to own class: For main menu, settings, exporting, etc

    render_ui: bool = False
    """Whether to render the Main UI"""

    # Fixme: Move to somewhere better
    def _render_ui(self):
        if not self.render_ui:
            return

        self._final.texture.fbo.use()
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 8)
        imgui.push_style_var(imgui.StyleVar_.tab_rounding, 8)
        imgui.push_style_var(imgui.StyleVar_.grab_rounding, 8)
        imgui.push_style_var(imgui.StyleVar_.frame_rounding, 8)
        imgui.push_style_var(imgui.StyleVar_.child_rounding, 8)
        imgui.push_style_color(imgui.Col_.frame_bg, (0.1, 0.1, 0.1, 0.5))
        imgui.new_frame()
        imgui.set_next_window_pos((0, 0))
        imgui.set_next_window_bg_alpha(0.6)
        imgui.begin(f"{self.name}", False, imgui.WindowFlags_.no_move | imgui.WindowFlags_.no_resize | imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.always_auto_resize)

        # Render every module
        for module in self.modules:
            if imgui.tree_node_ex(
                f"{module.uuid:>2} - {type(module).__name__.replace('ShaderFlow', '')}",
                imgui.TreeNodeFlags_.default_open | imgui.TreeNodeFlags_.leaf | imgui.TreeNodeFlags_.bullet
            ):
                module.__shaderflow_ui__()
                imgui.spacing()
                imgui.tree_pop()

        imgui.end()
        imgui.pop_style_color()
        imgui.pop_style_var(6)
        imgui.render()
        self.imgui.render(imgui.get_draw_data())

    def __ui__(self) -> None:

        # Render status
        imgui.text(f"Resolution: {self.render_resolution} -> {self.resolution} @ {self.ssaa:.2f}x SSAA")

        # Framerate
        imgui.spacing()
        if (state := imgui.slider_float("Framerate", self.fps, 10, 240, "%.0f"))[0]:
            self.fps = round(state[1])
        for fps in (options := (24, 30, 60, 120, 144, 240)):
            if (state := imgui.button(f"{fps} Hz")):
                self.fps = fps
            if fps != options[-1]:
                imgui.same_line()

        # Temporal
        imgui.spacing()
        if (state := imgui.slider_float("Time Scale", self.speed.target, -2, 2, "%.2f"))[0]:
            self.speed.target = state[1]
        for scale in (options := (-10, -5, -2, -1, 0, 1, 2, 5, 10)):
            if (state := imgui.button(f"{scale}x")):
                self.speed.target = scale
            if scale != options[-1]:
                imgui.same_line()

        # SSAA
        imgui.spacing()
        if (state := imgui.slider_float("SSAA", self.ssaa, 0.01, 4, "%.2f"))[0]:
            self.ssaa = state[1]
        for ssaa in (options := (0.1, 0.25, 0.5, 1.0, 1.25, 1.5, 2.0, 4.0)):
            if (state := imgui.button(f"{ssaa}x")):
                self.ssaa = ssaa
            if ssaa != options[-1]:
                imgui.same_line()

        # Subsample
        imgui.spacing()
        if (state := imgui.slider_int("Subsample", self.subsample, 1, 4)) != self.subsample:
            self.subsample = state[1]

        # Quality
        imgui.spacing()
        if (state := imgui.slider_float("Quality", self.quality, 0, 100, "%.0f%%"))[0]:
            self.quality = state[1]
