from . import *


class SombreroBackend(BrokenEnum):
    """ModernGL Window backends"""
    Headless = "headless"
    GLFW     = "glfw"
    # Pyglet   = "pyglet"
    # PyQT5    = "pyqt5"
    # PySide2  = "pyside2"
    # SDL2     = "sdl2"


class SombreroQuality(BrokenEnum):
    """
    Quality levels for Sombrero Shaders
    • Not all shaders or objects might react to this setting
    """
    Low    = 0
    Medium = 1
    High   = 2
    Ultra  = 3
    Final  = 4


@define
class SombreroScene(SombreroModule):

    # Basic - Required
    __name__     = "Untitled"
    __author__   = ["Broken Source"]
    __license__  = "AGPL-3.0-only"

    # Contact information - Optional
    __credits__  = ["ShaderFlow"]
    __email__    = None
    __website__  = None
    __github__   = None
    __twitter__  = None
    __telegram__ = None
    __discord__  = None
    __youtube__  = None

    """
    Implementing Fractional SSAA is a bit tricky:
    • A Window's FBO always match its real resolution (can't final render in other resolution)
    • We need a final shader to sample from some other SSAA-ed texture to the window

    For that, a internal self.__engine__ is used to sample from the user's main self.engine
    • __engine__: Uses the FBO of the Window, simply samples from a `final` texture to the screen
    • engine:     Scene's main engine, where the user's final shader is rendered to
    """
    __engine__: SombreroEngine = None
    engine:     SombreroEngine = None

    def __attrs_post_init__(self):
        self.register(self)

    def __build__(self):

        # Initialize default modules
        self.add(SombreroFrametimer)
        self.add(SombreroCamera)
        self.add(SombreroKeyboard)

        # Create the SSAA Workaround engines
        self.__engine__ = self.add(SombreroEngine)(final=True)
        self.  engine   = self.__engine__.child(SombreroEngine)
        self.__engine__.new_texture("final").from_module(self.engine)
        self.__engine__.shader.fragment = ("""
            void main() {
                fragColor = texture(final, astuv);
                fragColor.a = 1.0;
            }
        """)

        # Create OpenGL and Imgui context
        imgui.create_context()
        self.init_window()

    # ---------------------------------------------------------------------------------------------|
    # Registry

    modules: Dict[SombreroID, SombreroModule] = Factory(dict)

    def register(self, module: SombreroModule) -> SombreroModule:
        """
        Register a module in the Scene's modules registry

        Args:
            module: Module to register

        Returns:
            The module registered itself
        """
        log.trace(f"{module.who} New module registered")
        self.modules[module.uuid] = module
        module.__connected__.add(module.uuid)
        module.__group__.add(module.uuid)
        module.scene = self
        module._build()
        return module

    # ---------------------------------------------------------------------------------------------|
    # Basic information

    time:       Seconds = 0.0
    time_end:   Seconds = 10.0
    time_scale: float   = 1.0
    frame:      int     = 0
    fps:        Hertz   = 60.0
    dt:         Seconds = 0.0
    rdt:        Seconds = 0.0

    # Base classes and utils for a Scene
    eloop:         BrokenEventLoop   = Factory(BrokenEventLoop)
    vsync:         BrokenEventClient = None
    typer_app:     TyperApp          = None
    broken_ffmpeg: BrokenFFmpeg      = None

    @property
    def frameperiod(self) -> Seconds:
        return 1/self.fps

    @frameperiod.setter
    def frameperiod(self, value: Seconds):
        self.fps = 1/value

    # # Title

    __title__:  str = "Sombrero | ShaderFlow"

    @property
    def title(self) -> str:
        return self.__title__

    @title.setter
    def title(self, value: str) -> None:
        self.__title__ = value
        self.window.title = value

    # # Resizable

    __resizable__:  bool  = True

    @property
    def resizable(self) -> bool:
        return self.__resizable__

    @resizable.setter
    def resizable(self, value: bool) -> None:
        self.__resizable__    = value
        self.window.resizable = value

    quality: SombreroQuality = SombreroQuality.High.field()

    # # Resolution

    __width__:  int   = 1920
    __height__: int   = 1080
    __ssaa__:   float = 1.0

    def resize(self, width: int=Unchanged, height: int=Unchanged) -> None:

        # Get the new values of the resolution
        self.__width__  = BrokenUtils.round(width  or self.__width__,  2, type=int)
        self.__height__ = BrokenUtils.round(height or self.__height__, 2, type=int)

        log.debug(f"{self.who} Resizing window to size ({self.width}x{self.height})")

        # Resize the window and message modules
        self.window.size = (self.width, self.height)
        self.relay(SombreroMessage.Window.Resize(width=self.width, height=self.height))

    # Width

    @property
    def width(self) -> int:
        return self.__width__

    @width.setter
    def width(self, value: int) -> None:
        self.resize(width=value)

    # Height

    @property
    def height(self) -> int:
        return self.__height__

    @height.setter
    def height(self, value: int) -> None:
        self.resize(height=value)

    # Pairs

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.width, self.height

    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        self.resize(*value)

    @property
    def render_resolution(self) -> Tuple[int, int]:
        """The window resolution multiplied by the SSAA factor"""
        return (
            BrokenUtils.round(self.width *self.ssaa, 2, type=int),
            BrokenUtils.round(self.height*self.ssaa, 2, type=int)
        )

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    # # SSAA

    @property
    def ssaa(self) -> float:
        return self.__ssaa__

    @ssaa.setter
    def ssaa(self, value: float) -> None:
        log.debug(f"{self.who} Changing SSAA to {value}")
        self.__ssaa__ = value
        self.relay(SombreroMessage.Engine.RecreateTextures)

    # # Window backend

    __backend__: SombreroBackend = SombreroBackend.Headless.field()

    @property
    def backend(self) -> str:
        return self.__backend__.value

    @backend.setter
    def backend(self, option: str | SombreroBackend) -> None:
        """Change the ModernGL Window backend, recreates the window"""

        # Optimization: Don't recreate the window if the backend is the same
        if (new := SombreroBackend.get(option)) == self.__backend__:
            log.debug(f"{self.who} Backend already is {self.__backend__}")
            return

        # Actually change the backend
        log.info(f"{self.who} Changing backend to {new}")
        self.__backend__ = new
        self.init_window()

        # Fixme: Recreating textures was needed, even though the OpenGL Context is healthy
        self.relay(SombreroMessage.Engine.RecreateTextures)

    # # Window Fullscreen

    __fullscreen__: bool = False

    @property
    def fullscreen(self) -> bool:
        return self.__fullscreen__

    @fullscreen.setter
    def fullscreen(self, value: bool) -> None:
        try:
            self.window.fullscreen = value
            self.__fullscreen__ = value
        except AttributeError:
            pass

    # # Window Vsync

    __window_vsync__: bool = False

    @property
    def window_vsync(self) -> bool:
        return self.__window_vsync__

    @window_vsync.setter
    def window_vsync(self, value: bool) -> None:
        self.__window_vsync__ = value
        self.window.vsync = value

    # # Window Exclusive

    __exclusive__: bool = False

    @property
    def exclusive(self) -> bool:
        return self.__exclusive__

    @exclusive.setter
    def exclusive(self, value: bool) -> None:
        self.__exclusive__ = value
        self.window.mouse_exclusivity = value

    # Window methods
    icon:        Option[Path, "str"] = SHADERFLOW.RESOURCES.ICON
    opengl:      moderngl.Context    = None
    window:      ModernglWindow      = None

    # Imgui
    render_ui: bool          = False
    imgui:     ModernglImgui = None
    imguio:    Any           = None

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""

        # Destroy the previous window but not the context
        # Workaround: Do not destroy the context on headless, _ctx=Dummy
        if self.window:
            log.debug(f"{self.who} Destroying previous Window")
            self.window._ctx = BrokenNOP()
            self.window.destroy()

        # Dynamically import the Window class based on the backend
        log.debug(f"{self.who} Dynamically importing ({self.backend}) Window class")
        Window = getattr(importlib.import_module(f"moderngl_window.context.{self.backend}"), "Window")

        # Create Window
        log.debug(f"{self.who} Creating Window")
        self.window = Window(
            size=self.resolution,
            title=self.title,
            aspect_ratio=None,
            resizable=self.resizable,
            fullscreen=self.fullscreen,
            vsync=False if self.rendering else self.window_vsync,
        )

        # Assign keys to the SombreroKeyboard
        SombreroKeyboard.Keys = self.window.keys
        SombreroKeyboard.Keys.SHIFT = "SHIFT"
        SombreroKeyboard.Keys.CTRL  = "CTRL"
        SombreroKeyboard.Keys.ALT   = "ALT"

        # First time:  Get the Window's OpenGL Context as our own self.opengl
        # Other times: Assign the previous self.opengl to the new Window, find FBOs
        if not self.opengl:
            log.debug(f"{self.who} Binding to Window's OpenGL Context")
            self.opengl = self.window.ctx

        else:
            log.debug(f"{self.who} Rebinding to Window's OpenGL Context")

            # Assign the current "Singleton" context to the Window
            self.window._ctx = self.opengl

            # Detect new screen and Framebuffer
            self.opengl._screen  = self.opengl.detect_framebuffer(0)
            self.opengl.fbo      = self.opengl.detect_framebuffer()
            self.opengl.mglo.fbo = self.opengl.fbo.mglo
            self.window.set_default_viewport()

        # Bind imgui
        self.imgui  = ModernglImgui(self.window)
        self.imguio = imgui.get_io()

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
        BrokenThread.new(target=self.window.set_icon, icon_path=self.icon)

        # Workaround: Implement file dropping for GLFW
        if self.__backend__ == SombreroBackend.GLFW:
            log.debug(f"{self.who} Implementing file dropping for GLFW")
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)

        log.debug(f"{self.who} Finished Window creation")

    # ---------------------------------------------------------------------------------------------|
    # SombreroModule

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Time",        value=self.time)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}TimeEnd",     value=self.time_end)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Tau",         value=self.time/self.time_end)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}DeltaTime",   value=self.dt)
        yield ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}Resolution",  value=self.resolution)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}AspectRatio", value=self.aspect_ratio)
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}Quality",     value=self.quality)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}SSAA",        value=self.ssaa)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}FPS",         value=self.fps)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Frame",       value=self.frame)
        yield ShaderVariable(qualifier="uniform", type="bool",  name=f"{self.prefix}Rendering",   value=self.rendering)
        yield ShaderVariable(qualifier="uniform", type="bool",  name=f"{self.prefix}Realtime",    value=self.realtime)

    def __handle__(self, message: SombreroMessage) -> None:
        if isinstance(message, SombreroMessage.Window.Close):
            self.quit()

        if isinstance(message, SombreroMessage.Keyboard.KeyDown):
            if message.key == SombreroKeyboard.Keys.TAB:
                self.render_ui  = not self.render_ui
            if message.key == SombreroKeyboard.Keys.F:
                self.fullscreen = not self.fullscreen
            if message.key == SombreroKeyboard.Keys.R:
                self.exclusive  = not self.exclusive

    def __next__(self, dt: float) -> Self:

        # Immediately display the next frame
        self.window.swap_buffers()

        # Temporal
        self.time     += dt * self.time_scale
        self.dt        = dt * self.time_scale
        self.rdt       = dt
        self.frame     = int(self.time * self.fps)
        self.vsync.fps = self.fps

        # The scene must be the first one to update as it controls others
        self._update()

        # Update modules in reverse order of addition
        for module in reversed(self.modules.values()):
            if module is not self:
                module._update()

        # Draw the UI
        # Todo: Move to a Utils class for other stuff such as theming?
        if self.render_ui:
            self.__engine__.fbo.use()

            # Styling
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
            imgui.begin(f"Sombrero Scene - {self.__name__}", False, imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_ALWAYS_AUTO_RESIZE)

            # Render every module
            for module in self.modules.values():
                if imgui.tree_node(f"{module.uuid:>2} - {type(module).__name__}", imgui.TREE_NODE_BULLET):
                    imgui.separator()
                    module.__sombrero_ui__()
                    imgui.separator()
                    imgui.spacing()
                    imgui.tree_pop()

            imgui.end()
            imgui.pop_style_color()
            imgui.pop_style_var(6)
            imgui.render()

            # Blend render with window texture
            self.imgui.render(imgui.get_draw_data())


        return self

    def __ui__(self) -> None:

        # Framerate
        imgui.spacing()
        if (state := imgui.input_float("Framerate", self.fps, 1, 1, "%.2f"))[0]:
            self.fps = state[1]
        for fps in (options := [24, 30, 60, 120, 144, 240]):
            if (state := imgui.button(f"{fps} Hz")):
                self.fps = fps
            if fps != options[-1]:
                imgui.same_line()

        # Temporal
        imgui.spacing()
        if (state := imgui.input_float("Time Scale", self.time_scale, 0.1, 0.1, "%.2fx"))[0]:
            self.time_scale = state[1]
        for scale in (options := [-10, -5, -2, -1, 0, 1, 2, 5, 10]):
            if (state := imgui.button(f"{scale}x")):
                self.time_scale = scale
            if scale != options[-1]:
                imgui.same_line()

        # SSAA
        imgui.spacing()
        if (state := imgui.input_float("SSAA", self.ssaa, 0.1, 0.1, "%.2fx"))[0]:
            self.ssaa = state[1]
        for ssaa in (options := [0.1, 0.25, 0.5, 1.0, 1.25, 1.5, 2.0]):
            if (state := imgui.button(f"{ssaa}x")):
                self.ssaa = ssaa
            if ssaa != options[-1]:
                imgui.same_line()

        # Quality
        imgui.spacing()
        imgui.text(f"Quality: {self.quality}")
        for quality in (options := SombreroQuality.options):
            if (state := imgui.button(quality.name)):
                self.quality = quality
            if quality != options[-1]:
                imgui.same_line()

    # ---------------------------------------------------------------------------------------------|
    # User actions

    @abstractmethod
    def commands(self) -> None:
        """
        Let the user configure commands for the Scene
        """
        ...

    def cli(self, *args: List[str]):
        self.broken_typer = BrokenTyper(chain=True)
        self.broken_typer.command(self.main,     context=True, default=True)
        self.broken_typer.command(self.settings, context=True)
        self.commands()
        self.broken_typer(args)

    @abstractmethod
    def settings(self):
        """Optional scene settings to be configured on the CLI"""
        pass

    __quit__:  bool = False
    rendering: bool = False
    realtime:  bool = False

    def quit(self) -> None:
        if self.realtime:
            self.__quit__ = True

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        # Fixme: How to deal with ShaderFlow as a dependency scenario?
        return SHADERFLOW.DIRECTORIES.CURRENT_SCENE

    def read_file(self, file: Path, bytes: bool=False) -> str | bytes:
        """
        Read a file relative to the current Scene Python script

        Args:
            `file`:  File to read, relative to the current Scene script directory
            `bytes`: Whether to read the file as bytes, defaults to text

        Returns:
            File contents as text or bytes
        """
        file = self.directory/file
        return file.read_bytes() if bytes else file.read_text()


    def main(self,
        width:      Annotated[int,   TyperOption("--width",      "-w", help="(Basic    ) Width  of the Rendering Resolution")]=1920,
        height:     Annotated[int,   TyperOption("--height",     "-h", help="(Basic    ) Height of the Rendering Resolution")]=1080,
        fps:        Annotated[float, TyperOption("--fps",        "-f", help="(Basic    ) Target Frames per Second (Exact when Exporting)")]=60,
        fullscreen: Annotated[bool,  TyperOption("--fullscreen",       help="(Basic    ) Start the Window in Fullscreen")]=False,
        benchmark:  Annotated[bool,  TyperOption("--benchmark",  "-b", help="(Basic    ) Benchmark the Scene's speed on raw rendering")]=False,
        ssaa:       Annotated[float, TyperOption("--ssaa",       "-s", help="(Quality  ) Fractional Super Sampling Anti Aliasing factor (⚠️ Quadratically Slower)")]=1,
        scale:      Annotated[float, TyperOption("--scale",      "-x", help="(Quality  ) Pre-multiply Width and Height by a Scale Factor")]=1.0,
        quality:    Annotated[str,   TyperOption("--quality",    "-q", help="(Quality  ) Shader Quality level (low, medium, high, ultra, final)")]="high",
        render:     Annotated[bool,  TyperOption("--render",     "-r", help="(Exporting) Export the Scene to a Video File")]=False,
        output:     Annotated[str,   TyperOption("--output",     "-o", help="(Exporting) Output File Name. Absolute. Relative Path or Plain Name. Saved on (DATA/$(plain_name or $scene-$date))")]=None,
        format:     Annotated[str,   TyperOption("--format",           help="(Exporting) Output Video Container (mp4, mkv, webm, avi..)")]="mp4",
        time:       Annotated[float, TyperOption("--time-end",   "-t", help="(Exporting) How many seconds to render, defaults to 10 or longest SombreroAudio")]=None,
        raw:        Annotated[bool,  TyperOption("--raw",              help="(Exporting) Send raw buffers before GPU SSAA frames to FFmpeg (Enabled if SSAA < 1)")]=False,
        # headless:   Annotated[bool,  TyperOption("--headless",   "-H", help="(Exporting) Use Headless rendering. It works, ")]=False,
        open:       Annotated[bool,  TyperOption("--open",             help="(Exporting) Open the Video's Output Directory after rendering")]=False,
    ) -> Optional[Path]:

        # Implicit render mode if output is provided
        render = render or benchmark or bool(output)

        # Set useful state flags
        self.realtime  = not render
        self.rendering = render
        self.benchmark = benchmark

        # Window configuration based on launch mode
        self.resolution = (width*scale, height*scale)
        self.resizable  = self.realtime
        self.ssaa       = ssaa
        self.quality    = quality
        self.fps        = fps
        self.time       = 0
        self.time_end   = 0
        self.fullscreen = fullscreen
        self.backend    = SombreroBackend.Headless if self.rendering else SombreroBackend.GLFW
        self.title      = f"ShaderFlow | {self.__name__} Scene"

        # When rendering, let FFmpeg apply the SSAA, I trust it more (higher quality?)
        if self.rendering and (raw or self.ssaa < 1):
            self.resolution = self.render_resolution
            self.ssaa = 1

        # Create the Vsync event loop
        self.vsync = self.eloop.new(
            callback=self.__next__,
            frequency=self.fps,
            decoupled=self.rendering,
            precise=True,
        )

        # Setup
        for module in self.modules.values():
            module._setup()

        # Find the longest audio duration or set time_end
        for module in (not bool(time)) * self.rendering * list(self.find(SombreroAudio)):
            self.time_end = max(self.time_end, module.duration or 0)
        else:
            self.time_end = self.time_end or time or 10

        if self.rendering:
            import arrow

            # Get video output path - if not absolute, save to data directory
            output = Path(output or f"({arrow.utcnow().format('YYYY-MM-DD_HH-mm-ss')}) {self.__name__}")
            output = output if output.is_absolute() else SHADERFLOW.DIRECTORIES.DATA/output
            output = output.with_suffix(output.suffix or f".{format}")

            # Create FFmpeg process
            self.broken_ffmpeg = (
                BrokenFFmpeg()
                .quiet()
                .overwrite()
                .format(FFmpegFormat.Rawvideo)
                .pixel_format(FFmpegPixelFormat.RGB24)
                .resolution(self.resolution)
                .framerate(self.fps)
                .filter(FFmpegFilterFactory.scale(self.resolution))
                .filter(FFmpegFilterFactory.flip_vertical())
                .input("-")
            )

            # Fixme: Is this the correct point for modules to manage FFmpeg?
            for module in self.modules.values():
                module._ffmpeg(self.broken_ffmpeg)

            # Add empty audio track if no input audio
            # self.broken_ffmpeg = (
            #     self.broken_ffmpeg
            #     .custom("-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100".split())
            #     .shortest()
            # )

            # Todo: Apply preset based config
            self.broken_ffmpeg = (
                self.broken_ffmpeg
                .video_codec(FFmpegVideoCodec.H264)
                .audio_codec(FFmpegAudioCodec.AAC)
                .audio_bitrate("300k")
                .preset(FFmpegH264Preset.Slow)
                .tune(FFmpegH264Tune.Film)
                .quality(FFmpegH264Quality.High)
                .pixel_format(FFmpegPixelFormat.YUV420P)
                .custom("-t", self.time_end)
            )

            # Add output video
            self.broken_ffmpeg.output(output)
            if not benchmark:
                self.broken_ffmpeg = self.broken_ffmpeg.pipe()

            # Add progress bar
            progress_bar = tqdm.tqdm(
                total=int(self.time_end*self.fps),
                desc=f"SombreroScene ({type(self).__name__}) → Video",
                dynamic_ncols=True,
                colour="#43BFEF",
                leave=False,
                unit=" Frames",
                mininterval=1/60,
                maxinterval=0.1,
                smoothing=0.1,
            )

        import time

        # Benchmark and stats data
        RenderStatus = DotMap(
            render_start=time.perf_counter(),
            total_frames=0,
        )

        # Main rendering loop
        while (self.rendering) or (not self.__quit__):

            # Keep calling event loop until self was updated
            if (call := self.eloop.next().output) is not self:
                continue

            if not self.rendering:
                continue

            # Rendering logic
            progress_bar.update(1)
            RenderStatus.total_frames += 1

            # Write new frame to FFmpeg
            if not self.benchmark:
                self.broken_ffmpeg.write(self.window.fbo.read(components=3))

            # Render until time and end are Close
            if (self.time_end - self.time) > 1.5*self.frameperiod:
                continue

            if not self.benchmark:
                self.broken_ffmpeg.close()

            # Log stats
            progress_bar.refresh()
            progress_bar.close()
            RenderStatus.took = time.perf_counter() - RenderStatus.render_start
            log.info(f"Finished rendering ({output})")
            log.info((
                f"• Stats: "
                f"(Took {RenderStatus.took:.2f}s) at "
                f"({self.frame/RenderStatus.took:.2f} FPS | "
                f"{self.time_end/RenderStatus.took:.2f}x Realtime) with "
                f"({RenderStatus.total_frames} Total Frames)"
            ))

            if self.benchmark:
                return

            # Open output directory
            if open: BrokenPath.open_in_file_explorer(output.parent)
            break

        # Cleanup
        self.window.destroy()
        return output

    # # Window related events

    def __window_resize__(self, width: int, height: int) -> None:
        self.imgui.resize(width, height)
        self.__width__, self.__height__ = width, height
        self.relay(SombreroMessage.Window.Resize(width=width, height=height))

    def __window_close__(self) -> None:
        self.relay(SombreroMessage.Window.Close())

    def __window_iconify__(self, state: bool) -> None:
        self.relay(SombreroMessage.Window.Iconify(state=state))

    def __window_files_dropped_event__(self, *stuff: list[str]) -> None:
        if self.__backend__ == SombreroBackend.GLFW:
            self.relay(SombreroMessage.Window.FileDrop(files=stuff[1]))

    # # Keyboard related events

    def __window_key_event__(self, key: int, action: int, modifiers: int) -> None:
        # Prioritize imgui events
        self.imgui.key_event(key, action, modifiers)
        if self.imguio.want_capture_keyboard: return

        # Calculate and relay the key event
        self.relay(SombreroMessage.Keyboard.Press(key=key, action=action, modifiers=modifiers))

        # Key UP and Down
        if action == SombreroKeyboard.Keys.ACTION_PRESS:
            self.relay(SombreroMessage.Keyboard.KeyDown(key=key, modifiers=modifiers))
        elif action == SombreroKeyboard.Keys.ACTION_RELEASE:
            self.relay(SombreroMessage.Keyboard.KeyUp(key=key, modifiers=modifiers))

    def __window_unicode_char_entered__(self, char: str) -> None:
        if self.imguio.want_capture_keyboard: return
        self.relay(SombreroMessage.Keyboard.Unicode(char=char))

    # # Mouse related events

    # Conversion methods

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
            du=2*(dx/self.width ) * self.aspect_ratio,
            dv=2*(dy/self.height)*(-1),
            dx=dx, dy=dy,
        )

    # Actual events

    def __window_mouse_position_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_position_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the position event
        self.relay(SombreroMessage.Mouse.Position(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_press_event__(self, x: int, y: int, button: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_press_event(x, y, button)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the press event
        self.relay(SombreroMessage.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event__(self, x: int, y: int, button: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_release_event(x, y, button)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the release event
        self.relay(SombreroMessage.Mouse.Release(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_drag_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_drag_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the drag event
        self.relay(SombreroMessage.Mouse.Drag(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_scroll_event__(self, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_scroll_event(dx, dy)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the scroll event
        self.relay(SombreroMessage.Mouse.Scroll(
            **self.__dxdy2dudv__(dx=dx, dy=dy)
        ))

    # # Linear Algebra utilities

    def smoothstep(self, x: float) -> float:
        if x <= 0: return 0
        if x >= 1: return 1
        return 3*x**2 - 2*x**3
