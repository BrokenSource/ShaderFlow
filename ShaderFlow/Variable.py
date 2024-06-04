from __future__ import annotations

from typing import Any

from attr import define
from loguru import logger as log

from Broken import BrokenEnum, BrokenFluentBuilder


class ShaderVariableQualifier(BrokenEnum):
    """Guidance enum for GLSL variable qualifiers options"""
    Uniform   = "uniform"
    Attribute = "attribute"
    Varying   = "varying"

class ShaderVariableType(BrokenEnum):
    """Guidance enum for GLSL variable types"""
    Float     = "float"
    Int       = "int"
    Bool      = "bool"
    Vec2      = "vec2"
    Vec3      = "vec3"
    Vec4      = "vec4"
    Mat2      = "mat2"
    Mat3      = "mat3"
    Mat4      = "mat4"
    Sampler2D = "sampler2D"

class ShaderVariableInterpolation(BrokenEnum):
    """Guidance enum for GLSL variable interpolation options"""
    Flat          = "flat"
    Smooth        = "smooth"
    NoPerspective = "noperspective"

class ShaderVariableDirection(BrokenEnum):
    """Guidance enum for GLSL variable direction options"""
    In  = "in"
    Out = "out"

@define(eq=False)
class ShaderVariable(BrokenFluentBuilder):
    """
    Metaprogramming class to define a shader variable

    "uniform vec2 resolution;"
    • interpolation: "flat", "smooth", "noperspective" (smooth)
    • qualifier: "uniform"
    • type:      "vec2"
    • name:      "resolution"
    • value:     Any (of self.size)
    """
    qualifier:     ShaderVariableQualifier     = None
    type:          ShaderVariableType          = None
    name:          str                         = None
    value:         Any                         = None
    direction:     ShaderVariableDirection     = None
    interpolation: ShaderVariableInterpolation = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: ShaderVariable) -> bool:
        return self.name == other.name

    @property
    def size_string(self) -> str:
        """Get the size string for this variable"""
        return {
            ShaderVariableType.Float: "f",
            ShaderVariableType.Int:   "i",
            ShaderVariableType.Bool:  "i",
            ShaderVariableType.Vec2:  "2f",
            ShaderVariableType.Vec3:  "3f",
            ShaderVariableType.Vec4:  "4f",
        }.get(ShaderVariableType.get(self.type))

    # # To string methods

    @property
    def declaration(self) -> str:
        """String to declared this variable in GLSL"""
        return (" ".join(filter(None, (
            self.interpolation,
            self.direction,
            self.qualifier,
            self.type,
            self.name,
        )))).strip() + ";"

    @staticmethod
    def smart(definition: str | ShaderVariable) -> ShaderVariable:
        """Smartly creates variables from item or list of variables or string definition"""

        # Return if already instance of self
        if isinstance(definition, ShaderVariable):
            return definition

        # Attempt to smartly parse the string
        elif isinstance(definition, str):
            variable = ShaderVariable()
            string = definition.replace(";", "").strip().split()

            # Iterate on each line item split, attribute if an option, else name
            for i, item in enumerate(string):

                # Match against known types on enums
                if item in ShaderVariableDirection.values():
                    variable.direction = item
                elif item in ShaderVariableQualifier.values():
                    variable.qualifier = item
                elif item in ShaderVariableType.values():
                    variable.type = item
                elif item in ShaderVariableInterpolation.values():
                    variable.interpolation = item

                # Item -2 can be a custom type which is not in the enum
                elif i == len(string) - 2:
                    variable.type = item

                # Item -1 is assumed to be the name
                elif i == len(string) - 1:
                    variable.name = item

                # Unknown item
                else:
                    log.warning(f"Unknown item ({item}) on ShaderVariable Smart from ({string})")

        return variable
