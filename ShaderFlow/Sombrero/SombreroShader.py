from __future__ import annotations

from . import *

# -------------------------------------------------------------------------------------------------|
# Shader Variable Metaprogramming

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

@attrs.define
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

    # All variable components
    direction:     ShaderVariableDirection     = None
    interpolation: ShaderVariableInterpolation = None
    qualifier:     ShaderVariableQualifier     = None
    type:          ShaderVariableType          = None
    name:          str                         = None
    value:         Any                         = None

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
        }.get(ShaderVariableType.smart(self.type))

    # # To string methods

    @property
    def declaration(self) -> str:
        """String to declared this variable in GLSL"""
        return " ".join(filter(None, (
            self.interpolation,
            self.direction,
            self.qualifier,
            self.type,
            self.name,
        ))) + ";"

    def copy(self) -> ShaderVariable:
        """Creates a copy of this variable"""
        return copy.deepcopy(self)

    @staticmethod
    def smart(*definitions: str | list[str] | ShaderVariable | list[ShaderVariable]) -> list[ShaderVariable]:
        """Smartly creates variables from item or list of variables or string definition"""
        variables = []

        # Iterate on definitions, they can be a ShaderVariable itself or full string definition
        for definition in BrokenUtils.flatten(definitions):

            # Return if already instance of self
            if isinstance(definition, ShaderVariable):
                variables.append(definition)

            # Attempt to smartly parse the string
            elif isinstance(definition, str):
                variable = ShaderVariable()
                string = definition.replace(";", "").strip().split()

                # Iterate on each line item split, attribute if an option, else name
                for i, item in enumerate(string):

                    # Match against known types on enums
                    if item in ShaderVariableDirection.values:
                        variable.direction = item
                    elif item in ShaderVariableQualifier.values:
                        variable.qualifier = item
                    elif item in ShaderVariableType.values:
                        variable.type = item
                    elif item in ShaderVariableInterpolation.values:
                        variable.interpolation = item

                    # Item -2 can be a custom type which is not in the enum
                    elif i == len(string) - 2:
                        variable.type = item

                    # Item -1 is assumed to be the name
                    elif i == len(string) - 1:
                        variable.name = item

                    # Unknown item
                    else:
                        log.warning(f"Unknown item [{item}] on ShaderVariable Smart from [{string}]")

                variables.append(variable)

            else:
                log.warning(f"Unknown item [{definition}] on ShaderVariable Smart")
                continue

        # Return a single variable or list of variables
        return variables

# -------------------------------------------------------------------------------------------------|
# Shader Metaprogramming

@attrs.define
class SombreroShader:
    """Abstracts a Vertex and Fragment shader"""
    version: str = "330"

    # # Vertices

    # Vertices are (x, y) and some (u, v) for texture coordinates
    # Note: ShaderFlow likely will never deal with 3D vertice scenes, use Blender for that
    __vertices__: list[tuple[tuple[float, float], tuple[float, float]]] = attrs.field(factory=list)

    @property
    def vertices(self) -> numpy.ndarray:
        """Get the vertices as a numpy array"""
        return numpy.array(BrokenUtils.flatten(self.__vertices__), dtype="f4").reshape(-1)

    @vertices.setter
    def vertices(self, value: Any) -> None:
        """Set the vertices from a numpy array"""
        self.__vertices__ = value

    def add_vertice(self, x: float=0, y: float=0, u: float=0, v: float=0) -> Self:
        """
        Add a (x, y) = (u, v) vertex to the vertices

        Args:
            x: X coordinate
            y: Y coordinate
            u: U texture coordinate
            v: V texture coordinate

        Returns:
            Self: Fluent interface
        """
        self.__vertices__.append(((x, y), (u, v)))
        return self

    @property
    def vao_definition(self) -> tuple[str]:
        """
        Returns the VAO definition for the vertices

        Returns:
            tuple[str]: VAO definition, like ("3f 2f", "render_vertex", "coords_vertex")
        """
        sizes, names = [], []

        # For all variables of type In, find their size and add to the list
        for variable in self.vertex_variables:
            if variable.direction == ShaderVariableDirection.In.value:
                sizes.append(variable.size_string)
                names.append(variable.name)

        # Return moderngl definition of all sizes and names
        return (" ".join(sizes), *names)

    # # Default GLSL variables

    def __attrs_post_init__(self):
        """Set default values for some variables"""
        self.fragment_variable("out vec4 fragColor")
        self.vertex_variable("in vec2 vertex_position")
        self.vertex_variable("in vec2 vertex_gluv")
        self.vertex_io("flat int instance")

        # "Relative" coordinates
        self.vertex_io("vec2 gluv")
        self.vertex_io("vec2 stuv")

        # "Absolute" coordinates
        self.vertex_io("vec2 astuv")
        self.vertex_io("vec2 agluv")

        # Add a fullscreen center-(0, 0) uv rectangle
        for x, y in itertools.product((-1, 1), (-1, 1)):
            self.add_vertice(x=x, y=y, u=x, v=y)

        # Load default vertex and fragment shaders
        self.vertex   = (SHADERFLOW_DIRECTORIES.SHADERS/"Vertex"  /"Default.glsl").read_text()
        self.fragment = (SHADERFLOW_DIRECTORIES.SHADERS/"Fragment"/"Default.glsl").read_text()

        # Load default prelude
        self.include("prelude", (SHADERFLOW_DIRECTORIES.SHADERS/"Include"/"Prelude.glsl").read_text())

    # # Variables

    vertex_variables:   list[ShaderVariable] = attrs.field(factory=list)
    fragment_variables: list[ShaderVariable] = attrs.field(factory=list)

    def __add_variable__(self, store: dict, *variables: str | dict[str] | ShaderVariable | dict[ShaderVariable]) -> Self:
        """Internal method for smartly adding variables"""
        for variable in ShaderVariable.smart(variables):
            store.append(variable)
        return self

    def vertex_variable(self, *variables: str | list[str] | ShaderVariable | list[ShaderVariable]) -> Self:
        """Smartly adds a variable, list of variables or string definition to the vertex shader

        Args:
            variables: Variable(s) to add, ShaderVariable, list of ShaderVariables or string definition

        Returns:
            Self: Fluent interface
        """
        return self.__add_variable__(self.vertex_variables, variables)

    def fragment_variable(self, variables: str | list[str] | ShaderVariable | list[ShaderVariable]) -> Self:
        """Smartly adds a variable, list of variables or string definition to the fragment shader

        Args:
            variables: Variable(s) to add, ShaderVariable, list of ShaderVariables or string definition

        Returns:
            Self: Fluent interface
        """
        return self.__add_variable__(self.fragment_variables, variables)

    def common_variable(self, variables: str | list[str] | ShaderVariable | list[ShaderVariable]) -> Self:
        """Adds a variable to both vertex and fragment shader

        Args:
            variables: Variable(s) to add, ShaderVariable, list of ShaderVariables or string definition

        Returns:
            Self: Fluent interface
        """
        self.vertex_variable(variables)
        self.fragment_variable(variables)

    def vertex_io(self, variables: str | list[str] | ShaderVariable | list[ShaderVariable]) -> Self:
        """Adds an "out" in vertex and "in" in fragment shader

        Args:
            variables: Variable(s) to add, ShaderVariable, list of ShaderVariables or string definition

        Returns:
            Self: Fluent interface
        """
        for variable in ShaderVariable.smart(variables):
            self.vertex_variable(variable(direction="out").copy())
            self.fragment_variable(variable(direction="in").copy())

    # # Named Includes

    includes: dict[str, str] = attrs.field(factory=dict)

    def include(self, name: str, content: str) -> Self:
        """
        Adds a named include to the shader, for organization and safety
        Note: They are added as sections in the order of includes

        Args:
            name: Name of the include
            content: Content of the include

        Returns:
            Self: Fluent interface
        """
        self.includes[name] = content
        return self

    # # Vertex shader content

    __vertex__: str = ""

    @property
    def vertex(self) -> str:
        """Build the final Vertex Shader (+includes, +variables)"""
        return self.__build__(self.__vertex__, self.vertex_variables)

    @vertex.setter
    def vertex(self, value: str) -> None:
        """Set the Vertex Shader content"""
        self.__vertex__ = value

    # # Fragment shader content

    __fragment__: str = ""

    @property
    def fragment(self) -> str:
        """Build the final Fragment Shader (+includes, +variables)"""
        return self.__build__(self.__fragment__, self.fragment_variables)

    @fragment.setter
    def fragment(self, value: str) -> None:
        """Set the Fragment Shader content"""
        self.__fragment__ = value

    # # Build shader

    def __build__(self, content: str, variables: List[ShaderVariable]) -> str:
        """Build the final shader from the contents provided"""
        shader = []

        @contextmanager
        def section(name: str="") -> None:
            shader.append("\n\n// " + "-"*96 + "|")
            shader.append(f"// Sombrero Section: ({name})\n")
            yield

        # Version - always first
        shader.append(f"#version {self.version}")

        # Add variable definitions
        with section("Variables"):
            for variable in variables:
                shader.append(variable.declaration)

        # Add one section per named include
        for name, include in self.includes.items():
            with section(f"Include - {name}"):
                shader.append(include)

        # Add shader content itself
        with section("Content"):
            shader.append(content)

        # Build final stripped string
        return ('\n'.join(shader)).strip()

