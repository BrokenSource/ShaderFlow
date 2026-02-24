from __future__ import annotations

import contextlib
import gc
import importlib
import math
import os
import sys
import threading
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Optional, Self, Union

import moderngl
import numpy as np
from attrs import Factory, define, field
from cyclopts import App as Cyclopts
from cyclopts import Parameter
from imgui_bundle import imgui

import shaderflow
from shaderflow import logger
from shaderflow.camera import ShaderCamera
from shaderflow.exporting import ExportingHelper
from shaderflow.ffmpeg import FFmpeg
from shaderflow.frametimer import ShaderFrametimer
from shaderflow.keyboard import ShaderKeyboard
from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.resolution import Resolution
from shaderflow.scheduler import Scheduler
from shaderflow.shader import ShaderProgram
from shaderflow.temp.imgui_window import ModernglWindowRenderer
from shaderflow.utils import CycloUtils
from shaderflow.variable import ShaderVariable, Uniform

if TYPE_CHECKING:
    from moderngl_window.context.base import BaseWindow as ModernglWindow

# ---------------------------------------------------------------------------- #

class WindowBackend(Enum):
    Headless = "headless"
    GLFW     = "glfw"

    @classmethod
    def infer(cls) -> Self:

        # Optional external user override
        if (option := os.getenv("WINDOW_BACKEND")):
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

    backend: WindowBackend = Factory(WindowBackend.infer)
    """ModernGL Window backend, cannot be changed after creation"""

    window: 'ModernglWindow' = None
    """ModernGL Window class instance at `moderngl_window.context.<backend>.Window`"""

    opengl: moderngl.Context = None
    """ModernGL Context bound to this Scene"""

    quality: float = field(default=50.0, converter=lambda x: min(max(0.0, float(x)), 100.0))
    """Global quality level, if implemented on the shader/scene"""

    # -------------------------------------------|
    # Modules

    ffmpeg: FFmpeg = Factory(FFmpeg)
    """FFmpeg configuration for exporting videos"""

    modules: list[ShaderModule] = Factory(list)
    """List of all Modules in order of addition (including self)"""

    frametimer: ShaderFrametimer = None
    """Default Frametimer module"""

    keyboard: ShaderKeyboard = None
    """Default Keyboard module"""

    camera: ShaderCamera = None
    """Default Camera module"""

    shader: ShaderProgram = None
    """The main shader of the scene"""

    def __del__(self):
        for module in self.modules:
            module.destroy()
        with contextlib.suppress(AttributeError):
            self.opengl.release()
        with contextlib.suppress(AttributeError):
            self.window.destroy()
        gc.collect()

    # -------------------------------------------|
    # Super Sampling Anti-Aliasing

    _final: ShaderProgram = None
    """Internal shader used for downsampling final frames"""

    @property
    def fbo(self) -> moderngl.Framebuffer:
        return self._final.texture.fbo

    @property
    def components(self) -> int:
        return self._final.texture.components

    subsample: int = field(default=2, converter=lambda x: int(max(1, x)))
    """The kernel size of the final SSAA downsample"""

    # -------------------------------------------|

    def initialize(self) -> None:
        if (self.window is not None):
            return

        logger.info(f"Initializing scene {self.name} with backend {self.backend}")

        # Default modules
        self.frametimer = ShaderFrametimer(scene=self)
        self.keyboard = ShaderKeyboard(scene=self)
        self.camera = ShaderCamera(scene=self)

        # Linux: Use EGL for creating a OpenGL context, allows true headless with GPU acceleration
        # Note: (https://forums.developer.nvidia.com/t/81412) (https://brokensrc.dev/get/docker/)
        if (sys.platform == "linux") and (os.getenv("EGL", "1") == "1"):
            backend = "egl"

        # Dynamically import and instantiate the ModernGL Window class
        module = f"moderngl_window.context.{self.backend.value}"
        self.window = importlib.import_module(module).Window(
            size=self.resolution,
            title=self.title,
            resizable=self.resizable,
            visible=self.visible,
            fullscreen=self.fullscreen,
            backend=locals().get("backend"),
            vsync=False,
        )

        # Get OpenGL context
        self.opengl = self.window.ctx
        logger.info("OpenGL Renderer: ", self.opengl.info.get('GL_RENDERER'))

        imgui.create_context()
        self.imguio = imgui.get_io()
        self.imgui  = ModernglWindowRenderer(self.window)
        ShaderKeyboard.set_keymap(self.window.keys)

        # Bind window events
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
            import glfw
            glfw.set_cursor_enter_callback(self.window._window, (self.__window_mouse_enter_event__))
            glfw.set_drop_callback(self.window._window, (self.__window_files_dropped_event__))
            ShaderKeyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
            ShaderKeyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
            ShaderKeyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT

        # Create SSAA downsampler
        self._final = ShaderProgram(scene=self, name="iFinal")
        self._final.fragment = (shaderflow.resources/"shaders"/"fragment"/"final.glsl")
        self._final.texture.components = 3
        self._final.texture.dtype = np.uint8
        self._final.texture.final = True
        self._final.texture.track = 1.0
        self.shader = ShaderProgram(scene=self, name="iScreen")
        self.shader.texture.repeat(False)
        self.shader.texture.track = 1.0
        self.build()

    # -------------------------------------------|
    # Commands

    cli: Cyclopts = field(
        factory=lambda: Cyclopts(
            result_action="return_value",
            usage="",
        ),
        repr=False
    )

    def __attrs_post_init__(self) -> None:
        ShaderModule.__attrs_post_init__(self)
        self.name     = (self.name or type(self).__name__)
        self.cli.help = type(self).__doc__
        self.ffmpeg.cli_vcodecs(self.cli)
        self.ffmpeg.cli_acodecs(self.cli)
        self.cli.command(self.main)
        CycloUtils.chain(self.cli)

    # -------------------------------------------------------------------------|
    # Temporal

    time: float = field(default=0.0, converter=float)
    """Current scene time in seconds"""

    speed: float = field(default=1.0, converter=float)
    """Time scale factor, used for `dt`, which integrates to `time`"""

    runtime: float = field(default=10.0, converter=float)
    """Total duration of the scene, set by user or longest module"""

    fps: float = field(default=60.0, converter=float)
    """Target realtime or exporting framerate"""

    dt: float = field(default=0.0, converter=float)
    """Virtual delta time since last frame, scaled by `speed`"""

    rdt: float = field(default=0.0, converter=float)
    """Real life delta time since last frame"""

    @property
    def tau(self) -> float:
        """Normalized time value relative to runtime between 0 and 1"""
        return (self.time / self.runtime) % 1.0

    @property
    def cycle(self) -> float:
        """Normalized time value relative to runtime between 0 and 2pi"""
        return (self.tau * math.tau)

    @property
    def frametime(self) -> float:
        """Ideal delta between two frames"""
        return (1.0 / self.fps)

    @frametime.setter
    def frametime(self, value: float):
        self.fps = (1.0 / value)

    @property
    def frame(self) -> int:
        """Current frame index being rendered"""
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
        self.runtime /= self.speed
        return self.runtime

    # -------------------------------------------------------------------------|
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

    # -------------------------------------------------------------------------|
    # Resolution

    # # Scale

    _scale: float = field(default=1.0, converter=lambda x: max(0.01, x))

    @property
    def scale(self) -> float:
        """Resolution scale factor"""
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
        """Either the forced `self._aspect_ratio` or dynamic from `self.width/self.height`"""
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

        if (self.backend == WindowBackend.GLFW) and (self._aspect_ratio is not None):
            __import__("glfw").set_window_aspect_ratio(self.window._window, 2**16, int(2**16 / self._aspect_ratio))

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
        self.aspect_ratio = (ratio or self._aspect_ratio)
        self._scale = (scale or self._scale)
        self._ssaa = (ssaa or self._ssaa)

        # The parameters aren't trivial. The idea is to fit resolution from the scale-less components,
        # so scaling isn't carried over, then to apply scaling (self.resolution)
        resolution = Resolution.fit(
            old=(self._width, self._height),
            new=(width, height),
            max=bounds,
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

    def screenshot(self) -> np.ndarray:
        """Take a screenshot of the screen and return a numpy array with the data"""
        data = self.fbo.read(viewport=(0, 0, self.width, self.height))
        data = np.ndarray((self.height, self.width, self.components), dtype=np.uint8, buffer=data)
        return np.flipud(data)

    # -------------------------------------------------------------------------|
    # Main event loop

    scheduler: Scheduler = Factory(Scheduler)
    """Scheduler for the Scene, handles all the tasks and their execution"""

    vsync: Scheduler.Task = None
    """Task for the Scene's main event loop, the rendering of the next frame"""

    quit: bool = False

    def next(self, dt: float=0.0) -> None:
        """Integrate time, update all modules and render the next frame"""

        # Fixme: Windows: https://github.com/glfw/glfw/pull/1426
        # Immediately swap the buffer with previous frame for vsync
        if (not self.exporting):
            self.window.swap_buffers()

        # Update in reverse order of addition (child -> parent -> root)
        # Update non-shader first, as the pipeline might change
        for module in self.modules:
            if not isinstance(module, ShaderProgram):
                module.update()
        for module in reversed(self.modules):
            if isinstance(module, ShaderProgram):
                module.update()

        self._render_ui()

        # Temporal logic at end, so frame zero is t=0
        self.vsync.fps = self.fps
        self.dt    = dt * self.speed
        self.rdt   = dt
        self.time += self.dt

    realtime: bool = True
    """Realtime mode: Running with a window and user interaction"""

    exporting: bool = False
    """Is this Scene exporting to a video file?"""

    freewheel: bool = False
    """Non-realtime mode: Either Exporting, Rendering or Benchmarking"""

    headless: bool = False
    """Running Headlessly, without a window and user interaction"""

    def main(self, *,
        width: Annotated[Optional[int], Parameter(
            help="Width of the rendering resolution (None to keep or find by --ar aspect ratio)",
            group="🔴 Basic", name=("width", "-w"))] = 1920,

        height: Annotated[Optional[int], Parameter(
            help="Height of the rendering resolution (None to keep or find by --ar aspect ratio)",
            group="🔴 Basic", name=("height", "-h"))] = 1080,

        scale: Annotated[Optional[float], Parameter(
            help="Post-multiply width and height by a scale factor (None to keep)",
            group="🔴 Basic", name=("scale", "-S"))] = None,

        ratio: Annotated[Optional[Union[float, str]], Parameter(
            help="Force resolution aspect ratio (Examples: '16:9', '16/9', '1.777') (None for dynamic)",
            group="🔴 Basic", name=("ratio", "-r"))] = None,

        fps: Annotated[float, Parameter(
            help="Realtime target or video exact frames per second",
            group="🔴 Basic", name=("fps", "-f"))] = 60.0,

        frameskip: Annotated[bool, Parameter(
            help="Frames are skipped if the rendering is behind schedule (Limits maximum dt to 1/fps)",
            group="🔴 Window", name="frameskip", negative="rigorous")] = True,

        fullscreen: Annotated[bool, Parameter(
            help="Start the realtime window in fullscreen mode",
            group="🔴 Window", name="fullscreen", negative="windowed")] = False,

        quality: Annotated[float, Parameter(
            help="Global quality level (0-100%) (If implemented on the scene/shader)",
            group="🟡 Quality", name=("quality", "-q"))] = 50.0,

        ssaa: Annotated[float, Parameter(
            help="Super sampling anti aliasing factor (N**2 GPU cost)",
            group="🟡 Quality", name=("ssaa", "-s"))] = 1.0,

        subsample: Annotated[int, Parameter(
            help="Subpixel downsample kernel size for the final SSAA (1-4)",
            group="🟡 Quality")] = 2,

        output: Annotated[Optional[Path], Parameter(
            help="Output video file name and format",
            group="🟢 Exporting", name=("output", "-o"))] = None,

        time: Annotated[Optional[float], Parameter(
            help="Total length of the exported video (Loop duration) (None to keep, default 10 or longest module)",
            group="🟢 Exporting", name=("time", "-t"))] = None,

        speed: Annotated[float, Parameter(
            help="Time speed factor of the scene (Duration is stretched by 1/speed) (None to keep)",
            group="🟢 Exporting", name=("speed"))] = 1.0,

        freewheel: Annotated[bool, Parameter(
            help="Unlock the Scene's event loop framerate, implicit when exporting",
            group="🔵 Special", name=("freewheel"), negative="")] = False,

        raw: Annotated[bool, Parameter(
            help="Send raw OpenGL frames before GPU SSAA to FFmpeg (CPU Downsampling)",
            group="🔵 Special", negative="")] = False,

        turbo: Annotated[bool, Parameter(
            help="Fast data transfers to FFmpeg (disabling may fix segfaults in some systems)",
            group="🔵 TurboPipe")] = True,

        buffers: Annotated[int, Parameter(
            help="Number of pre-rendered frames to be sent to FFmpeg (only if turbo enabled)",
            group="🔵 TurboPipe")] = 5,
    ) -> Optional[Union[Path, bytes]]:
        """Main event loop of the scene"""
        self.initialize()
        self.exporting  = (bool(output))
        self.freewheel  = (self.exporting or freewheel)
        self.headless   = (self.freewheel)
        self.realtime   = (not self.headless)
        self.title      = (f"ShaderFlow • {self.name}")
        self.subsample  = (subsample)
        self.quality    = (quality)
        self.fullscreen = (fullscreen)
        self.speed      = (speed)
        self.fps        = (fps)
        self.time       = 0
        self.relay(ShaderMessage.Shader.Compile)
        self.scheduler.clear()

        # Set module defaults or overrides
        for module in self.modules:
            module.setup()

        self.set_duration(eval(time) if isinstance(time, str) else time)

        # Calculate the final resolution
        _width, _height = self.resize(
            width=width, height=height,
            ratio=ratio, scale=scale,
        )

        # Optimization: Save bandwidth by piping native frames
        if self.freewheel and (raw or self.ssaa < 1):
            self.resize(*self.render_resolution, scale=1, ssaa=1)
        else:
            self.ssaa = ssaa

        # Status tracker and refactored exporting utilities
        export = ExportingHelper(self)

        # Configure FFmpeg and Popen it
        if (self.exporting):
            export.ffmpeg_clean()
            export.ffmpeg_sizes(width=_width, height=_height)
            export.ffmpeg_output(output)
            export.make_buffers(buffers)
            export.ffhook()
            export.popen()
        if (self.freewheel):
            export.open_bar()

        # Some scenes might take a while to setup
        self.visible = (not self.headless)

        # Add self.next to the event loop
        self.vsync = self.scheduler.new(
            task=self.next,
            frequency=self.fps,
            freewheel=self.freewheel,
            frameskip=frameskip,
            precise=True,
        )

        while (task := self.scheduler.next()):
            if (task is not self.vsync):
                continue
            if (self.quit):
                break
            if (self.realtime):
                continue
            export.pipe(turbo=turbo)
            export.update()

            if (export.finished):
                export.finish()
                if (export.path_output):
                    output = self.ffmpeg.outputs[0].path
                if (export.pipe_output):
                    output = export.stdout.read()
                export.log_stats(output=output)
                return output

    # -------------------------------------------------------------------------|
    # Module

    def handle(self, message: ShaderMessage) -> None:

        if isinstance(message, ShaderMessage.Window.Close):
            logger.info("Received Window Close Event")
            self.hidden = True
            self.quit = True

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
                from datetime import datetime # isort: skip
                from PIL import Image
                image = Image.fromarray(self.screenshot())
                time  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                path  = shaderflow.directories.user_data_path/"screenshots"/f"({time}) {self.name}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"(F2 ) Saving screenshot to ({path})")
                threading.Thread(target=image.save, kwargs=dict(fp=path), daemon=True).start()

            elif (message.key == ShaderKeyboard.Keys.F11):
                logger.info("(F11) Toggling fullscreen")
                self.fullscreen = (not self.fullscreen)

        elif isinstance(message, (ShaderMessage.Mouse.Drag, ShaderMessage.Mouse.Position)):
            self.mouse_gluv = (message.u, message.v)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",   "iLayer",       None) # Special
        yield Uniform("float", "iTime",        self.time)
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

    # -------------------------------------------------------------------------|
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
        self.relay(ShaderMessage.Window.Close)

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
            self.speed += 0.2*dy
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

    # -------------------------------------------------------------------------|
    # Todo: Move UI to own class: For main menu, settings, exporting, etc

    imgui: ModernglWindowRenderer = None
    """ModernGL Imgui integration class bound to the Window"""

    imguio: Any = None
    """Imgui IO object"""

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
        imgui.begin(self.name, False, imgui.WindowFlags_.no_move | imgui.WindowFlags_.no_resize | imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.always_auto_resize)

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
        if (state := imgui.slider_float("Time Scale", self.speed, -2, 2, "%.2f"))[0]:
            self.speed = state[1]
        for scale in (options := (-10, -5, -2, -1, 0, 1, 2, 5, 10)):
            if (state := imgui.button(f"{scale}x")):
                self.speed = scale
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
