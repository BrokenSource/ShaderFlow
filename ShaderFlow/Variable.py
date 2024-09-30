from typing import Any, Literal, Optional, Self

from attr import define

from Broken import BrokenFluent

DECLARATION_ORDER = (
    "interpolation",
    "direction",
    "qualifier",
    "type",
    "name"
)

GlslQualifier = Literal[
    "uniform",
    "attribute",
    "varying",
]

GlslType = Literal[
    "sampler2D",
    "float",
    "int",
    "bool",
    "vec2",
    "vec3",
    "vec4",
    "mat2",
    "mat3",
    "mat4",
]

GlslDirection = Literal[
    "in",
    "out",
]

GlslInterpolation = Literal[
    "flat",
    "smooth",
    "noperspective",
]

# ------------------------------------------------------------------------------------------------ #

@define(eq=False)
class ShaderVariable(BrokenFluent):
    type: GlslType
    name: str
    value: Optional[Any] = None
    qualifier: Optional[GlslQualifier] = None
    direction: Optional[GlslDirection] = None
    interpolation: Optional[GlslInterpolation] = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Self) -> bool:
        return (self.name == other.name)

    @property
    def size_string(self) -> str:
        return dict(
            float="f",
            int="i",
            bool="i",
            vec2="2f",
            vec3="3f",
            vec4="4f",
        ).get(self.type)

    @property
    def declaration(self) -> str:
        parts = (getattr(self, key) for key in DECLARATION_ORDER)
        return " ".join(filter(None, parts)).strip() + ";"

# ------------------------------------------------------------------------------------------------ #

@define(eq=False)
class Uniform(ShaderVariable):
    qualifier: GlslQualifier = "uniform"

@define(eq=False)
class InVariable(ShaderVariable):
    direction: GlslDirection = "in"

@define(eq=False)
class OutVariable(ShaderVariable):
    direction: GlslDirection = "out"

@define(eq=False)
class FlatVariable(ShaderVariable):
    interpolation: GlslInterpolation = "flat"
