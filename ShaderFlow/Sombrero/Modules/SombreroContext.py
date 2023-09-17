from . import *


class SombreroBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

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
    width:  int   = 1920
    height: int   = 1080
    fps:    float = 60
    msaa:   int   = 1
    ssaa:   int   = 1

    # # Quality

    __quality__: SombreroQuality = SombreroQuality.High

    @property
    def quality(self) -> int:
        return self.__quality__.value

    @quality.setter
    def quality(self, option: int | SombreroQuality) -> None:
        self.__quality__ = SombreroQuality.smart(option)

    # # Resolution

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

    @resolution.setter
    def resolution(self, value: tuple[int, int]) -> None:
        self.width, self.height = value

    # # Window backend

    backend: SombreroBackend = SombreroBackend.GLFW
    title:   str             = "Sombrero"

    # # Messages, pipeline

    def update(self, time: float, dt: float) -> None:
        self.time += dt

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Window.Resize):
            self.resolution = (message.width, message.height)

    @property
    def pipeline(self) -> dict[str, Any]:
        return [
            ShaderVariable(qualifier="uniform", type="float", name="iTime",       value=self.time),
            ShaderVariable(qualifier="uniform", type="vec2",  name="iResolution", value=self.resolution),
        ]

# Access a bound SombreroSettings with a .settings property
SombreroModule.broken_extend("context", SombreroContext)
