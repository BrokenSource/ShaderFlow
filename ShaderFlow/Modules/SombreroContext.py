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
    time:   float = 0
    dt:     float = 0
    width:  int   = 1920
    height: int   = 1080
    fps:    float = 60
    msaa:   int   = 0
    ssaa:   int   = 1

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

    # # OpenGL

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

    # # Pipeline

    def pipeline(self) -> list[ShaderVariable]:
        return [
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Time",        value=self.time),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}DeltaTime",   value=self.dt),
            ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}Resolution",  value=self.resolution),
            ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.prefix}AspectRatio", value=self.aspect_ratio),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}Quality",     value=self.quality),
        ]