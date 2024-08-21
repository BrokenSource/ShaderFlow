import importlib
import inspect
import math
import os
import sys
from abc import abstractmethod
from collections import deque
from pathlib import Path
from subprocess import PIPE
from time import perf_counter
from typing import (
    Annotated,
    Any,
    Deque,
    Dict,
    Iterable,
    List,
    Optional,
    Self,
    Tuple,
    Union,
)

import glfw
import imgui
import moderngl
import PIL
import tqdm
import turbopipe
from attr import Factory, define, field
from dotmap import DotMap
from moderngl_window.context.base import BaseWindow as ModernglWindow
from moderngl_window.integrations.imgui import ModernglWindowRenderer as ModernglImgui
from typer import Option

import Broken
from Broken import (
    BrokenEnum,
    BrokenPath,
    BrokenPlatform,
    BrokenResolution,
    BrokenScheduler,
    BrokenTask,
    BrokenThread,
    BrokenTyper,
    OnceTracker,
    PlainTracker,
    clamp,
    denum,
    hyphen_range,
    limited_integer_ratio,
    log,
    selfless,
)
from Broken.Externals.FFmpeg import BrokenFFmpeg
from Broken.Loaders import LoaderBytes, LoaderString
from Broken.Types import Hertz, Seconds, Unchanged
from ShaderFlow import SHADERFLOW
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Modules.Camera import ShaderCamera
from ShaderFlow.Modules.Dynamics import DynamicNumber
from ShaderFlow.Modules.Frametimer import ShaderFrametimer
from ShaderFlow.Modules.Keyboard import ShaderKeyboard
from ShaderFlow.Shader import ShaderObject
from ShaderFlow.Variable import ShaderVariable


class WindowBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

@define
class ShaderScene(ShaderModule):
    __name__ = "Scene"

    modules: Deque[ShaderModule] = Factory(deque)
    """Deque of all Modules on the Scene, not a set for order preservation"""

    scheduler: BrokenScheduler = Factory(BrokenScheduler)
    """Scheduler for the Scene, handles all the tasks and their execution"""

    vsync: BrokenTask = None
    """Task for the Scene's main event loop, the rendering of the next frame"""

    # ShaderFlow modules
    frametimer: ShaderFrametimer = None
    keyboard: ShaderKeyboard = None
    camera: ShaderCamera = None
    ffmpeg: BrokenFFmpeg = None

    # # Fractional SSAA

    shader: ShaderObject = None
    """The main ShaderObject of the Scene, the visible content of the Window"""

    _final: ShaderObject = None
    """Internal ShaderObject used for a Fractional Super-Sampling Anti-Aliasing (SSAA). This shader
    samples the texture from the user's final self.shader, which is rendered at SSAA resolution"""

    alpha: bool = False
    """Makes the final texture have an alpha channel, useful for transparent windows. Exporting
    videos might fail, perhaps output a Chroma Key compatible video - add this to the shader:
    - `fragColor.rgb = mix(vec3(0, 1, 0), fragColor.rgb, fragColor.a);`"""

    quality: float = field(default=50, converter=lambda x: clamp(float(x), 0, 100))
    """Visual quality level (0-100%), if implemented on the Shader/Scene"""

    typer: BrokenTyper = Factory(lambda: BrokenTyper(chain=True))
    """This Scene's BrokenTyper instance for the CLI. Commands are added by any module in the
    `self.commands` method. The `self.main` is always added to it"""

    scene_panel: str = "🔥 Scene commands"

    def __post__(self):
        self.typer.description = (self.typer.description or self.__class__.__doc__)
        self.typer._panel = self.scene_panel
        self.typer.command(self.main, context=True)
        self.build()

    def cli(self, *args: List[Union[Any, str]]):
        """Run this Scene's CLI with added commands with the given arguments"""
        self.typer(*args)

    _built: OnceTracker = Factory(OnceTracker)

    def build(self):
        if self._built():
            return
        imgui.create_context()
        self.imguio = imgui.get_io()
        self.imguio.font_global_scale = 1
        self.imguio.fonts.add_font_from_file_ttf(
            str(Broken.BROKEN.RESOURCES.FONTS/"DejaVuSans.ttf"),
            16*self.imguio.font_global_scale,
        )

        # Default modules
        self.init_window()
        self.frametimer = ShaderFrametimer(scene=self)
        self.keyboard = ShaderKeyboard(scene=self)
        self.camera = ShaderCamera(scene=self)

        # Create the SSAA Workaround engines
        self._final = ShaderObject(scene=self, name="iFinal")
        self._final.texture.components = 3 + int(self.alpha)
        self._final.texture.dtype = "f1"
        self._final.texture.final = True
        self._final.texture.track = True
        self._final.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Final.glsl")
        self.shader = ShaderObject(scene=self, name="iScreen")
        self.shader.texture.track = True
        self.shader.texture.repeat(False)

    # ---------------------------------------------------------------------------------------------|
    # Temporal

    time: Seconds = field(default=0.0, converter=float)
    """Virtual time in seconds. Ideally, everything should depend on time, for flexibility"""

    speed: float = Factory(lambda: DynamicNumber(value=1, frequency=3))
    """Time scale factor, used for `dt`, which integrates to `time`"""

    runtime: Seconds = field(default=10.0, converter=float)
    """The longest module duration; overriden by the user; or default length of 10s"""

    fps: Hertz = field(default=60.0, converter=lambda x: max(float(x), 1.0))
    """Target frames per second rendering speed"""

    dt: Seconds = field(default=0.0, converter=float)
    """Virtual delta time since last frame, time scaled by `speed`. Use `self.rdt` for real delta"""

    rdt: Seconds = field(default=0.0, converter=float)
    """Real life, physical delta time since last frame. Use `self.dt` for time scaled version"""

    @property
    def tau(self) -> float:
        """Normalized time value relative to runtime between 0 and 1"""
        return ((self.time - self.frametime) / self.runtime)

    @property
    def cycle(self) -> float:
        """A number from 0 to 2pi that ends on the runtime ('normalized angular time')"""
        return (2 * math.pi * self.tau)

    @property
    def frametime(self) -> Seconds:
        """Ideal time between two frames. This value is coupled with `fps`"""
        return (1 / self.fps)

    @frametime.setter
    def frametime(self, value: Seconds):
        self.fps = (1 / value)

    @property
    def frame(self) -> int:
        """Current frame being rendered. This value is coupled with 'time' and 'fps'"""
        return round(self.time * self.fps)

    @frame.setter
    def frame(self, value: int):
        self.time = (value / self.fps)

    # Total Duration

    @property
    def duration(self) -> Seconds:
        """Alias to self.runtime. Set both with `.set_duration()`"""
        return self.runtime

    def set_duration(self, override: Seconds=None, *, minimum: Seconds=10) -> Seconds:
        """Either force the runtime to be 'override' or find the longest module lower bounded"""
        self.runtime = (override or minimum)
        for module in (not bool(override)) * self.modules:
            self.runtime = max(self.runtime, module.duration)
        self.runtime /= self.speed.value
        return self.runtime

    @property
    def total_frames(self) -> int:
        """The total frames this scene should render when exporting, if 'runtime' isn't changed"""
        return round(self.runtime * self.fps)

    # ---------------------------------------------------------------------------------------------|
    # Window synchronized properties

    # # Title

    _title: str = "ShaderFlow"

    @property
    def title(self) -> str:
        """Realtime window 'title' property"""
        return self._title

    @title.setter
    def title(self, value: str):
        log.debug(f"{self.who} Changing Window Title to ({value})")
        self.window.title = value
        self._title = value

    # # Resizable

    _resizable: bool = True

    @property
    def resizable(self) -> bool:
        """Realtime window 'is resizable' property"""
        return self._resizable

    @resizable.setter
    def resizable(self, value: bool):
        log.debug(f"{self.who} Changing Window Resizable to ({value})")
        self.window.resizable = value
        self._resizable = value

    # # Visible

    _visible: bool = False

    @property
    def visible(self) -> bool:
        """Realtime window 'is visible' property"""
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        log.debug(f"{self.who} Changing Window Visibility to ({value})")
        self.window.visible = value
        self._visible = value

    @property
    def hidden(self) -> bool:
        """Realtime window 'is hidden' property"""
        return not self.visible

    @hidden.setter
    def hidden(self, value: bool):
        self.visible = not value

    # # Window Fullscreen

    _fullscreen: bool = False

    @property
    def fullscreen(self) -> bool:
        """Window 'is fullscreen' property"""
        return self._fullscreen

    @fullscreen.setter
    def fullscreen(self, value: bool):
        log.debug(f"{self.who} Changing Window Fullscreen to ({value})")
        self._fullscreen = value
        try:
            self.window.fullscreen = value
        except AttributeError:
            pass

    # # Window Exclusive

    _exclusive: bool = False

    @property
    def exclusive(self) -> bool:
        """Window 'mouse exclusivity' property: Is the mouse cursor be locked to the window"""
        return self._exclusive

    @exclusive.setter
    def exclusive(self, value: bool):
        log.debug(f"{self.who} Changing Window Exclusive to ({value})")
        self.window.mouse_exclusivity = value
        self._exclusive = value

    # # Video modes and monitor

    monitor: int = field(default=os.getenv("MONITOR", 0), converter=int)

    @property
    def glfw_monitor(self) -> Optional[glfw._GLFWmonitor]:
        if (monitors := glfw.get_monitors()):
            return monitors[self.monitor]

    @property
    def glfw_video_mode(self) -> Optional[Dict]:
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
    def monitor_size(self) -> Optional[Tuple[int, int]]:
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

    # # Scale

    _scale: float = field(default=1.0, converter=lambda x: max(0.01, x))

    @property
    def scale(self) -> float:
        """Resolution scale factor, the `self.width` and `self.height` are multiplied by this"""
        return self._scale

    @scale.setter
    def scale(self, value: float):
        log.debug(f"{self.who} Changing Resolution Scale to ({value})")
        self.resize(scale=value)

    # # Width

    _width: int = field(default=1920, converter=lambda x: int(max(1, x)))
    """The scale-less rendering width of the Scene"""

    @property
    def width(self) -> int:
        """Rendering width (horizontal size) of the Scene"""
        return BrokenResolution.round(self._width * self._scale)

    @width.setter
    def width(self, value: int):
        self.resize(width=value)

    # # Height

    _height: int = field(default=1080, converter=lambda x: int(max(1, x)))
    """The scale-less rendering height of the Scene"""

    @property
    def height(self) -> int:
        """Rendering height (vertical size) of the Scene"""
        return BrokenResolution.round(self._height * self._scale)

    @height.setter
    def height(self, value: int):
        self.resize(height=value)

    # # SSAA

    _ssaa: float = field(default=1.0,  converter=lambda x: max(0.01, x))

    @property
    def ssaa(self) -> float:
        """Fractional Super Sampling Anti-Aliasing (SSAA) factor. Improves the image quality (>1) by
        rendering at a higher resolution and then downsampling, resulting in smoother edges at a
        significant GPU computational cost of O(N^2). Values lower than 1 (yield worse quality, but)
        are useful when the GPU can't keep up: when the resolution is too high or FPS is too low"""
        return self._ssaa

    @ssaa.setter
    def ssaa(self, value: float):
        log.debug(f"{self.who} Changing Fractional SSAA to {value}")
        self._ssaa = value
        self.relay(ShaderMessage.Shader.RecreateTextures)

    # # Resolution (With, Height)

    @property
    def resolution(self) -> Tuple[int, int]:
        """The resolution the Scene is rendering"""
        return (self.width, self.height)

    @resolution.setter
    def resolution(self, value: Tuple[int, int]):
        self.resize(*value)

    @property
    def render_resolution(self) -> Tuple[int, int]:
        """Internal 'true' rendering resolution for SSAA. Same as `self.resolution*self.ssaa`"""
        return BrokenResolution.round(self.width*self.ssaa, self.height*self.ssaa)

    # # Aspect Ratio

    _aspect_ratio: float = None

    @property
    def aspect_ratio(self) -> float:
        """Either the forced `self._aspect_ratio` or dynamic from `self.width/self.height`. When set
        and resizing, the logic of `BrokenResolution.fit` is applied to enforce ratios"""
        return self._aspect_ratio or (self._width/self._height)

    @aspect_ratio.setter
    def aspect_ratio(self, value: Union[float, str]):
        log.debug(f"{self.who} Changing Aspect Ratio to {value}")

        # The aspect ratio can be sent as a fraction or "none", "false"
        if isinstance(value, str):
            value = eval(value.replace(":", "/").capitalize())

        # Optimization: Only change if different
        if (self._aspect_ratio == value):
            return

        self._aspect_ratio = value

        if (self.backend == WindowBackend.GLFW):
            num, den = limited_integer_ratio(self._aspect_ratio, limit=2**20) or (glfw.DONT_CARE, glfw.DONT_CARE)
            glfw.set_window_aspect_ratio(self.window._window, num, den)

    def resize(self,
        width: Union[int, float]=Unchanged,
        height: Union[int, float]=Unchanged,
        *,
        ratio: Union[Unchanged, float, str]=Unchanged,
        scale: float=Unchanged
    ) -> Tuple[int, int]:
        """
        Resize the true final rendering resolution of the Scene. Rounded to nearest multiple of 2,
        so FFmpeg is happy, and limited by the monitor resolution if realtime

        Args:
            width:  New width of the Scene, None to not change
            height: New height of the Scene, None to not change

        Returns:
            Tuple[int, int]: The new width and height of the Scene
        """

        # Maybe update auxiliary properties
        self.aspect_ratio = (ratio or self._aspect_ratio)
        self._scale = (scale or self._scale)

        # The parameters aren't trivial. The idea is to fit resolution from the scale-less components,
        # so scaling isn't carried over, then to apply scaling (self.resolution)
        resolution = BrokenResolution.fit(
            old=(self._width, self._height),
            new=(width, height),
            max=(self.monitor_size),
            ar=self._aspect_ratio
        )

        # Optimization: Only resize when resolution changes
        if (resolution != (self.width, self.height)):
            self._width, self._height = resolution
            self.window.size = self.resolution
            self.relay(ShaderMessage.Shader.RecreateTextures)
            log.info(f"{self.who} Resized Window to {self.resolution}")

        return self.resolution

    # ---------------------------------------------------------------------------------------------|
    # Window, OpenGL, Backend

    backend: WindowBackend = WindowBackend.get(os.getenv("WINDOW_BACKEND", WindowBackend.GLFW))
    """The ModernGL Window Backend. **Cannot be changed after creation**. Can also be set with the
    environment variable `WINDOW_BACKEND=<backend>`, where `backend = {glfw, headless}`"""

    opengl: moderngl.Context = None
    """ModernGL Context of this Scene. The thread accessing this MUST own or ENTER its context for
    creating, changing, deleting objects; more often than not, it's the Main thread"""

    window: ModernglWindow = None
    """ModernGL Window instance at `site-packages/moderngl_window.context.<self.backend>.Window`"""

    imgui: ModernglImgui = None
    """ModernGL Imgui integration class bound to the Window"""

    imguio: Any = None
    """Imgui IO object"""

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""
        if self.window:
            raise RuntimeError("Window backend cannot be changed after creation")

        # Linux: Use EGL for creating a OpenGL context, allows true headless with GPU acceleration
        # Note: (https://forums.developer.nvidia.com/t/81412) (https://brokensrc.dev/get/docker/)
        backend = ("egl" if BrokenPlatform.OnLinux and eval(os.getenv("WINDOW_EGL", "1")) else None)

        # Dynamically import the ModernGL Window Backend and instantiate it. Vsync is on our side 😉
        module = f"moderngl_window.context.{denum(self.backend).lower()}"
        self.window = importlib.import_module(module).Window(
            size=self.resolution,
            title=self.title,
            resizable=self.resizable,
            visible=self.visible,
            fullscreen=self.fullscreen,
            vsync=False,
            backend=backend
        )
        ShaderKeyboard.set_keymap(self.window.keys)
        self.imgui  = ModernglImgui(self.window)
        self.opengl = self.window.ctx

        # Bind window events to relay
        self.window.resize_func               = self.__window_resize__
        self.window.close_func                = self.__window_close__
        self.window.iconify_func              = self.__window_iconify__
        self.window.key_event_func            = self.__window_key_event__
        self.window.mouse_position_event_func = self.__window_mouse_position_event__
        self.window.mouse_press_event_func    = self.__window_mouse_press_event__
        self.window.mouse_release_event_func  = self.__window_mouse_release_event__
        self.window.mouse_drag_event_func     = self.__window_mouse_drag_event__
        self.window.mouse_scroll_event_func   = self.__window_mouse_scroll_event__
        self.window.unicode_char_entered_func = self.__window_unicode_char_entered__
        self.window.files_dropped_event_func  = self.__window_files_dropped_event__

        if (self.backend == WindowBackend.GLFW):
            BrokenThread.new(target=self.window.set_icon, icon_path=Broken.PROJECT.RESOURCES.ICON_PNG, daemon=True)
            glfw.set_cursor_enter_callback(self.window._window, lambda _, enter: self.__window_mouse_enter_event__(inside=enter))
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)
            ShaderKeyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
            ShaderKeyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
            ShaderKeyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT

        log.info(f"OpenGL Renderer: {self.opengl.info['GL_RENDERER']}")

    def read_screen(self) -> bytes:
        """Take a screenshot of the screen and return raw bytes. Length `width*height*components`"""
        return self.window.fbo.read(viewport=(0, 0, self.width, self.height))

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
        log.info(f"{self.who} Reading file ({file})")
        return LoaderBytes(file) if bytes else LoaderString(file)

    # ---------------------------------------------------------------------------------------------|
    # Main event loop

    quit: PlainTracker = Factory(lambda: PlainTracker(False))
    """Should the scene end the main event loop? Use as `if scene.quit():`"""

    def next(self, dt: float) -> Self:
        """Integrate time, update all modules and render the next frame"""

        # Fixme: Windows: https://github.com/glfw/glfw/pull/1426
        # Immediately swap the buffer with previous frame for vsync
        self.window.swap_buffers()

        # Temporal logic
        dt = min(dt, 1)
        self.speed.next(dt=abs(dt))
        self.vsync.fps = self.fps
        self.dt    = dt * self.speed
        self.rdt   = dt
        self.time += self.dt

        # Note: Updates in reverse order of addition (child -> parent)
        # Note: Update non-engine first, as the pipeline might change
        for module in self.modules:
            if not isinstance(module, ShaderObject):
                module.update()
        for module in reversed(self.modules):
            if isinstance(module, ShaderObject):
                module.update()

        self._render_ui()
        return self

    exporting: bool = True
    """Is this Scene exporting to a video file?"""

    rendering: bool = False
    """Either Exporting, Rendering or Benchmarking. 'Not Realtime' mode"""

    realtime: bool = False
    """Running with a window and user interaction"""

    headless: bool = False
    """Running Headlessly, without a window and user interaction"""

    benchmark: bool = False
    """Stress test the rendering speed of the Scene"""

    loop: int = field(default=1, converter=int)
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
        width:      Annotated[int,   Option("--width",      "-w", help="[bold red](🔴 Basic  )[/bold red] Width  of the rendering resolution [medium_purple3](None to keep or find by --ar aspect ratio)[/medium_purple3] [dim](1920 on init)[/dim]")]=None,
        height:     Annotated[int,   Option("--height",     "-h", help="[bold red](🔴 Basic  )[/bold red] Height of the rendering resolution [medium_purple3](None to keep or find by --ar aspect ratio)[/medium_purple3] [dim](1080 on init)[/dim]")]=None,
        ratio:      Annotated[str,   Option("--ar",         "-X", help="[bold red](🔴 Basic  )[/bold red] Force resolution aspect ratio [green](examples: '16:9', '16/9', '1.777')[/green] [medium_purple3](None for dynamic)[/medium_purple3]")]=None,
        scale:      Annotated[float, Option("--scale",      "-x", help="[bold red](🔴 Basic  )[/bold red] Post-multiply width and height by a scale factor [medium_purple3](None to keep)[/medium_purple3] [dim](1.0 on init)[dim]")]=None,
        fps:        Annotated[float, Option("--fps",        "-f", help="[bold red](🔴 Basic  )[/bold red] Target frames per second [medium_purple3](defaults to the monitor framerate on realtime else 60)[/medium_purple3]")]=None,
        fullscreen: Annotated[bool,  Option("--fullscreen",       help="[bold red](🔴 Window )[/bold red] Start the realtime window in fullscreen mode [medium_purple3](toggle with F11)[/medium_purple3]")]=False,
        maximize:   Annotated[bool,  Option("--maximize",   "-M", help="[bold red](🔴 Window )[/bold red] Start the realtime window in maximized mode")]=False,
        quality:    Annotated[float, Option("--quality",    "-q", help="[bold yellow](🟡 Quality)[/bold yellow] Global quality level [green](0-100%)[/green] [yellow](if supported by the scene/shader)[/yellow] [medium_purple3](None to keep, default 50%)[/medium_purple3]")]=None,
        ssaa:       Annotated[float, Option("--ssaa",       "-s", help="[bold yellow](🟡 Quality)[/bold yellow] Super sampling anti aliasing factor [green](0-2)[/green] [yellow](O(N^2) GPU cost)[/yellow] [medium_purple3](None to keep, default 1.0)[/medium_purple3]")]=None,
        render:     Annotated[bool,  Option("--render",     "-r", help="[bold green](🟢 Export )[/bold green] Export the Scene to a video file [medium_purple3](defined on --output, and implicit if so)[/medium_purple3]")]=False,
        output:     Annotated[str,   Option("--output",     "-o", help="[bold green](🟢 Export )[/bold green] Output video file name [green]('absolute', 'relative', 'plain' path)[/green] [dim]($base/$(plain or $scene-$date))[/dim]")]=None,
        base:       Annotated[Path,  Option("--base",       "-D", help="[bold green](🟢 Export )[/bold green] Export base directory [medium_purple3](if plain name)[/medium_purple3]")]=Broken.PROJECT.DIRECTORIES.DATA,
        time:       Annotated[float, Option("--time",       "-t", help="[bold green](🟢 Export )[/bold green] Total length of the exported video [dim](loop duration)[/dim] [medium_purple3](None to keep, default 10 or longest module)[/medium_purple3]")]=None,
        speed:      Annotated[float, Option("--speed",      "-S", help="[bold green](🟢 Export )[/bold green] Time speed factor of the scene [yellow](duration is stretched by [italic]1/speed[/italic])[/yellow] [medium_purple3](None to keep)[/medium_purple3] [dim](1 on init)[/dim]")]=None,
        format:     Annotated[str,   Option("--format",     "-F", help="[bold green](🟢 Export )[/bold green] Output video container [green]('mp4', 'mkv', 'webm', 'avi, '...')[/green] [yellow](--output one is prioritized)[/yellow]")]="mp4",
        vcodec:     Annotated[str,   Option("--vcodec",     "-c", help="[bold green](🟢 Export )[/bold green] Video codec [green]('h264', 'h264-nvenc', 'h265, 'hevc-nvenc', 'vp9', 'av1-{aom,svt,nvenc,rav1e}')[/green]")]="h264",
        acodec:     Annotated[str,   Option("--acodec",     "-a", help="[bold green](🟢 Export )[/bold green] Audio codec [green]('aac', 'mp3', 'flac', 'wav', 'opus', 'ogg', 'copy', 'none', 'empty')[/green]")]="copy",
        loop:       Annotated[int,   Option("--loop",       "-l", help="[bold blue](🔵 Special)[/bold blue] Exported videos loop copies [yellow](final duration is multiplied by this)[/yellow] [dim](1 on init)[/dim]")]=None,
        benchmark:  Annotated[bool,  Option("--benchmark",  "-B", help="[bold blue](🔵 Special)[/bold blue] Benchmark the Scene's speed on raw rendering [medium_purple3](use SKIP_GPU=1 for CPU only benchmark)[/medium_purple3]")]=False,
        raw:        Annotated[bool,  Option("--raw",              help="[bold blue](🔵 Special)[/bold blue] Send raw OpenGL frames before GPU SSAA to FFmpeg [medium_purple3](enabled if ssaa < 1)[/medium_purple3] [dim](CPU Downsampling)[/dim]")]=False,
        open:       Annotated[bool,  Option("--open",             help="[bold blue](🔵 Special)[/bold blue] Open the directory of the exports after finishing rendering")]=False,
        batch:      Annotated[str,   Option("--batch",      "-b", help="[bold white](🔘 Testing)[/bold white] [dim]Hyphenated indices range to export multiple videos, if implemented [medium_purple3](1,5-7,10)[/medium_purple3][/dim]")]="0",
        nbuffer:    Annotated[int,   Option("--nbuffer",    "-N", help="[bold white](🔘 Testing)[/bold white] [dim]Number of buffers to use for FFmpeg data feeding[/dim]")]=2,
        noturbo:    Annotated[bool,  Option("--no-turbo",         help="[bold white](🔘 Testing)[/bold white] [dim]Disables [steel_blue1][link=https://github.com/BrokenSource/TurboPipe]TurboPipe[/link][/steel_blue1] (faster FFmpeg data feeding throughput)[/dim]")]=False,
        _index:     Annotated[Optional[int],  Option(hidden=True)]=None,
        _started:   Annotated[Optional[str],  Option(hidden=True)]=None,
        _outputs:   Annotated[Optional[Path], Option(hidden=True)]=None,
    ) -> Optional[List[Path]]:
        """
        Main event loop of this ShaderFlow Scene. Start a realtime window, exports to video, stress test speeds
        """

        # -----------------------------------------------------------------------------------------|
        # Implementation of batch exporting: Recurse on this method providing all locals()

        if (_index is None):
            _started: str = __import__("arrow").now().format("YYYY-MM-DD HH-mm-ss")
            _outputs: List[Path] = list()

            for _index in hyphen_range(batch):
                self.main(**selfless(locals()))

            (open and self.exporting) and BrokenPath.explore(_outputs[0].parent)
            return _outputs

        # -----------------------------------------------------------------------------------------|

        self.exporting  = (render or bool(output))
        self.rendering  = (self.exporting or benchmark)
        self.realtime   = (not self.rendering)
        self.headless   = (self.rendering)
        self.benchmark  = (benchmark)
        self.title      = (f"ShaderFlow | {self.__name__}")
        self.fps        = (fps or self.monitor_framerate)
        self.quality    = (quality or self.quality)
        self.loop       = (loop or self.loop)
        self.ssaa       = (ssaa or self.ssaa)
        self.fullscreen = (fullscreen)
        self.index      = _index
        self.time       = 0
        self.speed.set(speed or self.speed.value)

        for module in self.modules:
            module.setup()
        self.set_duration(time)

        # A hidden window resize might trigger the resize callback depending on the platform
        self.relay(ShaderMessage.Shader.Compile)
        self._width, self._height = (1920, 1080)
        _width, _height = self.resize(width, height, ratio=ratio, scale=scale)

        # Optimization: Save bandwidth by piping native frames on ssaa < 1
        if self.rendering and (raw or self.ssaa < 1):
            self.resolution = self.render_resolution
            self.ssaa = 1

        # Configure FFmpeg and Popen it
        if (self.rendering):
            export = Path(output or f"({_started}) {self.__name__}")
            export = export if export.is_absolute() else (base/export)
            export = export.with_suffix("." + (export.suffix or format).replace(".", ""))
            export = self.export_name(export)

            self.ffmpeg = (BrokenFFmpeg(time=self.runtime).quiet()
                .pipe_input(pixel_format=("rgba" if self.alpha else "rgb24"),
                    width=self.width, height=self.height, framerate=self.fps)
                .scale(width=_width, height=_height)
                .output(path=export)
            )

            # Apply default good codec options on the video
            self.ffmpeg.apply_vcodec_str(vcodec)
            self.ffmpeg.apply_acodec_str(acodec)

            for module in self.modules:
                if module is self: continue
                module.ffmpeg(self.ffmpeg)

            if self.exporting:
                self.ffmpeg = self.ffmpeg.popen(stdin=PIPE)
                fileno = self.ffmpeg.stdin.fileno()
                buffers = [
                    self.opengl.buffer(reserve=self._final.texture.size_t)
                    for _ in range(max(2, nbuffer))
                ]

            status = DotMap(
                start=perf_counter(),
                frame=0,
                bar=tqdm.tqdm(
                    total=self.total_frames,
                    desc=f"Scene #{self.index} ({type(self).__name__}) → Video",
                    dynamic_ncols=True,
                    colour="#43BFEF",
                    leave=False,
                    unit=" frames",
                    mininterval=1/30,
                    maxinterval=0.1,
                    smoothing=0.1,
                )
            )

        # Some scenes might take a while to setup
        self.visible = not self.headless

        if (self.backend == WindowBackend.GLFW and maximize):
            glfw.maximize_window(self.window._window)

        # Add self.next to the event loop
        self.vsync = self.scheduler.new(
            task=self.next,
            frequency=self.fps,
            freewheel=self.rendering,
            precise=True,
        )

        # Main rendering loop
        while (self.rendering) or (not self.quit()):
            task = self.scheduler.next()

            # Only continue if exporting
            if (task.output is not self):
                continue
            if self.realtime:
                continue
            status.bar.update(1)
            status.frame += 1

            # Write a new frame to FFmpeg
            if self.exporting:
                buffer = (buffers[status.frame % nbuffer])
                turbopipe.sync(buffer)

                # Always buffer-proxy, great speed up on Intel ARC and minor elsewhere
                self._final.texture.fbo().read_into(buffer)

                # TurboPipe can be slower on iGPU systems, make it opt-out
                if noturbo:
                    self.ffmpeg.stdin.write(buffer.read())
                else:
                    turbopipe.pipe(buffer, fileno)

            # Finish exporting condition
            if (status.frame < self.total_frames):
                continue
            status.bar.close()

            if self.exporting:
                log.info("Waiting for FFmpeg process to finish (Queued writes, codecs lookahead, buffers, etc)")
                turbopipe.close()
                self.ffmpeg.stdin.close()
                self.ffmpeg.wait()

            if (self.loop > 1):
                log.info(f"Repeating video ({self.loop-1} times)")
                export.rename(temporary := export.with_stem(f"{export.stem}-loop"))
                (BrokenFFmpeg(stream_loop=(self.loop-1)).quiet().copy_audio().copy_video()
                    .input(temporary).output(export, pixel_format=None).run())
                temporary.unlink()
            _outputs.append(export)

            # Log stats
            status.took = (perf_counter() - status.start)
            log.info(f"Finished rendering ({export})", echo=(not self.benchmark))
            log.info((
                f"• Stats: "
                f"(Took [cyan]{status.took:.2f}s[/cyan]) at "
                f"([cyan]{self.frame/status.took:.2f}fps[/cyan] | "
                f"[cyan]{self.runtime/status.took:.2f}x[/cyan] Realtime) with "
                f"({status.frame} Total Frames)"
            ))
            break

    # ---------------------------------------------------------------------------------------------|
    # Module

    def handle(self, message: ShaderMessage) -> None:

        if isinstance(message, ShaderMessage.Window.Close):
            log.info(f"{self.who} Received Window Close Event")
            self.hidden = True
            self.quit(True)

        elif isinstance(message, ShaderMessage.Keyboard.KeyDown):
            if message.key == ShaderKeyboard.Keys.O:
                log.info(f"{self.who} (O  ) Resetting the Scene")
                for module in self.modules:
                    module.setup()
                self.time = 0

            elif message.key == ShaderKeyboard.Keys.R:
                log.info(f"{self.who} (R  ) Reloading Shaders")
                for module in self.modules:
                    if isinstance(module, ShaderObject):
                        module.compile()

            elif message.key == ShaderKeyboard.Keys.TAB:
                log.info(f"{self.who} (TAB) Toggling Menu")
                self.render_ui = not self.render_ui

            elif message.key == ShaderKeyboard.Keys.F1:
                log.info(f"{self.who} (F1 ) Toggling Exclusive Mode")
                self.exclusive = not self.exclusive

            elif message.key == ShaderKeyboard.Keys.F2:
                import arrow
                time  = arrow.now().format("YYYY-MM-DD_HH-mm-ss")
                image = PIL.Image.frombytes("RGB", self.resolution, self.read_screen())
                image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
                path  = Broken.PROJECT.DIRECTORIES.SCREENSHOTS/f"({time}) {self.__name__}.png"
                log.minor(f"{self.who} (F2 ) Saving Screenshot to ({path})")
                BrokenThread.new(target=image.save, fp=path)

            elif message.key == ShaderKeyboard.Keys.F11:
                log.info(f"{self.who} (F11) Toggling Fullscreen")
                self.fullscreen = not self.fullscreen

        elif isinstance(message, (ShaderMessage.Mouse.Drag, ShaderMessage.Mouse.Position)):
            self.mouse_gluv = (message.u, message.v)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "float", "iTime",        self.time)
        yield ShaderVariable("uniform", "float", "iDuration",    self.duration)
        yield ShaderVariable("uniform", "float", "iDeltaTime",   self.dt)
        yield ShaderVariable("uniform", "vec2",  "iResolution",  self.resolution)
        yield ShaderVariable("uniform", "float", "iWantAspect",  self.aspect_ratio)
        yield ShaderVariable("uniform", "float", "iQuality",     self.quality/100)
        yield ShaderVariable("uniform", "float", "iSSAA",        self.ssaa)
        yield ShaderVariable("uniform", "float", "iFrameRate",   self.fps)
        yield ShaderVariable("uniform", "int",   "iFrame",       self.frame)
        yield ShaderVariable("uniform", "bool",  "iRealtime",    self.realtime)
        yield ShaderVariable("uniform", "vec2",  "iMouse",       self.mouse_gluv)
        yield ShaderVariable("uniform", "bool",  "iMouseInside", self.mouse_inside)
        for i in range(1, 6):
            yield ShaderVariable("uniform", "bool", f"iMouse{i}", self.mouse_buttons[i])

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

    def __window_files_dropped_event__(self, *stuff: list[str]) -> None:
        self.relay(ShaderMessage.Window.FileDrop(files=stuff[1]))

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

    mouse_gluv: Tuple[float, float] = Factory(lambda: (0, 0))

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

    mouse_buttons: Dict[int, bool] = Factory(lambda: {k: False for k in range(1, 6)})

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

    def __window_mouse_enter_event__(self, inside: bool) -> None:
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
            self.camera.rotate(self.camera.base_z, angle=math.degrees(angle))
            return

        elif self.exclusive:
            self.camera.apply_zoom(-dy/500)
            self.camera.rotate(self.camera.base_z, angle=-dx/10)
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

        self._final.texture.fbo().use()
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 8)
        imgui.push_style_var(imgui.STYLE_TAB_ROUNDING, 8)
        imgui.push_style_var(imgui.STYLE_GRAB_ROUNDING, 8)
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 8)
        imgui.push_style_var(imgui.STYLE_CHILD_ROUNDING, 8)
        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, 0.1, 0.1, 0.1, 0.5)
        imgui.new_frame()
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_bg_alpha(0.6)
        imgui.begin(f"{self.__name__}", False, imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_COLLAPSE  | imgui.WINDOW_ALWAYS_AUTO_RESIZE)

        # Render every module
        for module in self.modules:
            if imgui.tree_node(f"{module.uuid:>2} - {type(module).__name__.replace('ShaderFlow', '')}", imgui.TREE_NODE_BULLET | imgui.TREE_NODE_DEFAULT_OPEN):
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
        for fps in (options := [24, 30, 60, 120, 144, 240]):
            if (state := imgui.button(f"{fps} Hz")):
                self.fps = fps
            if fps != options[-1]:
                imgui.same_line()

        # Temporal
        imgui.spacing()
        if (state := imgui.slider_float("Time Scale", self.speed.target, -2, 2, "%.2f"))[0]:
            self.speed.target = state[1]
        for scale in (options := [-10, -5, -2, -1, 0, 1, 2, 5, 10]):
            if (state := imgui.button(f"{scale}x")):
                self.speed.target = scale
            if scale != options[-1]:
                imgui.same_line()

        # SSAA
        imgui.spacing()
        if (state := imgui.slider_float("SSAA", self.ssaa, 0.01, 2, "%.2f"))[0]:
            self.ssaa = state[1]
        for ssaa in (options := [0.1, 0.25, 0.5, 1.0, 1.25, 1.5, 2.0]):
            if (state := imgui.button(f"{ssaa}x")):
                self.ssaa = ssaa
            if ssaa != options[-1]:
                imgui.same_line()

        # Quality
        imgui.spacing()
        if (state := imgui.slider_float("Quality", self.quality, 0, 100, "%.0f%%"))[0]:
            self.quality = state[1]
