import importlib
import math
import os
import time
from abc import abstractmethod
from collections import deque
from pathlib import Path
from subprocess import PIPE
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
from attr import Factory, define, field
from dotmap import DotMap
from loguru import logger as log
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
    SameTracker,
    clamp,
    denum,
    flatten,
    hyphen_range,
    limited_integer_ratio,
)
from Broken.Externals.FFmpeg import (
    BrokenFFmpeg,
    FFmpegAudioCodec,
    FFmpegFilterFactory,
    FFmpegFormat,
    FFmpegH264Preset,
    FFmpegH264Quality,
    FFmpegH264Tune,
    FFmpegHWAccel,
    FFmpegPixelFormat,
    FFmpegVideoCodec,
)
from Broken.Loaders import LoaderBytes, LoaderString
from Broken.Types import Hertz, Seconds, Unchanged
from ShaderFlow import SHADERFLOW
from ShaderFlow.Message import Message
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Modules.Camera import ShaderCamera
from ShaderFlow.Modules.Dynamics import DynamicNumber
from ShaderFlow.Modules.Frametimer import ShaderFrametimer
from ShaderFlow.Modules.Keyboard import ShaderKeyboard
from ShaderFlow.Shader import ShaderObject
from ShaderFlow.Variable import ShaderVariable


class ShaderBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

@define
class ShaderScene(ShaderModule):
    __name__ = "Scene"

    # # Base modules

    modules: Deque[ShaderModule] = Factory(deque)
    """Deque of all Modules on the Scene, not a set for order preservation"""

    # Scheduling
    scheduler: BrokenScheduler = Factory(BrokenScheduler)
    vsync: BrokenTask = None

    # ShaderFlow modules
    camera: ShaderCamera = None
    keyboard: ShaderKeyboard = None
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

    quality: float = field(default=80, converter=lambda x: clamp(x, 0, 100))
    """Rendering Quality, if implemented - either on the GPU Shader or CPU Python side"""

    def build(self):

        # Init Imgui
        imgui.create_context()
        self.imguio = imgui.get_io()
        self.imguio.font_global_scale = 1
        self.imguio.fonts.add_font_from_file_ttf(
            str(Broken.BROKEN.RESOURCES.FONTS/"DejaVuSans.ttf"),
            16*self.imguio.font_global_scale,
        )

        # Default modules
        self.init_window()
        log.info(f"{self.who} Adding default base Scene modules")
        ShaderFrametimer(scene=self)
        self.keyboard = ShaderKeyboard(scene=self)
        self.camera   = ShaderCamera(scene=self)

        # Create the SSAA Workaround engines
        log.info(f"{self.who} Creating SSAA Implementation")
        self.shader = ShaderObject(scene=self)
        self.shader.texture.name = "iScreen"
        self.shader.texture.track = True
        self.shader.texture.repeat(False)
        self._final = ShaderObject(scene=self)
        self._final.texture.components = 3 + int(self.alpha)
        self._final.texture.dtype = "f1"
        self._final.texture.final = True
        self._final.texture.track = True
        self._final.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Final.glsl")

    # ---------------------------------------------------------------------------------------------|
    # Temporal

    time: Seconds = 0.0
    """Current time in seconds. Ideally, everything should depend on time, for flexibility"""

    tempo: float = Factory(lambda: DynamicNumber(value=1, frequency=3))
    """Time scale factor, used for `dt`, which integrates to `time`"""

    runtime: float = field(default=10.0, converter=float)
    """The longest module duration; overriden by the user; or default length of 10s"""

    fps: Hertz = 60.0
    """Target frames per second rendering speed"""

    dt: Seconds = 0.0
    """Virtual delta time since last frame, time scaled by `tempo`"""

    rdt: Seconds = 0.0
    """Real life, physical delta time since last frame"""

    @property
    def tau(self) -> float:
        """Normalized time value relative to runtime between 0 and 1"""
        return self.time / self.runtime

    @property
    def frametime(self) -> Seconds:
        """Ideal time between two frames, coupled with `fps`"""
        return 1/self.fps

    @frametime.setter
    def frametime(self, value: Seconds) -> None:
        self.fps = 1/value

    @property
    def frame(self) -> int:
        """Current frame being rendered. Coupled with 'time' and 'fps'"""
        return int(self.time * self.fps)

    @frame.setter
    def frame(self, value: int) -> None:
        self.time = value / self.fps

    # Total Duration

    @property
    def duration(self) -> float:
        return self.runtime

    def set_duration(self, override: float=None, *, default: float=10) -> float:
        self.runtime = (override or default)
        for module in (not bool(override)) * self.modules:
            self.runtime = max(self.runtime, module.duration)
        return self.runtime

    @property
    def total_frames(self) -> int:
        return int(self.runtime * self.fps)

    # ---------------------------------------------------------------------------------------------|
    # Window synchronized properties

    # # Title

    _title: str = "ShaderFlow"

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        log.debug(f"{self.who} Changing Window Title to ({value})")
        self.window.title = value
        self._title = value

    # # Resizable

    _resizable: bool = True

    @property
    def resizable(self) -> bool:
        return self._resizable

    @resizable.setter
    def resizable(self, value: bool) -> None:
        log.debug(f"{self.who} Changing Window Resizable to ({value})")
        self.window.resizable = value
        self._resizable = value

    # # Visible

    _visible: bool = False

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        log.debug(f"{self.who} Changing Window Visibility to ({value})")
        self.window.visible = value
        self._visible = value

    # # Window Fullscreen

    _fullscreen: bool = False

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    @fullscreen.setter
    def fullscreen(self, value: bool) -> None:
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
        return self._exclusive

    @exclusive.setter
    def exclusive(self, value: bool) -> None:
        log.debug(f"{self.who} Changing Window Exclusive to ({value})")
        self.window.mouse_exclusivity = value
        self._exclusive = value

    # # Video modes and monitor

    monitor: int = os.environ.get("MONITOR", 0)

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
        """Note: Defaults to 60 if no monitor is found"""
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
    def scale(self, value: float) -> None:
        log.debug(f"{self.who} Changing Resolution Scale to ({value})")
        self.resize(scale=value)

    # # Width

    _width: int = field(default=1920, converter=lambda x: int(max(1, x)))

    @property
    def width(self) -> int:
        """Rendering width (horizontal size) of the Scene in pixels"""
        return BrokenResolution.round_component(self._width * self.scale)

    @width.setter
    def width(self, value: int) -> None:
        self.resize(width=value)

    # # Height

    _height: int = field(default=1080, converter=lambda x: int(max(1, x)))

    @property
    def height(self) -> int:
        """Rendering height (vertical size) of the Scene in pixels"""
        return BrokenResolution.round_component(self._height * self.scale)

    @height.setter
    def height(self, value: int) -> None:
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
    def ssaa(self, value: float) -> None:
        log.debug(f"{self.who} Changing Fractional SSAA to {value}")
        self._ssaa = value
        self.relay(Message.Shader.RecreateTextures)

    # # Resolution (With, Height)

    @property
    def resolution(self) -> Tuple[int, int]:
        """The resolution the Scene is rendering in pixels"""
        return BrokenResolution.round_resolution(self.width, self.height)

    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        self.resize(*value)

    @property
    def render_resolution(self) -> Tuple[int, int]:
        """Internal 'true' rendering resolution for SSAA. Same as `self.resolution*self.ssaa`"""
        return BrokenResolution.round_resolution(self.width*self.ssaa, self.height*self.ssaa)

    # # Aspect Ratio

    _aspect_ratio: float = None

    @property
    def aspect_ratio(self) -> float:
        """Either the forced `self._aspect_ratio` or dynamic from `self.width/self.height`. When set
        and resizing, the logic of `BrokenResolution.fit` is applied to enforce ratios"""
        return self._aspect_ratio or (self.width/self.height)

    @aspect_ratio.setter
    def aspect_ratio(self, value: Union[float, str]) -> None:
        log.debug(f"{self.who} Changing Aspect Ratio to {value}")

        # Replace ":" with "/", eval or default to None if falsy
        if isinstance(value, str):
            value = eval(value.replace(":", "/").capitalize())

        # Convert zeros to None
        value = value or None

        # Optimization: Only change if different
        if (self._aspect_ratio == value):
            return

        self._aspect_ratio = value

        if (self.backend == ShaderBackend.GLFW):
            num, den = limited_integer_ratio(self._aspect_ratio, limit=2**20) or (-1, -1)
            glfw.set_window_aspect_ratio(self.window._window, num, den)

    def resize(self,
        width: int=Unchanged,
        height: int=Unchanged,
        *,
        scale: float=1,
        aspect_ratio: float=Union[Unchanged, float, str],
    ) -> Tuple[int, int]:
        """
        Resize the true final rendering resolution of the Scene
        - Rounded to nearest multiple of 2, so FFmpeg is happy
        - Limited by the Monitor resolution if Realtime
        - Safe to use floats as input arguments
        - Use None to not change this resolution component
        - Doesn't signal a resize if same resolution as before

        Args:
            width:  New width of the Scene, None to not change
            height: New height of the Scene, None to not change

        Returns:
            Self: Fluent interface
        """
        self.aspect_ratio = aspect_ratio
        self._scale = scale

        # Find the best
        resolution = BrokenResolution.fit(
            old_width=self.width, old_height=self.height, new_width=width, new_height=height,
            maximum_width=self.monitor_width, maximum_height=self.monitor_height,
            scale=1, aspect_ratio=self._aspect_ratio,
        )

        # Optimization: Only resize when resolution changes
        if resolution != (self.width, self.height):
            log.info(f"{self.who} Resizing window to resolution {resolution}")
            self.window.fbo.viewport = (0, 0, self.width, self.height)
            self._width, self._height = resolution
            self.window.size = resolution
            self.relay(Message.Shader.RecreateTextures)
        return self.resolution

    # ---------------------------------------------------------------------------------------------|
    # Window, OpenGL, Backend

    backend: ShaderBackend = ShaderBackend.get(os.environ.get("SHADERFLOW_BACKEND", ShaderBackend.GLFW))
    """The ModernGL Window Backend. **Cannot be changed after creation**. Can also be set with the
    environment variable `SHADERFLOW_BACKEND=<backend>`, where `backend = {glfw, headless}`"""

    opengl: moderngl.Context = None
    """ModernGL Context of this Scene. The thread accessing this MUST own or ENTER its context for
    creating, changing, deleting objects; more often than not, it's the Main thread"""

    window: ModernglWindow = None
    """ModernGL Window instance at `site-packages/moderngl_window.context.<self.backend>.Window`"""

    imgui: ModernglImgui = None
    """ModernGL Imgui integration class bound to the Window"""

    imguio: Any = None
    """Imgui IO object"""

    # Todo: Proper UI classes? For main menu, settings, exporting, etc
    render_ui: bool = False
    """Whether to render the Main UI"""

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""
        log.info(f"{self.who} Creating Window and OpenGL Context")
        log.info(f"{self.who} • Backend:    {denum(self.backend)}")
        log.info(f"{self.who} • Resolution: {self.resolution}")

        # Provide GPU Acceleration on headless rendering, as xvfb-run is software rendering
        # https://forums.developer.nvidia.com/t/81412 - Comments 2 and 6
        backend = "egl" * (self.backend == ShaderBackend.Headless) * (BrokenPlatform.OnLinux) or None

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

        if (self.backend == ShaderBackend.GLFW):
            BrokenThread.new(target=self.window.set_icon, icon_path=Broken.PROJECT.RESOURCES.ICON, daemon=True)
            glfw.set_cursor_enter_callback(self.window._window, lambda _, enter: self.__window_mouse_enter_event__(inside=enter))
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)
            ShaderKeyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
            ShaderKeyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
            ShaderKeyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT
            # glfw.maximize_window(self.window._window)

        log.debug(f"{self.who} Finished Window creation")

    def read_screen(self) -> bytes:
        """Take a screenshot of the screen and return raw bytes. Length `width*height*components`"""
        return self.window.fbo.read(viewport=(0, 0, self.width, self.height))

    # ---------------------------------------------------------------------------------------------|
    # User actions

    @abstractmethod
    def commands(self) -> None:
        """Configure commands for the Scene. Add with self.broken_typer.command(...)"""
        ...

    _built: SameTracker = Factory(SameTracker)

    def cli(self, *args: List[str]):
        args = flatten(args)
        self.broken_typer = BrokenTyper(chain=True)
        self.broken_typer.command(self.main, context=True, default=True)
        self.commands()
        if ("--help" not in args) and (not self._built(True)):
            self.build()
        self.broken_typer(args)

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        return BrokenPath(SHADERFLOW.DIRECTORIES.CURRENT_SCENE)

    def read_file(self, file: Path, bytes: bool=False) -> Union[str, bytes]:
        """
        Read a file relative to the current Scene Python script

        Args:
            `file`:  File to read, relative to the current Scene script directory
            `bytes`: Whether to read the file as bytes, defaults to text

        Returns:
            File contents as text or bytes
        """
        file = (self.directory/file)
        log.info(f"{self.who} Reading file ({file})")
        return LoaderBytes(file) if bytes else LoaderString(file)

    # ---------------------------------------------------------------------------------------------|
    # Main event loop

    _quit: bool = False
    """Should the the main event loop end on Realtime mode?"""

    def quit(self) -> None:
        if self.realtime:
            self._quit = True

    def next(self, dt: float) -> Self:

        # Fixme: Windows: https://github.com/glfw/glfw/pull/1426
        # Immediately swap the buffer with previous frame for vsync
        if self.realtime:
            self.window.swap_buffers()

        # Temporal logic
        dt = min(dt, 1)
        self.tempo.next(dt=abs(dt))
        self.rdt       = dt
        self.dt        = dt * self.tempo
        self.time     += self.dt
        self.vsync.fps = self.fps

        # Note: Updates in reverse order of addition (child -> parent)
        # Note: Non-engine first as pipeline might change
        for module in self.modules:
            if not isinstance(module, ShaderObject):
                module.update()
        for module in self.modules:
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

    # Batch exporting

    batch: Iterable[int] = field(factory=lambda: [0], converter=lambda x: list(x) or [0])
    """Batch indices iterable to export"""

    index: int = 0
    """Current Batch exporting video index"""

    @abstractmethod
    def export_name(self, path: Path) -> Path:
        """Change the video file name being exported based on the current batch index. By default,
        the name is unchanged in single export, else the stem is appended with the batch index"""
        if (len(self.batch) > 1):
            return path.with_stem(f"{path.stem}_{self.index}")
        return path

    export_format: str = field(default="mp4", converter=lambda x: str(denum(x)))
    """The last (or only) video export format (extension) to use"""

    export_base: BrokenPath = field(default=Broken.PROJECT.DIRECTORIES.DATA, converter=lambda x: Path(x))
    """The last (or only) video export base directory. Videos should render to ($base/$name) if $name
    is plain, that is, the path isn't absolute"""

    def main(self,
        width:      Annotated[int,   Option("--width",      "-w", help="(🔴 Basic    ) Width  of the Rendering Resolution. None to keep or find by Aspect Ratio (1920 on init)")]=None,
        height:     Annotated[int,   Option("--height",     "-h", help="(🔴 Basic    ) Height of the Rendering Resolution. None to keep or find by Aspect Ratio (1080 on init)")]=None,
        scale:      Annotated[float, Option("--scale",      "-x", help="(🔴 Basic    ) Post-multiply Width and Height by a Scale Factor")]=1.0,
        aspect:     Annotated[str,   Option("--ar",         "-a", help="(🔴 Basic    ) Force resolution aspect ratio, None for dynamic. Examples: '16:9', '16/9', '1.777'")]=None,
        fps:        Annotated[float, Option("--fps",        "-f", help="(🔴 Basic    ) Target Frames per Second. On Realtime, defaults to the monitor framerate else 60")]=None,
        fullscreen: Annotated[bool,  Option("--fullscreen",       help="(🔴 Basic    ) Start the Real Time Window in Fullscreen Mode")]=False,
        quality:    Annotated[float, Option("--quality",    "-q", help="(🟡 Quality  ) Shader Quality level, if supported (0-100%)")]=80,
        ssaa:       Annotated[float, Option("--ssaa",       "-s", help="(🟡 Quality  ) Fractional Super Sampling Anti Aliasing factor, O(N^2) GPU cost")]=1.0,
        render:     Annotated[bool,  Option("--render",     "-r", help="(🟢 Exporting) Export the Scene to a Video File (defined on --output, and implicit if so)")]=False,
        output:     Annotated[str,   Option("--output",     "-o", help="(🟢 Exporting) Output File Name: Absolute, Relative Path or Plain Name. Saved on ($base/$(plain_name or $scene-$date))")]=None,
        end:        Annotated[float, Option("--end",        "-t", help="(🟢 Exporting) How many seconds to render, defaults to 10 or longest advertised module")]=None,
        format:     Annotated[str,   Option("--format",           help="(🟢 Exporting) Output Video Container (mp4, mkv, webm, avi..), overrides --output one")]="mp4",
        base:       Annotated[Path,  Option("--base",             help="(🟢 Exporting) Output File Base Directory")]=Broken.PROJECT.DIRECTORIES.DATA,
        batch:      Annotated[str,   Option("--batch",      "-b", help="(🔵 Special  ) [WIP] Hyphenated indices range to export multiple videos, if implemented. (1,5-7,10)")]="0",
        benchmark:  Annotated[bool,  Option("--benchmark",        help="(🔵 Special  ) Benchmark the Scene's speed on raw rendering. Use SKIP_GPU=1 for CPU only benchmark")]=False,
        raw:        Annotated[bool,  Option("--raw",              help="(🔵 Special  ) Send raw OpenGL Frames before GPU SSAA to FFmpeg (CPU Downsampling) (Enabled if SSAA < 1)")]=False,
        open:       Annotated[bool,  Option("--open",             help="(🔵 Special  ) Open the Video's Output Directory after render finishes")]=False,
    ) -> Optional[Union[Path, List[Path]]]:
        """Main Event Loop of the Scene. Options to start a realtime window, exports to a file, or stress test speeds"""
        outputs: List[Path] = []

        from arrow import now as arrow_now
        export_started = arrow_now().format("YYYY-MM-DD HH-mm-ss")

        # Maybe update indices of exporting videos
        self.batch = hyphen_range(batch) or self.batch
        self.export_format = format
        self.export_base   = base

        for index in self.batch:
            self.index      = index
            self.exporting  = (render or bool(output))
            self.rendering  = (self.exporting or benchmark)
            self.realtime   = (not self.rendering)
            self.benchmark  = benchmark
            self.headless   = (self.rendering)
            self.fps        = (fps or self.monitor_framerate)
            self.title      = f"ShaderFlow | {self.__name__}"
            self.fullscreen = fullscreen
            self.quality    = quality
            self.ssaa       = ssaa
            self.time       = 0

            # Maybe keep or force aspect ratio, and find best resolution
            video_resolution = self.resize(width=width, height=height, scale=scale, aspect_ratio=aspect)

            # Optimization: Save bandwidth by piping native frames on ssaa < 1
            if self.rendering and (raw or ssaa < 1):
                self.resolution = self.render_resolution
                self.ssaa = 1

            for module in self.modules:
                module.setup()

            self.relay(Message.Shader.Compile)
            self.set_duration(end)

            # Configure FFmpeg and Popen it
            if (self.rendering):

                # Get video output path - if not absolute, save to data directory
                export_name = Path(output or f"({export_started}) {self.__name__}")
                export_name = export_name if export_name.is_absolute() else (self.export_base/export_name)
                export_name = export_name.with_suffix(export_name.suffix or f".{self.export_format}")
                export_name = self.export_name(export_name)

                self.ffmpeg = (
                    BrokenFFmpeg()
                    .quiet()
                    .format(FFmpegFormat.Rawvideo)
                    .pixel_format(FFmpegPixelFormat.RGBA if self.alpha else FFmpegPixelFormat.RGB24)
                    .resolution(self.resolution)
                    .framerate(self.fps)
                    .filter(FFmpegFilterFactory.scale(video_resolution))
                    .filter(FFmpegFilterFactory.flip_vertical())
                    .overwrite()
                    .input("-")
                )

                # Fixme: Is this the correct point for modules to manage FFmpeg?
                for module in self.modules:
                    module.ffmpeg(self.ffmpeg)

                # Add empty audio track if no input audio
                # self.ffmpeg = (
                #     self.ffmpeg
                #     .custom("-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100".split())
                #     .shortest()
                # )

                # Todo: Apply preset based config
                self.ffmpeg = (
                    self.ffmpeg
                    .video_codec(FFmpegVideoCodec.H264)
                    .audio_codec(FFmpegAudioCodec.AAC)
                    .audio_bitrate("300k")
                    .preset(FFmpegH264Preset.Slow)
                    .tune(FFmpegH264Tune.Film)
                    .quality(FFmpegH264Quality.High)
                    .pixel_format(FFmpegPixelFormat.YUV420P)
                    .custom("-t", self.runtime)
                    .custom("-movflags", "+faststart")
                )

                self.ffmpeg.output(export_name)

                # Fixme: Why Popen on Linux is slower on main thread (blocking?)
                # Idea: Python 3.13 Sub-interpreters could help, but require >= 3.13
                if self.exporting:
                    if BrokenPlatform.OnWindows:
                        self.ffmpeg = self.ffmpeg.Popen(stdin=PIPE)
                    else:
                        self.ffmpeg = self.ffmpeg.pipe()

                # Optimization: Don't allocate new buffers on each read for piping
                buffer = self.opengl.buffer(reserve=self._final.texture.length)

                # Status tracker
                status = DotMap(
                    start=time.perf_counter(),
                    bar=tqdm.tqdm(
                        total=self.total_frames,
                        desc=f"Scene #{self.index} ({type(self).__name__}) → Video",
                        dynamic_ncols=True,
                        colour="#43BFEF",
                        leave=False,
                        unit=" frames",
                        mininterval=1/60,
                        maxinterval=0.1,
                        smoothing=0.1,
                    )
                )

            # Add self.next to the event loop
            self.vsync = self.scheduler.new(
                task=self.next,
                frequency=self.fps,
                decoupled=self.rendering,
                precise=True,
            )

            # Some scenes might take a while to setup
            self.visible = not self.headless

            # Main rendering loop
            while (self.rendering) or (not self._quit):
                task = self.scheduler.next()

                # Only continue if exporting
                if (task.output is not self):
                    continue
                if self.realtime:
                    continue

                # Update status bar
                status.bar.update(1)
                status.bar.disable = False

                # Write a new frame to FFmpeg
                if self.exporting:
                    self._final.texture.fbo().read_into(buffer)
                    self.ffmpeg.stdin.write(buffer.read())

                # Finish exporting condition
                if (status.bar.n < self.total_frames):
                    continue

                if self.exporting:
                    self.ffmpeg.stdin.close()
                    outputs.append(export_name)

                # Log stats
                status.bar.refresh()
                status.bar.close()
                status.took = (time.perf_counter() - status.start)
                log.info(f"Finished rendering ({export_name})", echo=not self.benchmark)
                log.info((
                    f"• Stats: "
                    f"(Took {status.took:.2f} s) at "
                    f"({self.frame/status.took:.2f} FPS | "
                    f"{self.runtime/status.took:.2f} x Realtime) with "
                    f"({status.bar.n} Total Frames)"
                ))

                if self.benchmark:
                    return None
                break

        BrokenPath.open_in_file_explorer(outputs[0].parent) if open else None
        return (outputs[0] if len(outputs) == 1 else outputs) or None

    # ---------------------------------------------------------------------------------------------|
    # Module

    def handle(self, message: Message) -> None:

        if isinstance(message, Message.Window.Close):
            log.info(f"{self.who} Received Window Close Event")
            self.quit()

        elif isinstance(message, Message.Keyboard.KeyDown):
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
                BrokenThread.new(target=image.save, fp=path)
                log.minor(f"{self.who} (F2 ) Saved Screenshot to ({path})")

            elif message.key == ShaderKeyboard.Keys.F11:
                log.info(f"{self.who} (F11) Toggling Fullscreen")
                self.fullscreen = not self.fullscreen

        elif isinstance(message, (Message.Mouse.Drag, Message.Mouse.Position)):
            self.mouse_gluv = (message.u, message.v)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "float", "iTime",        self.time)
        yield ShaderVariable("uniform", "float", "iDuration",    self.duration)
        yield ShaderVariable("uniform", "float", "iDeltaTime",   self.dt)
        yield ShaderVariable("uniform", "vec2",  "iResolution",  self.resolution)
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
        self.relay(Message.Shader.RecreateTextures)
        self.relay(Message.Shader.Render)

    def __window_close__(self) -> None:
        self.relay(Message.Window.Close())

    def __window_iconify__(self, state: bool) -> None:
        self.relay(Message.Window.Iconify(state=state))

    def __window_files_dropped_event__(self, *stuff: list[str]) -> None:
        self.relay(Message.Window.FileDrop(files=stuff[1]))

    # # Keyboard related events

    def __window_key_event__(self, key: int, action: int, modifiers: int) -> None:
        self.imgui.key_event(key, action, modifiers)
        if self.imguio.want_capture_keyboard and self.render_ui:
            return
        if action == ShaderKeyboard.Keys.ACTION_PRESS:
            self.relay(Message.Keyboard.KeyDown(key=key, modifiers=modifiers))
        elif action == ShaderKeyboard.Keys.ACTION_RELEASE:
            self.relay(Message.Keyboard.KeyUp(key=key, modifiers=modifiers))
        self.relay(Message.Keyboard.Press(key=key, action=action, modifiers=modifiers))

    def __window_unicode_char_entered__(self, char: str) -> None:
        if self.imguio.want_capture_keyboard and self.render_ui:
            return
        self.relay(Message.Keyboard.Unicode(char=char))

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
        self.relay(Message.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event__(self, x: int, y: int, button: int) -> None:
        self.imgui.mouse_release_event(x, y, button)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.mouse_buttons[button] = False
        self.relay(Message.Mouse.Release(
            **self.__xy2uv__(x, y),
            button=button
        ))

    mouse_inside: bool = False

    def __window_mouse_enter_event__(self, inside: bool) -> None:
        self.mouse_inside = inside
        self.relay(Message.Mouse.Enter(state=inside))

    def __window_mouse_scroll_event__(self, dx: int, dy: int) -> None:
        self.imgui.mouse_scroll_event(dx, dy)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        elif self.keyboard(ShaderKeyboard.Keys.LEFT_ALT):
            self.tempo.target += (dy)*0.2
            return
        self.relay(Message.Mouse.Scroll(
            **self.__dxdy2dudv__(dx=dx, dy=dy)
        ))

    def __window_mouse_position_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.imgui.mouse_position_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.relay(Message.Mouse.Position(
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

        self.relay(Message.Mouse.Drag(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    # ---------------------------------------------------------------------------------------------|
    # Todo: Move UI to own class

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
            if imgui.tree_node(f"{module.uuid:>2} - {type(module).__name__.replace('ShaderFlow', '')}", imgui.TREE_NODE_BULLET):
                imgui.separator()
                module.__shaderflow_ui__()
                imgui.separator()
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
        if (state := imgui.slider_float("Time Scale", self.tempo.target, -2, 2, "%.2f"))[0]:
            self.tempo.target = state[1]
        for scale in (options := [-10, -5, -2, -1, 0, 1, 2, 5, 10]):
            if (state := imgui.button(f"{scale}x")):
                self.tempo.target = scale
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
