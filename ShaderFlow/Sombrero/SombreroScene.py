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
    Quality levels for Sombrero, generally speaking
    • Not all shaders or objects might react to this setting
    """
    Low    = 0
    Medium = 2
    High   = 4
    Ultra  = 6
    Final  = 8


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
        super().__attrs_post_init__()
        self.register(self)

        # First module -
        self.add(SombreroFrametimer)

        # Create the SSAA Workaround engines
        self.__engine__ = self.add(SombreroEngine)(final=True)
        self.  engine   = self.__engine__.child(SombreroEngine)
        self.__engine__.new_texture("iFinalSSAA").from_module(self.engine)
        self.__engine__.shader.fragment = ("""
            void main() {
                fragColor = texture(iFinalSSAA, astuv);
                fragColor.a = 1.0;
            }
        """)


        # Initialize default modules
        self.add(SombreroCamera)
        self.add(SombreroKeyboard)
        imgui.create_context()
        self.init_window()
        self.setup()

    # ---------------------------------------------------------------------------------------------|
    # Registry

    modules: Dict[SombreroID, SombreroModule] = field(factory=dict)

    def register(self, module: SombreroModule) -> SombreroModule:
        """
        Register a module in the Scene's modules registry

        Args:
            module (SombreroModule): Module to register

        Returns:
            SombreroModule: The module registered
        """
        log.info(f"{module.who} New module registered")
        self.modules[module.uuid] = module
        module.__connected__.add(self.uuid) # Fixme: Why is this not being propagated?
        module.scene = self
        return module

    # ---------------------------------------------------------------------------------------------|
    # Basic information

    time:       float = 0
    time_scale: float = 1
    time_end:   float = 10
    frame:      int   = 0
    fps:        float = 60
    dt:         float = 0
    rdt:        float = 0

    # Base classes and utils for a Scene
    eloop:     BrokenEventLoop = field(factory=BrokenEventLoop)
    vsync:     BrokenEvent     = None
    typer_app: typer.Typer     = None
    ffmpeg:    BrokenFFmpeg    = None

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

    # # Quality

    __quality__: SombreroQuality = SombreroQuality.High

    @property
    def quality(self) -> int:
        return self.__quality__.value

    @quality.setter
    def quality(self, option: int | SombreroQuality) -> None:
        self.__quality__ = SombreroQuality.smart(option)

    # # Resolution

    __width__:  int   = 1920
    __height__: int   = 1080
    __ssaa__:   float = 1.0

    def resize(self, width: int=Unchanged, height: int=Unchanged) -> None:

        # Get the new values of the resolution
        self.__width__   = (width  or self.__width__ )
        self.__height__  = (height or self.__height__)

        log.info(f"{self.who} Resizing window to size ({self.width}x{self.height})")

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
        return int(self.width * self.ssaa), int(self.height * self.ssaa)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    # # SSAA

    @property
    def ssaa(self) -> float:
        return self.__ssaa__

    @ssaa.setter
    def ssaa(self, value: float) -> None:
        log.info(f"{self.who} Changing SSAA to {value}")
        self.__ssaa__ = value
        self.relay(SombreroMessage.Engine.RecreateTextures)

    # # Window backend

    __backend__: SombreroBackend = SombreroBackend.Headless

    @property
    def backend(self) -> str:
        return self.__backend__.value

    @backend.setter
    def backend(self, option: str | SombreroBackend) -> None:
        """Change the ModernGL Window backend, recreates the window"""

        # Optimization: Don't recreate the window if the backend is the same
        if (new := SombreroBackend.smart(option)) == self.__backend__:
            log.info(f"{self.who} Backend already is {self.backend}")
            return

        # Actually change the backend
        log.info(f"{self.who} Changing backend to {new}")
        self.__backend__ = new
        self.init_window()

        # Fixme: Recreating textures was needed, even though the OpenGL Context is healthy
        self.relay(SombreroMessage.Engine.RecreateTextures)

    # Window methods
    icon:        Option[Path, "str"] = SHADERFLOW.RESOURCES.ICON
    opengl:      moderngl.Context    = None
    window:      ModernglWindow      = None
    fullscreen:  bool                = False
    exclusive:   bool                = False

    # Imgui
    render_ui: bool          = False
    imgui:     ModernglImgui = None
    imguio:    Any           = None

    def init_window(self) -> None:
        """Create the window and the OpenGL context"""

        # Destroy the previous window but not the context
        # Workaround: Do not destroy the context on headless, _ctx=Dummy
        if self.window:
            log.info(f"{self.who} Destroying previous Window ")
            self.window._ctx = BrokenNOP()
            self.window.destroy()

        # Dynamically import the Window class based on the backend
        log.info(f"{self.who} Dynamically importing ({self.backend}) Window class")
        Window = getattr(importlib.import_module(f"moderngl_window.context.{self.backend}"), "Window")

        # Create Window
        log.info(f"{self.who} Creating Window")
        self.window = Window(
            size=self.resolution,
            title=self.title,
            aspect_ratio=None,
            resizable=self.resizable,
            vsync=False
        )

        # Assign keys to the SombreroKeyboard
        SombreroKeyboard.Keys = self.window.keys
        SombreroKeyboard.Keys.SHIFT = "SHIFT"
        SombreroKeyboard.Keys.CTRL  = "CTRL"
        SombreroKeyboard.Keys.ALT   = "ALT"

        # First time:  Get the Window's OpenGL Context as our own self.opengl
        # Other times: Assign the previous self.opengl to the new Window, find FBOs
        if not self.opengl:
            log.info(f"{self.who} Binding to Window's OpenGL Context")
            self.opengl = self.window.ctx

        else:
            log.info(f"{self.who} Rebinding to Window's OpenGL Context")

            # Assign the current "Singleton" context to the Window
            self.window._ctx = self.opengl

            # Detect new screen and Framebuffers
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
        self.window.set_icon(self.icon)

        # Workaround: Implement file dropping for GLFW
        if self.__backend__ == SombreroBackend.GLFW:
            log.info(f"{self.who} Implementing file dropping for GLFW")
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event__)

        log.info(f"{self.who} Finished Window creation")

    # ---------------------------------------------------------------------------------------------|
    # SombreroModule

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Time",        value=self.time)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}DeltaTime",   value=self.dt)
        yield ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}Resolution",  value=self.resolution)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}AspectRatio", value=self.aspect_ratio)
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}Quality",     value=self.quality)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}SSAA",        value=self.ssaa)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}FPS",         value=self.fps)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Frame",       value=self.frame)

    def __handle__(self, message: SombreroMessage) -> None:
        if isinstance(message, SombreroMessage.Window.Close):
            self.quit()

        if isinstance(message, SombreroMessage.Keyboard.KeyDown):
            if message.key == SombreroKeyboard.Keys.TAB:
                self.render_ui = not self.render_ui
            if message.key == SombreroKeyboard.Keys.F:
                self.fullscreen = not self.fullscreen
                self.window.fullscreen = self.fullscreen
            if message.key == SombreroKeyboard.Keys.R:
                self.exclusive = not self.exclusive
                self.window.mouse_exclusivity = self.exclusive

    def __update__(self, dt: float):

        # Temporal
        self.time     += dt * self.time_scale
        self.dt        = dt * self.time_scale
        self.rdt       = dt
        self.frame     = int(self.time * self.fps)
        self.vsync.fps = self.fps

        # The scene must be the first one to update as it controls others
        self.update()

        # Update modules in reverse order of addition
        for module in reversed(self.modules.values()):
            if module is not self:
                module.update()

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
                if imgui.tree_node(f"{module.suuid:>2} - {type(module).__name__}", imgui.TREE_NODE_BULLET):
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

        # Swap window buffers
        self.window.swap_buffers()

        return self

    def __ui__(self) -> None:

        # Framerates
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
        imgui.text(f"Quality: {self.__quality__}")
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

    __quit__:      bool = False
    __rendering__: bool = False
    __realtime__:  bool = False

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
        self.__quit__ = True

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        # Fixme: How to deal with ShaderFlow as a dependency scenario?
        return SHADERFLOW.DIRECTORIES.CURRENT_SCENE

    def read_file(self, file: Path, bytes: bool=False) -> str | bytes:
        """
        Read a file relative to the current Scene script

        Args:
            file (Path): File to read, relative to the current Scene script directory
            bytes (bool, optional): Whether to read the file as bytes, defaults to text

        Returns:
            str | bytes: File contents
        """
        file = self.directory/file
        return file.read_bytes() if bytes else file.read_text()

    def main(self,
        # Basic options
        render:    Annotated[bool,  typer.Option("--render",    "-r", help="Render the Scene to a video file")]=False,
        open:      Annotated[bool,  typer.Option("--open",            help="Open the output directory after rendering?")]=False,
        benchmark: Annotated[bool,  typer.Option("--benchmark", "-b", help="Benchmark the Scene's speed on raw rendering")]=False,

        # Rendering options
        width:     Annotated[int,   typer.Option("--width",     "-w", help="Rendering resolution and window width")]=1920,
        height:    Annotated[int,   typer.Option("--height",    "-h", help="Rendering resolution and window height")]=1080,
        fps:       Annotated[int,   typer.Option("--fps",       "-f", help="Target rendering framerate")]=60,
        time:      Annotated[float, typer.Option("--time-end",  "-t", help="How many seconds to render")]=10,
        ssaa:      Annotated[float, typer.Option("--ssaa",      "-s", help="Fractional Super Sampling Anti Aliasing factor (quadratically slower)")]=1,
        quality:   Annotated[str,   typer.Option("--quality",   "-q", help="Shader Quality level (low, medium, high, ultra, final)")]="high",

        # FFmpeg options
        preset:    Annotated[str,   typer.Option("--preset",    "-p", help="FFmpeg render preset.")]="Not implemented yet",

        # Output options
        output:    Annotated[str,   typer.Option("--output",    "-o", help="Name of the output video file: Absolute or relative path; or plain name, defaults to $scene-$date, saved on (DATA/$plain_name)")]=None,
        format:    Annotated[str,   typer.Option("--format",          help="Output video container (mp4, mkv, webm, avi..)")]="mp4",
    ) -> Path | None:
        """
        Launch the Scene in Realtime or Render to a video file
        """

        # Implicit render mode if output is provided
        render = render or benchmark or bool(output)

        # Set useful state flags
        self.__realtime__  = not render
        self.__rendering__ = render
        self.__benchmark__ = benchmark

        # Window configuration based on launch mode
        self.resolution = (width, height)
        self.resizable  = self.__realtime__
        self.ssaa       = ssaa
        self.quality    = quality
        self.fps        = fps
        self.time       = 0
        self.time_end   = time
        self.backend    = SombreroBackend.Headless if render else SombreroBackend.GLFW
        self.title      = f"ShaderFlow | {self.__name__} Scene | BrokenSource"

        # When rendering, let FFmpeg apply the SSAA, I trust it more (higher quality?)
        if self.__rendering__ and SHADERFLOW.CONFIG.default("ffmpeg_ssaa", True):
            self.resolution = self.render_resolution
            self.ssaa = 1

        self.vsync = self.eloop.new(
            callback=self.__update__,
            frequency=self.fps,
            dt=True,
        )

        import time

        if self.__rendering__:
            import arrow

            self.vsync.decoupled = True

            # Get video output path - if not absolute, save to data directory
            output = Path(output or f"({arrow.utcnow().format('YYYY-MM-DD_HH-mm-ss')}) {self.__name__}.mp4")
            output = output if output.is_absolute() else SHADERFLOW.DIRECTORIES.DATA/output
            output = output.with_suffix(f".{format}")

            # Create FFmpeg process
            self.ffmpeg = (
                BrokenFFmpeg()
                .quiet()
                .overwrite()
                .format(FFmpegFormat.Rawvideo)
                .pixel(FFmpegPixelFormat.RGB24)
                .resolution(self.resolution)
                .framerate(self.fps)
                .filter(FFmpegFilterFactory.scale(width, height))
                .filter(FFmpegFilterFactory.flip_vertical())
                .input("-")
            )

            # Add empty audio track if no input audio
            log.fixme("Adding empty audio track for now until better Audio logistics")
            self.ffmpeg = (
                self.ffmpeg
                .custom("-f lavfi -i anullsrc".split())
                .shortest()
            )

            # Apply preset
            self.ffmpeg = (
                self.ffmpeg
                .video_codec(FFmpegVideoCodec.H264)
                .preset(FFmpegH264Preset.Slow)
                .tune(FFmpegH264Tune.Film)
                .quality(FFmpegH264Quality.High)
            )

            log.todo("Apply FFmpeg SombreroScene rendering preset")

            # Add output video
            self.ffmpeg.output(output)
            self.ffmpeg = self.ffmpeg.pipe(open=not benchmark)

            # Add progress bar
            progress_bar = tqdm(
                total=int(self.time_end * self.fps),
                desc="Rendering video",
                leave=False,
                unit="Frame"
            )

        # Benchmark time
        render_start = time.perf_counter()

        # Main rendering loop
        while not self.__quit__:

            # Keep calling event loop until self was updated
            if self.eloop.next() is not self:
                continue

            if not self.__rendering__:
                continue

            # Rendering logic
            progress_bar.update(1)

            # Write new frame to FFmpeg
            if not self.__benchmark__:
                self.ffmpeg.write(self.window.fbo.read(components=3))

            # Quit if rendered until the end
            if self.time <= self.time_end:
                continue

            if not self.__benchmark__:
                self.ffmpeg.close()

            # Log stats
            took = time.perf_counter() - render_start
            log.info(f"Finished rendering ({output})")
            log.info((
                f"• Stats: "
                f"Took {took:.2f}s at "
                f"{self.frame/took:.2f} FPS, "
                f"{self.time_end/took:.2f}x Realtime"
            ))

            if self.__benchmark__:
                return

            # Open output directory
            if open: BrokenPath.open_in_file_explorer(output.parent)

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

    def __dxdy2duv__(self, dx: int=0, dy: int=0) -> dict[str, float]:
        """Convert a DXDY pixel coordinate into a Center-UV normalized coordinate"""
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
            **self.__dxdy2duv__(dx=dx, dy=dy),
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
            **self.__dxdy2duv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_scroll_event__(self, dx: int, dy: int) -> None:
        # Prioritize imgui events
        self.imgui.mouse_scroll_event(dx, dy)
        if self.imguio.want_capture_mouse: return

        # Calculate and relay the scroll event
        self.relay(SombreroMessage.Mouse.Scroll(
            **self.__dxdy2duv__(dx=dx, dy=dy)
        ))

    # # Linear Algebra utilities

    def smoothstep(self, x: float) -> float:
        return numpy.clip(3*x**2 - 2*x**3, 0, 1)
