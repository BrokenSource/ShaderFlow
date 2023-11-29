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
    • "Final" quality level is meant for final renders
    """
    Low    = 0
    Medium = 1
    High   = 2
    Ultra  = 3
    Final  = 4

@attrs.define
class SombreroContext(SombreroModule):
    time:       float = 0
    time_scale: float = 1
    dt:         float = 0
    width:      int   = 1920
    height:     int   = 1080
    fps:        float = 60
    msaa:       int   = 0
    ssaa:       int   = 1

    # ModernGL stuff
    opengl: moderngl.Context = None
    window: moderngl_window.BaseWindow = None
    title: str = "Sombrero | ShaderFlow"

    # # Quality

    __quality__: SombreroQuality = SombreroQuality.High

    @property
    def quality(self) -> int:
        return self.__quality__.value

    @quality.setter
    def quality(self, option: int | SombreroQuality) -> None:
        self.__quality__ = SombreroQuality.smart(option)

    # # Window backend

    __backend__: SombreroBackend = SombreroBackend.GLFW

    @property
    def backend(self) -> str:
        return self.__backend__.value

    @backend.setter
    def backend(self, option: str | SombreroBackend) -> None:
        self.__backend__ = SombreroBackend.smart(option)

    # # Resolution

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

    @resolution.setter
    def resolution(self, value: tuple[int, int]) -> None:
        self.width, self.height = value

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def render_resolution(self) -> tuple[int, int]:
        """The window resolution multiplied by the SSAA factor"""
        return int(self.width * self.ssaa), int(self.height * self.ssaa)

    # # Pipeline

    def pipeline(self) -> list[ShaderVariable]:
        return [
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Time",        value=self.time),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}DeltaTime",   value=self.dt),
            ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}Resolution",  value=self.resolution),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}AspectRatio", value=self.aspect_ratio),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Quality",     value=self.quality),
        ]

    # Window methods

    def init(self) -> None:
        """Create the window and the OpenGL context"""

        # Build window settings dictionary
        moderngl_window.conf.settings.WINDOW["class"]        = f"moderngl_window.context.{self.backend}.Window"
        moderngl_window.conf.settings.WINDOW["aspect_ratio"] = self.aspect_ratio
        moderngl_window.conf.settings.WINDOW["size"]         = self.resolution
        moderngl_window.conf.settings.WINDOW["title"]        = self.title
        moderngl_window.conf.settings.WINDOW["samples"]      = self.msaa
        moderngl_window.conf.settings.WINDOW["vsync"]        = False

        # Create window and get context
        self.window = moderngl_window.create_window_from_settings()
        self.opengl = self.window.ctx

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

    def __window_resize_func__(self, width: int, height: int) -> None:
        self.resolution = width, height
        self.relay(SombreroMessage.Window.Resize(width=width, height=height))

    def __window_close_func__(self) -> None:
        self.relay(SombreroMessage.Window.Close())

    def __window_iconify_func__(self, state: bool) -> None:
        self.relay(SombreroMessage.Window.Iconify(state=state))

    def __window_key_event_func__(self, key: int, action: int, modifiers: int) -> None:
        self.relay(SombreroMessage.Keyboard.Key(key=key, action=action, modifiers=modifiers))

    def __window_mouse_position_event_func__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Position(x=x, y=y, dx=dx, dy=dy))

    def __window_mouse_press_event_func__(self, x: int, y: int, button: int) -> None:
        self.relay(SombreroMessage.Mouse.Press(x=x, y=y, button=button))

    def __window_mouse_release_event_func__(self, x: int, y: int, button: int) -> None:
        self.relay(SombreroMessage.Mouse.Release(x=x, y=y, button=button))

    def __window_mouse_drag_event_func__(self, x: int, y: int, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Drag(x=x, y=y, dx=dx, dy=dy))

    def __window_mouse_scroll_event_func__(self, dx: int, dy: int) -> None:
        self.relay(SombreroMessage.Mouse.Scroll(dx=dx, dy=dy))

    def __window_unicode_char_entered_func__(self, char: str) -> None:
        self.relay(SombreroMessage.Keyboard.Unicode(char=char))

    def __window_files_dropped_event_func__(self, files: list[str]) -> None:
        self.relay(SombreroMessage.Window.FileDrop(files=files))

