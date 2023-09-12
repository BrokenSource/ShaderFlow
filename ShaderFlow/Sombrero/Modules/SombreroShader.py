from . import *


@attrs.define
class ShaderVariable:
    """
    Metaprogramming class to define a shader variable

    "uniform vec2 resolution;"
    • qualifier: "uniform"
    • type:      "vec2"
    • name:      "resolution"
    • default:   Any
    • interpolation: "flat", "smooth", "noperspective"
    """
    parameter: str = "uniform"
    type:      str = None
    name:      str = None
    default:   str = None
    interpolation: str = ""

    def __hash__(self):
        return self

@attrs.define
class SombreroShader(SombreroModule):

    # # Variables

    # # Core content

    __vertex__:   str = None
    __fragment__: str = None

    @property
    def vertex(self) -> str:
        return self.__vertex__

    @vertex.setter
    def vertex(self, value: str) -> None:
        self.__vertex__ = value

    @property
    def fragment(self) -> str:
        return self.__fragment__

    @fragment.setter
    def fragment(self, value: str) -> None:
        self.__fragment__ = value
