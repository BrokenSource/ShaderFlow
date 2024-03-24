import contextlib
import functools
import itertools
from multiprocessing import Process
from typing import Any
from typing import Iterable
from typing import List
from typing import Self
from typing import Tuple

import imgui
import moderngl
import numpy
from attr import Factory
from attr import define

import Broken
import ShaderFlow
from Broken.Base import denum
from Broken.Loaders.LoaderString import LoaderString
from Broken.Logging import log
from ShaderFlow import SHADERFLOW
from ShaderFlow.Message import Message
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Texture import ShaderTexture
from ShaderFlow.Variable import ShaderVariable
from ShaderFlow.Variable import ShaderVariableDirection


@define
class Shader(ShaderModule):
    version:            int                  = 330
    program:            moderngl.Program     = None
    vao:                moderngl.VertexArray = None
    vbo:                moderngl.Buffer      = None
    texture:            ShaderTexture        = None
    clear:              bool                 = False
    instances:          int                  = 1
    vertices:           List[float]          = Factory(list)
    vertex_variables:   set[ShaderVariable]  = Factory(set)
    fragment_variables: set[ShaderVariable]  = Factory(set)

    def __post__(self):
        """Set default values for some variables"""
        self.texture = ShaderTexture(scene=self.scene, name=self.name, track=True)
        self.fragment_variable("out vec4 fragColor")
        self.vertex_variable("in vec2 vertex_position")
        self.vertex_variable("in vec2 vertex_gluv")
        self.vertex_io("flat int instance")
        self.vertex_io("vec2 gluv")
        self.vertex_io("vec2 stuv")
        self.vertex_io("vec2 astuv")
        self.vertex_io("vec2 agluv")
        self.vertex_io("vec2 fragCoord")
        self.vertex_io("vec2 glxy")
        self.vertex_io("vec2 stxy")

        # Add a fullscreen center-(0, 0) uv rectangle
        for x, y in itertools.product((-1, 1), (-1, 1)):
            self.add_vertice(x=x, y=y, u=x, v=y)

        # Load default vertex and fragment shaders
        self._vertex   = (SHADERFLOW.RESOURCES.VERTEX/  "Default.glsl")
        self._fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Default.glsl")

    def add_vertice(self, x: float=0, y: float=0, u: float=0, v: float=0) -> Self:
        self.vertices.extend((x, y, u, v))
        return self

    def clear_vertices(self) -> Self:
        self.vertices = []

    def vertex_variable(self, variable: ShaderVariable) -> Self:
        self.vertex_variables.add(ShaderVariable.smart(variable))

    def fragment_variable(self, variable: ShaderVariable) -> Self:
        self.fragment_variables.add(ShaderVariable.smart(variable))

    def common_variable(self, variable: ShaderVariable) -> Self:
        self.vertex_variable(variable)
        self.fragment_variable(variable)

    def vertex_io(self, variable: ShaderVariable) -> Self:
        variable = ShaderVariable.smart(variable)
        self.vertex_variable(variable.copy(direction="out"))
        self.fragment_variable(variable.copy(direction="in"))

    @property
    def vao_definition(self) -> Tuple[str]:
        """("2f 2f", "render_vertex", "coords_vertex")"""
        sizes, names = [], []
        for variable in self.vertex_variables:
            if variable.direction == ShaderVariableDirection.In.value:
                sizes.append(variable.size_string)
                names.append(variable.name)
        return (" ".join(sizes), *names)

    def _build_shader(self, content: str, variables: Iterable[ShaderVariable]) -> str:
        """Build the final shader from the contents provided"""
        shader = []

        @contextlib.contextmanager
        def section(name: str=""):
            shader.append("\n\n// " + "-"*96 + "|")
            shader.append(f"// ShaderFlow Section: ({name})\n")
            yield

        shader.append(f"#version {self.version}")

        # Add variable definitions
        with section("Variables"):
            for variable in variables:
                shader.append(variable.declaration)

        with section("Include - ShaderFlow"):
            shader.append(SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"ShaderFlow.glsl")

        # Add all modules includes to the shader
        for module in self.scene.modules:
            for defines in module.defines():
                shader.append(defines)

            for include in filter(None, module.includes()):
                with section(f"Include - {module.who}"):
                    shader.append(include)

        # Add shader content itself
        with section("Content"):
            shader.append(content)

        return '\n'.join(map(LoaderString, shader))

    # # Vertex shader content

    _vertex: str = ""

    @property
    def vertex(self) -> str:
        return self._build_shader(self._vertex, self.vertex_variables)

    @vertex.setter
    def vertex(self, value: str) -> None:
        self._vertex = LoaderString(value)
        self.load_shaders()

    # # Fragment shader content

    _fragment: str = ""

    @property
    def fragment(self) -> str:
        return self._build_shader(self._fragment, self.fragment_variables)

    @fragment.setter
    def fragment(self, value: str) -> None:
        self._fragment = LoaderString(value)
        self.load_shaders()

    # # Uniforms

    def set_uniform(self, name: str, value: Any=None) -> None:
        # Note: Denum safety, called hundreds of times: No noticeable performance impact (?)
        if (value is not None) and (uniform := self.program.get(name, None)):
            uniform.value = denum(value)

    def get_uniform(self, name: str) -> Any | None:
        return self.program.get(name, None)

    # # Rendering

    def dump_shaders(self, error: str=""):
        import rich
        directory = Broken.PROJECT.DIRECTORIES.DUMP
        log.error(f"{self.who} Dumping shaders to {directory}")
        (directory/f"{self.uuid}-frag.glsl").write_text(self.fragment)
        (directory/f"{self.uuid}-vert.glsl").write_text(self.vertex)
        (directory/f"{self.uuid}-error.md" ).write_text(error)
        Process(target=functools.partial(
            rich.print, self, file=(directory/f"{self.uuid}-module.prop").open("w")
        )).start()

    def _full_pipeline(self) -> Iterable[ShaderVariable]:
        for module in self.scene.modules:
            yield from module.pipeline()

    def load_shaders(self, _vertex: str=None, _fragment: str=None) -> Self:
        log.info(f"{self.who} Reloading shaders")

        # Add pipeline variable definitions
        for variable in self._full_pipeline():
            self.common_variable(variable)

        try:
            self.program = self.scene.opengl.program(
                _vertex or self.vertex,
                _fragment or self.fragment
            )
        except (Exception, UnicodeEncodeError) as error:
            # Fixme: conflict when pipeline updates
            self.dump_shaders(error=str(error))
            log.error(f"{self.who} Error compiling shaders, loading missing texture shader")
            return self
            self.load_shaders(
                _vertex   = LoaderString(SHADERFLOW.RESOURCES.VERTEX/"Default.glsl"),
                _fragment = LoaderString(SHADERFLOW.RESOURCES.FRAGMENT/"Missing.glsl")
            )

            if (_vertex or _fragment):
                raise RuntimeError(log.error("Recursion on Shader Loading"))

        # Render the vertices that are defined on the shader
        self.vbo = self.scene.opengl.buffer(numpy.array(self.vertices, dtype="f4"))
        self.vao = self.scene.opengl.vertex_array(
            self.program, [(self.vbo, *self.vao_definition)],
            skip_errors=True
        )

        return self

    # # Module

    def update(self) -> None:
        if not self.program:
            self.load_shaders()
        self.render()

    def render_fbo(self, fbo: moderngl.Framebuffer) -> None:
        fbo.use()
        if self.clear:
            fbo.clear()
        self.vao.render(
            moderngl.TRIANGLE_STRIP,
            instances=self.instances
        )

    def render(self) -> None:

        for index, variable in enumerate(self._full_pipeline()):
            # if variable not in self.fragment_variables:
            #     self.load_shaders()
            if (variable.type == "sampler2D"):
                self.set_uniform(variable.name, index)
                variable.value.use(index)
                continue

            # Optimization: Final shader doesn't need the full pipeline
            if self.texture.final:
                continue

            self.set_uniform(variable.name, variable.value)

        if self.texture.final:
            self.render_fbo(self.texture.fbo())
            return

        for layer, container in enumerate(self.texture.matrix[0]):
            self.set_uniform("iLayer", layer)
            self.render_fbo(container.fbo)

        self.texture.roll()

    def handle(self, message: Message) -> None:
        if isinstance(message, Message.Shader.ReloadShaders):
            self.load_shaders()
        elif isinstance(message, Message.Shader.Render):
            self.render()

            # Fixme: Should this be on a proper User Interface class?
            if self.texture.final:
                self.scene._render_ui()

    def __ui__(self) -> None:
        if imgui.button("Reload"):
            self.load_shaders()
        imgui.same_line()
        if imgui.button("Dump"):
            self.dump_shaders()
        if imgui.tree_node("Pipeline"):
            for variable in self._full_pipeline():
                imgui.text(f"{variable.name.ljust(16)}: {variable.value}")
            imgui.tree_pop()
