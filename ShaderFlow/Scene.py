from . import *


@define
class ShaderFlowScene(ShaderFlowModule):
    metadata = None # Todo
    __name__ = "ShaderFlowScene"

    """
    Implementing Fractional SSAA is a bit tricky:
    • A Window's FBO always match its real resolution (can't final render in other resolution)
    • We need a final shader to sample from some other SSAA-ed texture to the window

    For that, a internal self.__engine__ is used to sample from the user's main self.engine
    • __engine__: Uses the FBO of the Window, simply samples from a `final` texture to the screen
    • engine:     Scene's main engine, where the user's final shader is rendered to
    """
    __engine__: ShaderFlowEngine = None
    engine:     ShaderFlowEngine = None

    def __attrs_post_init__(self):
        imgui.create_context()
        self.register(self)

    def __build__(self):

        # Init Imgui
        self.imguio = imgui.get_io()
        self.imguio.font_global_scale = SHADERFLOW.CONFIG.imgui.default("font_scale", 1.0)
        self.imguio.fonts.add_font_from_file_ttf(
            str(BROKEN.RESOURCES.FONTS/"DejaVuSans.ttf"),
            16*self.imguio.font_global_scale,
        )

        # Default modules
        self.init_window()
        self.add(ShaderFlowFrametimer)
        self.add(ShaderFlowCamera)
        self.add(ShaderFlowKeyboard)

        # Create the SSAA Workaround engines
        self.__engine__ = self.add(ShaderFlowEngine)(final=True)
        self.  engine   = self.__engine__.add(ShaderFlowEngine)
        self.__engine__.new_texture(name="iFinalTexture").from_module(self.engine)
        self.__engine__.fragment = SHADERFLOW.RESOURCES.FRAGMENT/"Final.glsl"

    # ---------------------------------------------------------------------------------------------|
    # Registry

    modules: Deque[ShaderFlowModule] = Factory(deque)

    def register(self, module: ShaderFlowModule, **kwargs) -> ShaderFlowModule:
        self.modules.append(module := module(scene=self, **kwargs))
        log.trace(f"{module.who} New module registered")
        module._build()
        return module

    # ---------------------------------------------------------------------------------------------|
    # Basic information

    time:       Seconds = 0.0
    time_end:   Seconds = 10.0
    time_scale: float   = Factory(lambda: DynamicNumber(value=1, frequency=5))
    frame:      int     = 0
    fps:        Hertz   = 60.0
    dt:         Seconds = 0.0
    rdt:        Seconds = 0.0

    @property
    def frametime(self) -> Seconds:
        return 1/self.fps

    # Base classes and utils for a Scene
    eloop:         BrokenEventLoop   = Factory(BrokenEventLoop)
    vsync:         BrokenEventClient = None
    typer_app:     TyperApp          = None
    broken_ffmpeg: BrokenFFmpeg      = None

    # # Title

    __title__: str = "ShaderFlow"

    @property
    def title(self) -> str:
        return self.__title__

    @title.setter
    def title(self, value: str) -> None:
        self.__title__ = value
        self.window.title = value

    # # Resizable

    __resizable__: bool  = True

    @property
    def resizable(self) -> bool:
        return self.__resizable__

    @resizable.setter
    def resizable(self, value: bool) -> None:
        self.__resizable__    = value
        self.window.resizable = value
        glfw.set_window_attrib(self.window._window, glfw.RESIZABLE, value)

    # # Visible

    __visible__: bool = False

    @property
    def visible(self) -> bool:
        return self.__visible__

    @visible.setter
    def visible(self, value: bool) -> None:
        self.__visible__    = value
        self.window.visible = value

    # # Resolution

    quality: float = Field(default=75, converter=lambda x: max(0, min(100, float(x))))

    __width__:  int   = 1920
    __height__: int   = 1080
    __ssaa__:   float = 1.0

    def resize(self, width: int=Unchanged, height: int=Unchanged) -> None:
        self.__width__  = BrokenUtils.round(width  or self.__width__,  2, type=int)
        self.__height__ = BrokenUtils.round(height or self.__height__, 2, type=int)
        log.debug(f"{self.who} Resizing window to size ({self.width}x{self.height})")
        self.opengl.screen.viewport = (0, 0, self.width, self.height)
        self.window.size = self.resolution

        # Fixme: Necessary now without headless support? Apparently no
        # self.relay(ShaderFlowMessage.Window.Resize(width=self.width, height=self.height))
        # self.relay(ShaderFlowMessage.Engine.RecreateTextures())

    def read_screen(self) -> bytes:
        return self.opengl.screen.read(components=3)

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
        self.relay(ShaderFlowMessage.Engine.RecreateTextures)

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

    # Window attributes
    icon:      PathLike         = SHADERFLOW.RESOURCES.ICON
    opengl:    moderngl.Context = None
    window:    ModernglWindow   = None
    render_ui: bool             = False
    imgui:     ModernglImgui    = None
    imguio:    Any              = None

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""
        log.debug(f"{self.who} Creating Window")

        self.window = importlib.import_module(f"moderngl_window.context.glfw").Window(
            size=self.resolution,
            title=self.title,
            resizable=self.resizable,
            visible=self.visible,
            fullscreen=self.fullscreen,
            vsync=False if self.rendering else self.window_vsync,
        )
        ShaderFlowKeyboard.set_keymap(self.window.keys)
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

        # Workaround: Implement file dropping for GLFW and Keys, parallel icon setting
        glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)
        BrokenThread.new(target=self.window.set_icon, icon_path=self.icon)
        ShaderFlowKeyboard.Keys.LEFT_SHIFT = glfw.KEY_LEFT_SHIFT
        ShaderFlowKeyboard.Keys.LEFT_CTRL  = glfw.KEY_LEFT_CONTROL
        ShaderFlowKeyboard.Keys.LEFT_ALT   = glfw.KEY_LEFT_ALT

        log.debug(f"{self.who} Finished Window creation")

    # ---------------------------------------------------------------------------------------------|
    # ShaderFlowModule

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "float", "iTime",        self.time)
        yield ShaderVariable("uniform", "float", "iTimeEnd",     self.time_end)
        yield ShaderVariable("uniform", "float", "iTau",         self.time/self.time_end)
        yield ShaderVariable("uniform", "float", "iDeltaTime",   self.dt)
        yield ShaderVariable("uniform", "vec2",  "iResolution",  self.resolution)
        yield ShaderVariable("uniform", "float", "iAspectRatio", self.aspect_ratio)
        yield ShaderVariable("uniform", "float", "iQuality",     self.quality/100)
        yield ShaderVariable("uniform", "float", "iSSAA",        self.ssaa)
        yield ShaderVariable("uniform", "float", "iFPS",         self.fps)
        yield ShaderVariable("uniform", "float", "iFrame",       self.frame)
        yield ShaderVariable("uniform", "bool",  "iRendering",   self.rendering)
        yield ShaderVariable("uniform", "bool",  "iRealtime",    self.realtime)

    def __handle__(self, message: ShaderFlowMessage) -> None:
        if isinstance(message, ShaderFlowMessage.Window.Close):
            self.quit()

        if isinstance(message, ShaderFlowMessage.Keyboard.KeyDown):
            if message.key == ShaderFlowKeyboard.Keys.TAB:
                self.render_ui  = not self.render_ui
            if message.key == ShaderFlowKeyboard.Keys.F:
                self.fullscreen = not self.fullscreen
            if message.key == ShaderFlowKeyboard.Keys.R:
                self.exclusive  = not self.exclusive
            if message.key == ShaderFlowKeyboard.Keys.F2:
                import arrow
                time  = arrow.now().format("YYYY-MM-DD_HH-mm-ss")
                image = PIL.Image.frombytes("RGB", self.resolution, self.read_screen())
                image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
                path  = SHADERFLOW.DIRECTORIES.SCREENSHOTS/f"({time}) {self.__name__}.jpg"
                BrokenThread.new(target=image.save, fp=path, mode="JPEG", quality=95)
                log.minor(f"Saving screenshot to ({path})")

    def __next__(self, dt: float) -> Self:

        # Temporal
        self.time_scale.next(dt=abs(dt))
        self.time     += dt * self.time_scale
        self.dt        = dt * self.time_scale
        self.rdt       = dt
        self.frame     = int(self.time * self.fps)
        self.vsync.fps = self.fps

        # Update modules in reverse order of addition
        # Note: Non-engine first as pipeline might change
        for module in reversed(self.modules):
            if not isinstance(module, ShaderFlowEngine):
                module._update()
        for module in reversed(self.modules):
            if isinstance(module, ShaderFlowEngine):
                module._update()

        # Todo: Move to a Utils class for other stuff such as theming?
        if self.render_ui:
            self.__engine__.fbo.use()
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
        if (state := imgui.input_float("SSAA", self.ssaa, 0.1, 0.1, "%.2fx"))[0]:
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
    headless:  bool = False

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
        fullscreen: Annotated[bool,  TyperOption("--fullscreen",       help="(Basic    ) Start the Real Time Window in Fullscreen Mode")]=False,
        benchmark:  Annotated[bool,  TyperOption("--benchmark",  "-b", help="(Basic    ) Benchmark the Scene's speed on raw rendering")]=False,
        scale:      Annotated[float, TyperOption("--scale",      "-x", help="(Quality  ) Pre-multiply Width and Height by a Scale Factor")]=1.0,
        quality:    Annotated[float, TyperOption("--quality",    "-q", help="(Quality  ) Shader Quality level if supported (0-100%)")]=80,
        ssaa:       Annotated[float, TyperOption("--ssaa",       "-s", help="(Quality  ) Fractional Super Sampling Anti Aliasing factor, O(N²) GPU cost")]=1.0,
        render:     Annotated[bool,  TyperOption("--render",     "-r", help="(Exporting) Export the current Scene to a Video File defined on --output")]=False,
        output:     Annotated[str,   TyperOption("--output",     "-o", help="(Exporting) Output File Name: Absolute, Relative Path or Plain Name. Saved on ($DATA/$(plain_name or $scene-$date))")]=None,
        format:     Annotated[str,   TyperOption("--format",           help="(Exporting) Output Video Container (mp4, mkv, webm, avi..), overrides --output one")]="mp4",
        time:       Annotated[float, TyperOption("--time-end",   "-t", help="(Exporting) How many seconds to render, defaults to 10 or longest ShaderFlowAudio")]=None,
        raw:        Annotated[bool,  TyperOption("--raw",              help="(Exporting) Send raw OpenGL Frames before GPU SSAA to FFmpeg (Enabled if SSAA < 1)")]=False,
        preview:    Annotated[bool,  TyperOption("--preview",    "-p", help="(Exporting) Show a Preview Window, slightly slower render times")]=False,
        open:       Annotated[bool,  TyperOption("--open",             help="(Exporting) Open the Video's Output Directory after render finishes")]=False,
    ) -> Optional[Path]:

        # Note: Implicit render mode if output is provided or benchmark
        render = render or benchmark or bool(output)

        # Set useful state flags
        self.realtime  = not render
        self.rendering = render
        self.benchmark = benchmark
        self.headless  = (self.rendering or self.benchmark) and (not preview)

        # Window configuration based on launch mode
        self.resolution = (width*scale, height*scale)
        self.visible    = not (self.rendering and self.headless)
        self.resizable  = not self.rendering
        self.ssaa       = ssaa
        self.quality    = quality
        self.fps        = fps
        self.time       = 0
        self.time_end   = 0
        self.fullscreen = fullscreen
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
        for module in self.modules:
            module._setup()

        # Find the longest audio duration or set time_end
        for module in (not bool(time)) * self.rendering * list(self.find(ShaderFlowAudio)):
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
                .hwaccel(FFmpegHWAccel.Auto)
                .format(FFmpegFormat.Rawvideo)
                .pixel_format(FFmpegPixelFormat.RGB24)
                .resolution(self.resolution)
                .framerate(self.fps)
                .filter(FFmpegFilterFactory.scale(self.resolution))
                .filter(FFmpegFilterFactory.flip_vertical())
                .input("-")
            )

            # Fixme: Is this the correct point for modules to manage FFmpeg?
            for module in self.modules:
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
                desc=f"ShaderFlowScene ({type(self).__name__}) → Video",
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
                self.broken_ffmpeg.write(self.read_screen())

            # Render until time and end are Close
            if (self.time_end - self.time) > 1.5*self.frametime:
                continue

            if not self.benchmark:
                self.broken_ffmpeg.close()

            # Log stats
            progress_bar.refresh()
            progress_bar.close()
            RenderStatus.took = time.perf_counter() - RenderStatus.render_start
            log.info(f"Finished rendering ({output})", echo=not self.benchmark)
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
        width, height = max(10, width), max(10, height)
        self.imgui.resize(width, height)
        self.__width__, self.__height__ = width, height
        self.relay(ShaderFlowMessage.Window.Resize(width=width, height=height))

    def __window_close__(self) -> None:
        self.relay(ShaderFlowMessage.Window.Close())

    def __window_iconify__(self, state: bool) -> None:
        self.relay(ShaderFlowMessage.Window.Iconify(state=state))

    def __window_files_dropped_event__(self, *stuff: list[str]) -> None:
        self.relay(ShaderFlowMessage.Window.FileDrop(files=stuff[1]))

    # # Keyboard related events

    def __window_key_event__(self, key: int, action: int, modifiers: int) -> None:
        self.imgui.key_event(key, action, modifiers)
        if self.imguio.want_capture_keyboard: return

        # Calculate and relay the key event
        self.relay(ShaderFlowMessage.Keyboard.Press(key=key, action=action, modifiers=modifiers))

        # Key UP and Down
        if action == ShaderFlowKeyboard.Keys.ACTION_PRESS:
            self.relay(ShaderFlowMessage.Keyboard.KeyDown(key=key, modifiers=modifiers))
        elif action == ShaderFlowKeyboard.Keys.ACTION_RELEASE:
            self.relay(ShaderFlowMessage.Keyboard.KeyUp(key=key, modifiers=modifiers))

    def __window_unicode_char_entered__(self, char: str) -> None:
        if self.imguio.want_capture_keyboard: return
        self.relay(ShaderFlowMessage.Keyboard.Unicode(char=char))

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
            du=2*(dx/self.width)*self.aspect_ratio,
            dv=2*(dy/self.height)*(-1),
            dx=dx, dy=dy,
        )

    # Actual events

    def __window_mouse_position_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_position_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the position event
        self.relay(ShaderFlowMessage.Mouse.Position(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_press_event__(self, x: int, y: int, button: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_press_event(x, y, button)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the press event
        self.relay(ShaderFlowMessage.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event__(self, x: int, y: int, button: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_release_event(x, y, button)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the release event
        self.relay(ShaderFlowMessage.Mouse.Release(
            **self.__xy2uv__(x, y),
            button=button
        ))

    _mouse_drag_time_factor: float = 4
    """How much seconds to scroll in time when the mouse moves the full window height"""

    def __window_mouse_drag_event__(self, x: int, y: int, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_drag_event(x, y, dx, dy)
        if self.imguio.want_capture_mouse: return

        # Rotate the camera on Shift
        if self.keyboard(ShaderFlowKeyboard.Keys.LEFT_CTRL):
            cx, cy = (x - self.width/2), (y - self.height/2)
            angle = math.atan2(cy+dy, cx+dx) - math.atan2(cy, cx)
            if abs(angle) > math.pi: angle -= 2*math.pi
            self.camera.rotate(self.camera.base_z, angle=math.degrees(angle))
            return

        if self.exclusive:
            self.camera.apply_zoom(-dy/500)
            self.camera.rotate(self.camera.base_z, angle=-dx/10)
            return

        # Time Travel on Alt
        if self.keyboard(ShaderFlowKeyboard.Keys.LEFT_ALT):
            self.time -= self._mouse_drag_time_factor * (dy/self.height)
            return

        # Calculate and relay the drag event
        self.relay(ShaderFlowMessage.Mouse.Drag(
            **self.__dxdy2dudv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_scroll_event__(self, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_scroll_event(dx, dy)
        if self.imguio.want_capture_mouse: return

        if self.keyboard(ShaderFlowKeyboard.Keys.LEFT_ALT):
            self.time_scale.target += (dy)*0.2
            return

        # Calculate and relay the scroll event
        self.relay(ShaderFlowMessage.Mouse.Scroll(
            **self.__dxdy2dudv__(dx=dx, dy=dy)
        ))

    # # Linear Algebra utilities

    def smoothstep(self, x: float) -> float:
        if x <= 0: return 0
        if x >= 1: return 1
        return 3*x**2 - 2*x**3
