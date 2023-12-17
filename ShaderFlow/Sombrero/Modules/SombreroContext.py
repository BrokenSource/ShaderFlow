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
    Medium = 1
    High   = 2
    Ultra  = 3
    Final  = 4

@attrs.define
class SombreroContext(SombreroModule):

    # Basic information
    version:    int   = 330
    time:       float = 0
    time_scale: float = 1
    time_end:   float = 10
    frame:      int   = 0
    fps:        float = 60
    dt:         float = 0

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
    __ssaa__:   float = 1

    def resize(self, width: int=Unchanged, height: int=Unchanged) -> None:

        # Get the new values of the resolution
        self.__width__   = (width  or self.__width__ )
        self.__height__  = (height or self.__height__)

        log.info(f"{self.who} Resizing window to {self.width}x{self.height}")

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

    # # Pipeline

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Time",        value=self.time)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}DeltaTime",   value=self.dt)
        yield ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}Resolution",  value=self.resolution)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}AspectRatio", value=self.aspect_ratio)
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}Quality",     value=self.quality)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}SSAA",        value=self.ssaa)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}FPS",         value=self.fps)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Frame",       value=self.frame)

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

    icon: Option[Path, "str"] = SHADERFLOW.RESOURCES.ICON
    keys:   ModernglKeys      = None
    opengl: moderngl.Context  = None
    window: ModernglWindow    = None

    def setup(self):
        log.info(f"{self.who} Creating OpenGL Context")
        self.init_window()

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
        Window    = getattr(importlib.import_module(f"moderngl_window.context.{self.backend}"), "Window")

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

        # Bind window events to relay
        self.window.resize_func               = self.__window_resize_func__
        self.window.close_func                = self.__window_close_func__
        self.window.iconify_func              = self.__window_iconify_func__
        self.window.key_event_func            = self.__window_key_event_func__
        self.window.mouse_position_event_func = self.__window_mouse_position_event_func__
        self.window.mouse_press_event_func    = self.__window_mouse_press_event_func__
        self.window.mouse_release_event_func  = self.__window_mouse_release_event_func__
        self.window.mouse_drag_event_func     = self.__window_mouse_drag_event_func__
        self.window.mouse_scroll_event_func   = self.__window_mouse_scroll_event_func__
        self.window.unicode_char_entered_func = self.__window_unicode_char_entered_func__
        self.window.files_dropped_event_func  = self.__window_files_dropped_event_func__
        self.window.set_icon(self.icon)

        # Workaround: Implement file dropping for GLFW
        if self.__backend__ == SombreroBackend.GLFW:
            glfw.set_drop_callback(self.window._window, self.__window_files_dropped_event_func__)

    # # Window related events

    def __window_resize_func__(self, width: int, height: int) -> None:
        self.__width__, self.__height__ = width, height
        self.relay(SombreroMessage.Window.Resize(width=width, height=height))

    def __window_close_func__(self) -> None:
        self.relay(SombreroMessage.Window.Close())

    def __window_iconify_func__(self, state: bool) -> None:
        self.relay(SombreroMessage.Window.Iconify(state=state))

    def __window_files_dropped_event_func__(self, *stuff: list[str]) -> None:
        if self.__backend__ == SombreroBackend.GLFW:
            self.relay(SombreroMessage.Window.FileDrop(files=stuff[1]))

    # # Keyboard related events

    def __window_key_event_func__(self, key: int, action: int, modifiers: int) -> None:
        self.relay(SombreroMessage.Keyboard.Press(key=key, action=action, modifiers=modifiers))

    def __window_unicode_char_entered_func__(self, char: str) -> None:
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

    def __window_mouse_position_event_func__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Position(
            **self.__dxdy2duv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_press_event_func__(self, x: int, y: int, button: int) -> None:
        self.relay(SombreroMessage.Mouse.Press(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_release_event_func__(self, x: int, y: int, button: int) -> None:
        self.relay(SombreroMessage.Mouse.Release(
            **self.__xy2uv__(x, y),
            button=button
        ))

    def __window_mouse_drag_event_func__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Drag(
            **self.__dxdy2duv__(dx=dx, dy=dy),
            **self.__xy2uv__(x=x, y=y)
        ))

    def __window_mouse_scroll_event_func__(self, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Scroll(
            **self.__dxdy2duv__(dx=dx, dy=dy)
        ))

