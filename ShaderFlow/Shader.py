import contextlib
import errno
import itertools
from pathlib import Path
from typing import Any, Iterable, List, Self, Set, Tuple, Union

import imgui
import moderngl
import numpy
import watchdog
import watchdog.observers
from attr import Factory, define
from loguru import logger as log

import Broken
from Broken import BrokenPath, denum
from Broken.Loaders import LoaderString
from ShaderFlow import SHADERFLOW
from ShaderFlow.Message import Message
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Texture import ShaderTexture
from ShaderFlow.Variable import ShaderVariable, ShaderVariableDirection

WATCHDOG = watchdog.observers.Observer()
WATCHDOG.start()

@define
class ShaderObject(ShaderModule):
    version: int = 330
    """OpenGL Version to use for the shader. Must be <= than the Window Backend version."""

    program: moderngl.Program = None
    """ModernGL 'Compiled Shaders' object"""

    vao: moderngl.VertexArray = None
    """Buffer object for the vertices of the shader"""

    vbo: moderngl.Buffer = None
    """Buffer object for the vertices of the shader"""

    texture: ShaderTexture = None
    """ShaderTexture Module that this Shader renders to in layers and temporal"""

    clear: bool = False
    """Clear the Final Texture before rendering"""

    instances: int = 1
    """Number of gl_InstanceIDs to render"""

    vertices: List[float] = Factory(list)
    """Vertices of the shader. More often than not a Fullscreen Quad"""

    vertex_variables: Set[ShaderVariable] = Factory(set)
    """Variables metaprogramming that will be added to the Vertex Shader"""

    fragment_variables: Set[ShaderVariable] = Factory(set)
    """Variables metaprogramming that will be added to the Fragment Shader"""

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
        self.vertex   = (SHADERFLOW.RESOURCES.VERTEX/  "Default.glsl")
        self.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Default.glsl")

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

    def _watchshader(self, path: Path) -> None:

        @define(eq=False)
        class Handler(watchdog.events.FileSystemEventHandler):
            shader: ShaderObject
            def on_modified(self, event):
                if self.shader.scene.rendering:
                    return
                self.shader.scene.scheduler.once(self.shader.load_shaders)

        # Add the Shader Path to the watchdog for changes. Only ignore 'File Too Long'
        # exceptions when non-path strings as we can't get max len easily per system
        try:
            if (path := BrokenPath(path).valid()):
                WATCHDOG.schedule(Handler(self), path)
        except OSError as error:
            if error.errno != errno.ENAMETOOLONG:
                raise error

    _vertex: Union[Path, str] = ""
    """The 'User Content' of the Vertex Shader, interted after the Metaprogramming.
    A Path value will be watched for changes and shaders will be automatically reloaded"""

    def make_vertex(self, content: str) -> Self:
        return self._build_shader(LoaderString(content), self.vertex_variables)

    @property
    def vertex(self) -> str:
        return self.make_vertex(self._vertex)

    @vertex.setter
    def vertex(self, value: Union[Path, str]) -> None:
        self._watchshader(value)
        self._vertex = value

    # # Fragment shader content

    _fragment: Union[Path, str] = ""
    """The 'User Content' of the Fragment Shader, interted after the Metaprogramming.
    A Path value will be watched for changes and shaders will be automatically reloaded"""

    def make_fragment(self, content: str) -> Self:
        return self._build_shader(LoaderString(content), self.fragment_variables)

    @property
    def fragment(self) -> str:
        return self.make_fragment(self._fragment)

    @fragment.setter
    def fragment(self, value: Union[Path, str]) -> None:
        self._watchshader(value)
        self._fragment = value

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
        (directory/f"{self.uuid}-frag.glsl").write_text(self.fragment, encoding="utf-8")
        (directory/f"{self.uuid}-vert.glsl").write_text(self.vertex, encoding="utf-8")
        (directory/f"{self.uuid}-error.md" ).write_text(error, encoding="utf-8")
        # Process(target=functools.partial(
        #     rich.print, self, file=(directory/f"{self.uuid}-module.prop").open("w", encoding="utf-8")
        # )).start()

    def _full_pipeline(self) -> Iterable[ShaderVariable]:
        for module in self.scene.modules:
            yield from module.pipeline()

    def load_shaders(self, _vertex: str=None, _fragment: str=None) -> Self:
        log.info(f"{self.who} Compiling shaders")

        # Add pipeline variable definitions
        for variable in self._full_pipeline():
            self.common_variable(variable)

        try:
            self.program = self.scene.opengl.program(
                self.make_vertex(_vertex or self._vertex),
                self.make_fragment(_fragment or self._fragment)
            )
        except Exception as error:
            if (_vertex or _fragment):
                raise RuntimeError(log.error("Recursion on Missing Texture Shader Loading"))

            log.error(f"{self.who} Error compiling shaders, loading missing texture shader")
            self.dump_shaders(error=str(error))
            self.load_shaders(
                _vertex  =LoaderString(SHADERFLOW.RESOURCES.VERTEX/"Default.glsl"),
                _fragment=LoaderString(SHADERFLOW.RESOURCES.FRAGMENT/"Missing.glsl")
            )

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

    def render_fbo(self, fbo: moderngl.Framebuffer, clear: bool=True) -> None:
        fbo.use()
        if clear:
            fbo.clear()
        self.vao.render(
            moderngl.TRIANGLE_STRIP,
            instances=self.instances
        )

    def use_pipeline(self, pipeline: Iterable[ShaderVariable]) -> None:
        for index, variable in enumerate(pipeline):
            # if variable not in self.fragment_variables:
            #     self.load_shaders()
            if (variable.type == "sampler2D"):
                self.set_uniform(variable.name, index)
                variable.value.use(index)
                continue

            self.set_uniform(variable.name, variable.value)

    def render(self) -> None:

        # Optimization: Final shader doesn't need the full pipeline
        if self.texture.final:
            self.use_pipeline(self.scene.shader.texture.pipeline())
            self.render_fbo(self.texture.fbo(), clear=self.clear)
            return

        self.use_pipeline(self._full_pipeline())

        for layer, container in enumerate(self.texture.matrix[0]):
            self.set_uniform("iLayer", layer)
            self.render_fbo(fbo=container.fbo, clear=container.clear)

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
