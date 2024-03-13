import ShaderFlow

from . import *


class ShaderFlowBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

@define
class Scene(Module):
    __name__ = "Scene"

    # Registry
    modules: Deque[Module] = Factory(deque)

    """
    Implementing Fractional SSAA is a bit tricky:
    • A Window's FBO always match its real resolution (can't final render in other resolution)
    • We need a final shader to sample from some other SSAA-ed texture to the window

    For that, a internal self._final is used to sample from the user's main self.engine
    • _final: Uses the FBO of the Window, simply samples from a `final` texture to the screen
    • engine: Scene's main engine, where the user's final shader is rendered to
    """
    _final: Shader = None
    shader: Shader = None
    camera: Camera = None
    keyboard: Keyboard = None

    def build(self):

        # Init Imgui
        imgui.create_context()
        self.imguio = imgui.get_io()
        self.imguio.font_global_scale = SHADERFLOW.CONFIG.imgui.default("font_scale", 1.0)
        self.imguio.fonts.add_font_from_file_ttf(
            str(BROKEN.RESOURCES.FONTS/"DejaVuSans.ttf"),
            16*self.imguio.font_global_scale,
        )

        # Default modules
        self.init_window()
        log.info(f"{self.who} Adding default base Scene modules")
        ShaderFlowFrametimer(self)
        self.keyboard = Keyboard(scene=self)
        self.camera   = Camera(scene=self)

        # Create the SSAA Workaround engines
        log.info(f"{self.who} Creating SSAA Implementation")
        self.shader = Shader(self)
        self.shader.texture.name = "iScreen"
        self._final = Shader(self)
        self._final.texture.final = True
        self._final.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Final.glsl")

    # ---------------------------------------------------------------------------------------------|
    # Basic information

    time:       Seconds = 0.0
    time_end:   Seconds = 10.0
    time_scale: float   = Factory(lambda: DynamicsBase(value=1, frequency=5))
    frame:      int     = 0
    fps:        Hertz   = 60.0
    dt:         Seconds = 0.0
    rdt:        Seconds = 0.0

    # Base classes and utils for a Scene
    eloop:  BrokenEventLoop   = Factory(BrokenEventLoop)
    vsync:  BrokenEventClient = None
    ffmpeg: BrokenFFmpeg      = None

    @property
    def frametime(self) -> Seconds:
        return 1/self.fps

    # # Title

    _title: str = "ShaderFlow"

    @property
    def title(self) -> str:
        return self._title
    @title.setter
    def title(self, value: str) -> None:
        log.info(f"{self.who} Changing Window Title to ({value})")
        self.window.title = value
        self._title = value

    # # Resizable

    _resizable: bool = True

    @property
    def resizable(self) -> bool:
        return self._resizable
    @resizable.setter
    def resizable(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Resizable to ({value})")
        self.window.resizable = value
        self._resizable = value
        if (self._backend == ShaderFlowBackend.GLFW):
            glfw.set_window_attrib(self.window._window, glfw.RESIZABLE, value)

    # # Visible

    _visible: bool = False

    @property
    def visible(self) -> bool:
        return self._visible
    @visible.setter
    def visible(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Visibility to ({value})")
        self.window.visible = value
        self._visible = value

    # # Resolution

    quality: float = Field(default=75, converter=lambda x: clamp(x, 0, 100))
    _width:  int   = 1920
    _height: int   = 1080
    _ssaa:   float = 1.0

    def resize(self, width: int=Unchanged, height: int=Unchanged) -> None:
        self._width, self._height = BrokenUtils.round_resolution(width, height)
        log.info(f"{self.who} Resizing window to resolution {self.resolution}")
        self.opengl.screen.viewport = (0, 0, self.width, self.height)
        self.window.size = self.resolution

    def read_screen(self) -> bytes:
        return self.opengl.screen.read(viewport=(0, 0, self.width, self.height), components=3)

    # # Resolution related

    @property
    def width(self) -> int:
        return self._width
    @width.setter
    def width(self, value: int) -> None:
        self.resize(width=value)

    @property
    def height(self) -> int:
        return self._height
    @height.setter
    def height(self, value: int) -> None:
        self.resize(height=value)

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.width, self.height
    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        self.resize(*value)

    @property
    def ssaa(self) -> float:
        return self._ssaa
    @ssaa.setter
    def ssaa(self, value: float) -> None:
        log.info(f"{self.who} Changing Fractional SSAA to {value}")
        self._ssaa = value
        self.relay(Message.Shader.RecreateTextures)

    @property
    def render_resolution(self) -> Tuple[int, int]:
        return BrokenUtils.round_resolution(self.width*self.ssaa, self.height*self.ssaa)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    # # Window Fullscreen

    _fullscreen: bool = False

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen
    @fullscreen.setter
    def fullscreen(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Fullscreen to ({value})")
        self._fullscreen = value
        try:
            self.window.fullscreen = value
        except AttributeError:
            pass

    # # Window Vsync

    _window_vsync: bool = False

    @property
    def window_vsync(self) -> bool:
        return self._window_vsync
    @window_vsync.setter
    def window_vsync(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Native Vsync to ({value})")
        self._window_vsync = value
        self.window.vsync = value

    # # Window Exclusive

    _exclusive: bool = False

    @property
    def exclusive(self) -> bool:
        return self._exclusive

    @exclusive.setter
    def exclusive(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Exclusive to ({value})")
        self.window.mouse_exclusivity = value
        self._exclusive = value

    # # Focused

    @property
    def focused(self) -> bool:
        return glfw.get_window_attrib(self.window._window, glfw.FOCUSED)

    @focused.setter
    def focused(self, value: bool) -> None:
        log.info(f"{self.who} Changing Window Focused to ({value})")
        if value: glfw.focus_window(self.window._window)

    # # Backend

    _backend: ShaderFlowBackend = ShaderFlowBackend.GLFW

    @property
    def backend(self) -> ShaderFlowBackend:
        return self._backend

    # Window attributes
    icon:      PathLike         = Broken.PROJECT.RESOURCES.ICON
    opengl:    moderngl.Context = None
    window:    ModernglWindow   = None
    render_ui: bool             = False
    imgui:     ModernglImgui    = None
    imguio:    Any              = None

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""
        log.info(f"{self.who} Creating Window and OpenGL Context")
        log.info(f"{self.who} • Backend:    {self.backend}")
        log.info(f"{self.who} • Resolution: {self.resolution}")

        module = f"moderngl_window.context.{self.backend.value.lower()}"
        self.window = importlib.import_module(module).Window(
            size=self.resolution,
            title=self.title,
            resizable=self.resizable,
            visible=self.visible,
            fullscreen=self.fullscreen,
            vsync=False if self.rendering else self.window_vsync,
        )
        Keyboard.set_keymap(self.window.keys)
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
        self.window.mouse_enter_event_func    = self.__window_mouse_enter_event__
        self.window.unicode_char_entered_func = self.__window_unicode_char_entered__
        self.window.files_dropped_event_func  = self.__window_files_dropped_event__

        # Workaround: Implement file dropping for GLFW and Keys, parallel icon setting
        if (self._backend == ShaderFlowBackend.GLFW):
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)
            BrokenThread.new(target=self.window.set_icon, icon_path=self.icon)
            Keyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
            Keyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
            Keyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT
            glfw.maximize_window(self.window._window)

        log.debug(f"{self.who} Finished Window creation")

    # ---------------------------------------------------------------------------------------------|
    # Module

    def handle(self, message: Message) -> None:
        if isinstance(message, Message.Window.Close):
            log.info(f"{self.who} Received Window Close Event")
            self.quit()
        elif isinstance(message, Message.Keyboard.KeyDown):
            if message.key == Keyboard.Keys.TAB:
                log.info(f"{self.who} (TAB) Toggling Menu")
                self.render_ui  = not self.render_ui
            elif message.key == Keyboard.Keys.F1:
                log.info(f"{self.who} ( F1) Toggling Exclusive Mode")
                self.exclusive  = not self.exclusive
            elif message.key == Keyboard.Keys.F2:
                import arrow
                time  = arrow.now().format("YYYY-MM-DD_HH-mm-ss")
                image = PIL.Image.frombytes("RGB", self.resolution, self.read_screen())
                image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
                path  = Broken.PROJECT.DIRECTORIES.SCREENSHOTS/f"({time}) {self.__name__}.jpg"
                BrokenThread.new(target=image.save, fp=path, mode="JPEG", quality=95)
                log.minor(f"{self.who} ( F2) Saved Screenshot to ({path})")
            elif message.key == Keyboard.Keys.F11:
                log.info(f"{self.who} (F11) Toggling Fullscreen")
                self.fullscreen = not self.fullscreen
        elif isinstance(message, (Message.Mouse.Drag, Message.Mouse.Position)):
            self.mouse_gluv = (message.u, message.v)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "float", "iTime",        self.time)
        yield ShaderVariable("uniform", "float", "iTimeEnd",     self.time_end)
        yield ShaderVariable("uniform", "float", "iDeltaTime",   self.dt)
        yield ShaderVariable("uniform", "vec2",  "iResolution",  self.resolution)
        yield ShaderVariable("uniform", "float", "iQuality",     self.quality/100)
        yield ShaderVariable("uniform", "float", "iSSAA",        self.ssaa)
        yield ShaderVariable("uniform", "float", "iFramerate",   self.fps)
        yield ShaderVariable("uniform", "float", "iFrame",       self.frame)
        yield ShaderVariable("uniform", "bool",  "iRealtime",    self.realtime)
        yield ShaderVariable("uniform", "vec2",  "iMouse",       self.mouse_gluv)
        yield ShaderVariable("uniform", "bool",  "iMouseInside", self.mouse_inside)

    def next(self, dt: float) -> Self:

        # Limit maximum deltatime for framespikes or events catching up
        dt = min(dt, 1)

        # Temporal
        self.time_scale.next(dt=abs(dt))
        self.time     += dt * self.time_scale
        self.dt        = dt * self.time_scale
        self.rdt       = dt
        self.frame     = int(self.time * self.fps)
        self.vsync.fps = self.fps

        # Update modules in reverse order of addition
        # Note: Non-engine first as pipeline might change
        for module in (self.modules):
            if not isinstance(module, Shader):
                module.update()
        for module in (self.modules):
            if isinstance(module, Shader):
                module.update()

        # Todo: Move to a Utils class for other stuff such as theming?
        if self.render_ui:
            self._final.texture.fbo(0).use()
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

        # Fixme: https://github.com/glfw/glfw/pull/1426
        # Workaround: Swap early on the update, next one will catch up as frameskip=True
        if not self.headless:
            self.window.swap_buffers()

        return self

    def __ui__(self) -> None:

        # Render status
        imgui.text(f"Resolution: {self.render_resolution} -> {self.resolution} @ {self.ssaa}x SSAA")

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
        if (state := imgui.slider_float("Time Scale", self.time_scale.target, -2, 2, "%.2f"))[0]:
            self.time_scale.target = state[1]
        for scale in (options := [-10, -5, -2, -1, 0, 1, 2, 5, 10]):
            if (state := imgui.button(f"{scale}x")):
                self.time_scale.target = scale
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

    # ---------------------------------------------------------------------------------------------|
    # User actions

    @abstractmethod
    def commands(self) -> None:
        """
        Let the user configure commands for the Scene
        """
        ...

    # Workaround: Kill CFFI and Processes binaries on Windows.. PowerShell stupidly hangs..
    def _exit_hook(self):
        try:
            getattr(self.window, "destroy", Ignore())()
            if isinstance(self.ffmpeg, BrokenFFmpegPopenBuffered):
                self.ffmpeg.close()
        except Exception:
            pass

    def cli(self, *args: List[str]):
        self.broken_typer = BrokenTyper(chain=True, exit_hook=self._exit_hook)
        self.broken_typer.command(self.main,     context=True, default=True)
        self.broken_typer.command(self.settings, context=True)
        self.commands()
        self.broken_typer(args)

    @abstractmethod
    def settings(self):
        """Optional scene settings to be configured on the CLI"""
        pass

    _quit:     bool = False
    rendering: bool = False
    realtime:  bool = False
    headless:  bool = False

    def quit(self) -> None:
        if self.realtime:
            self._quit = True

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        # Fixme: How to deal with ShaderFlow as a dependency scenario?
        return BrokenPath(SHADERFLOW.DIRECTORIES.CURRENT_SCENE)

    def read_file(self, file: Path, bytes: bool=False) -> str | bytes:
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

    _built: bool = False

    def main(self,
        width:      Annotated[int,   TyperOption("--width",      "-w", help="(🌵 Basic    ) Width  of the Rendering Resolution")]=1920,
        height:     Annotated[int,   TyperOption("--height",     "-h", help="(🌵 Basic    ) Height of the Rendering Resolution")]=1080,
        fps:        Annotated[float, TyperOption("--fps",        "-f", help="(🌵 Basic    ) Target Frames per Second (Exact when Exporting)")]=60,
        fullscreen: Annotated[bool,  TyperOption("--fullscreen",       help="(🌵 Basic    ) Start the Real Time Window in Fullscreen Mode")]=False,
        benchmark:  Annotated[bool,  TyperOption("--benchmark",  "-b", help="(🌵 Basic    ) Benchmark the Scene's speed on raw rendering")]=False,
        scale:      Annotated[float, TyperOption("--scale",      "-x", help="(💎 Quality  ) Pre-multiply Width and Height by a Scale Factor")]=1.0,
        quality:    Annotated[float, TyperOption("--quality",    "-q", help="(💎 Quality  ) Shader Quality level if supported (0-100%)")]=80,
        ssaa:       Annotated[float, TyperOption("--ssaa",       "-s", help="(💎 Quality  ) Fractional Super Sampling Anti Aliasing factor, O(N²) GPU cost")]=1.0,
        render:     Annotated[bool,  TyperOption("--render",     "-r", help="(📦 Exporting) Export the current Scene to a Video File defined on --output")]=False,
        output:     Annotated[str,   TyperOption("--output",     "-o", help="(📦 Exporting) Output File Name: Absolute, Relative Path or Plain Name. Saved on ($DATA/$(plain_name or $scene-$date))")]=None,
        format:     Annotated[str,   TyperOption("--format",           help="(📦 Exporting) Output Video Container (mp4, mkv, webm, avi..), overrides --output one")]="mp4",
        time:       Annotated[float, TyperOption("--time-end",   "-t", help="(📦 Exporting) How many seconds to render, defaults to 10 or longest ShaderFlowAudio")]=None,
        raw:        Annotated[bool,  TyperOption("--raw",              help="(📦 Exporting) Send raw OpenGL Frames before GPU SSAA to FFmpeg (Enabled if SSAA < 1)")]=False,
        open:       Annotated[bool,  TyperOption("--open",             help="(📦 Exporting) Open the Video's Output Directory after render finishes")]=False,
    ) -> Optional[Path]:

        if not self._built:
            log.info(f"{self.who} Building Scene Once")
            self._built = True
            self.build()

        self.relay(Message.Shader.ReloadShaders)

        # Note: Implicit render mode if output is provided or benchmark
        render = render or benchmark or bool(output)
        output_resolution = (width*scale, height*scale)

        # Set useful state flags
        self.realtime  = not render
        self.rendering = render
        self.benchmark = benchmark
        self.headless  = (self.rendering or self.benchmark)

        # Window configuration based on launch mode
        self.resolution = output_resolution
        self.resizable  = not self.rendering
        self.visible    = not self.headless
        self.ssaa       = ssaa
        self.quality    = quality
        self.fps        = fps
        self.time       = 0
        self.time_end   = 0
        self.fullscreen = fullscreen
        self.title      = f"ShaderFlow | {self.__name__}"

        # When rendering, let FFmpeg apply the SSAA, I trust it more (higher quality?)
        if self.rendering and (raw or self.ssaa < 1):
            self.resolution = self.render_resolution
            self.ssaa = 1

        # Create the Vsync event loop
        self.vsync = self.eloop.new(
            callback=self.next,
            frequency=self.fps,
            decoupled=self.rendering,
            precise=True,
        )

        # Setup
        log.info(f"{self.who} Setting up Modules")
        for module in self.modules:
            module.setup()

        # Find the longest audio duration or set time_end
        for module in (not bool(time)) * self.rendering * list(self.find(ShaderFlowAudio)):
            self.time_end = max(self.time_end, module.duration or 0)
        else:
            self.time_end = self.time_end or time or 10

        if self.rendering:
            import arrow

            # Get video output path - if not absolute, save to data directory
            output = Path(output or f"({arrow.utcnow().format('YYYY-MM-DD_HH-mm-ss')}) {self.__name__}")
            output = output if output.is_absolute() else Broken.PROJECT.DIRECTORIES.DATA/output
            output = output.with_suffix(output.suffix or f".{format}")

            # Create FFmpeg process
            self.ffmpeg = (
                BrokenFFmpeg()
                .quiet()
                .overwrite()
                .hwaccel(FFmpegHWAccel.Auto)
                .format(FFmpegFormat.Rawvideo)
                .pixel_format(FFmpegPixelFormat.RGB24)
                .resolution(self.resolution)
                .framerate(self.fps)
                .filter(FFmpegFilterFactory.scale(output_resolution))
                .filter(FFmpegFilterFactory.flip_vertical())
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
                .custom("-t", self.time_end)
            )

            # Add output video
            self.ffmpeg.output(output)
            if not benchmark:
                self.ffmpeg = self.ffmpeg.pipe()

            # Add progress bar
            progress_bar = tqdm.tqdm(
                total=int(self.time_end*self.fps),
                desc=f"Scene ({type(self).__name__}) → Video",
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
        while (self.rendering) or (not self._quit):

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
                self.ffmpeg.write(self._final.texture.fbo(0).read(components=3))

            # Render until time and end are Close
            if (self.time_end - self.time) > 1.5*self.frametime:
                continue

            if not self.benchmark:
                self.ffmpeg.close()

            # Log stats
            progress_bar.refresh()
            progress_bar.close()
            RenderStatus.took = time.perf_counter() - RenderStatus.render_start
            log.info(f"Finished rendering ({output})", echo=not self.benchmark)
            log.info((
                f"• Stats: "
                f"(Took {RenderStatus.took:.2f} s) at "
                f"({self.frame/RenderStatus.took:.2f} FPS | "
                f"{self.time_end/RenderStatus.took:.2f} x Realtime) with "
                f"({RenderStatus.total_frames} Total Frames)"
            ))

            if self.benchmark:
                return

            # Open output directory
            if open: BrokenPath.open_in_file_explorer(output.parent)
            break

        return output

    # # Window related events

    def __window_resize__(self, width: int, height: int) -> None:
        width, height = max(10, width), max(10, height)
        self.imgui.resize(width, height)
        self._width, self._height = width, height
        self.relay(Message.Window.Resize(width=width, height=height))

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
        if action == Keyboard.Keys.ACTION_PRESS:
            self.relay(Message.Keyboard.KeyDown(key=key, modifiers=modifiers))
        elif action == Keyboard.Keys.ACTION_RELEASE:
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
            du=2*(dx/self.width)*self.aspect_ratio,
            dv=2*(dy/self.height)*(-1),
            dx=dx, dy=dy,
        )

    def __window_mouse_press_event__(self, x: int, y: int, button: int) -> None:
        self.imgui.mouse_press_event(x, y, button)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
        self.relay(Message.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event__(self, x: int, y: int, button: int) -> None:
        self.imgui.mouse_release_event(x, y, button)
        if self.imguio.want_capture_mouse and self.render_ui:
            return
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
        elif self.keyboard(Keyboard.Keys.LEFT_ALT):
            self.time_scale.target += (dy)*0.2
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
        if self.keyboard(Keyboard.Keys.LEFT_CTRL):
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
        elif self.keyboard(Keyboard.Keys.LEFT_ALT):
            self.time -= self._mouse_drag_time_factor * (dy/self.height)
            return

        self.relay(Message.Mouse.Drag(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

ShaderFlow.Scene = Scene
