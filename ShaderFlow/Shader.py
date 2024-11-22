from __future__ import annotations

import contextlib
import errno
import itertools
import os
import re
from pathlib import Path
from textwrap import dedent
from typing import Any, Iterable, List, Optional, Self, Tuple, Union

import _moderngl
import moderngl
import numpy
from attr import Factory, define
from ordered_set import OrderedSet
from watchdog.observers import Observer

import Broken
from Broken import BrokenPath, denum
from Broken.Loaders import LoadableString, LoaderString
from ShaderFlow import SHADERFLOW
from ShaderFlow.Imgui import imgui
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Texture import ShaderTexture
from ShaderFlow.Variable import FlatVariable, InVariable, OutVariable, ShaderVariable

WATCHDOG = Observer()
WATCHDOG.start()

@define
class ShaderDumper:
    shader: ShaderProgram # Fixme: Extending a parent class with refactored functionality
    """Parent ShaderObject instance"""

    error: str
    """str(_moderngl.Error) exception"""

    fragment: str
    """Potentially faulty Fragment shader"""

    vertex: str
    """Potentially faulty Vertex shader"""

    context: int = 5
    """Number of lines to show before and after the faulty line"""

    _parser = re.compile(r"^0\((\d+)\)\s*:\s*error\s* (\w+):\s(.*)", re.MULTILINE)

    @property
    def code(self) -> str:
        """Simple heuristic to choose what shader cause the error"""
        if ("fragment_shader" in self.error):
            return self.fragment
        elif ("vertex_shader" in self.error):
            return self.vertex
        raise RuntimeError(f"Cannot determine shader from error: {self.error}")

    @property
    def lines(self) -> List[str]:
        return self.code.splitlines()

    def dump(self):
        directory = Broken.PROJECT.DIRECTORIES.DUMP
        self.shader.log_error(f"Dumping shaders to {directory}")
        (directory/f"{self.shader.uuid}.frag").write_text(self.fragment, encoding="utf-8")
        (directory/f"{self.shader.uuid}.vert").write_text(self.vertex, encoding="utf-8")
        (directory/f"{self.shader.uuid}-error.md" ).write_text(self.error, encoding="utf-8")

        import rich
        from rich.panel import Panel
        from rich.syntax import Syntax

        # Visual only: Print highlighted code panels of all errors
        for match in ShaderDumper._parser.finditer(self.error):
            lineno, errno, message = match.groups()
            lineno = int(lineno)
            start  = max(0, lineno - self.context - 1)
            end    = min(len(self.lines), lineno + self.context)
            code   = []

            for i, line in enumerate(self.lines[start:end]):
                div = (">" if (i == lineno) else "|")
                code.append(f"({i+start+1:3d}) {div} {line}")

            rich.print(Panel(
                Syntax(code='\n'.join(code), lexer="glsl"),
                title=f"({errno} at Module #{self.shader.uuid}, Line {lineno}): {message}",
            ))

@define
class ShaderProgram(ShaderModule):
    version: int = 330
    """OpenGL Version to use for the shader. Must be <= than the Window Backend version"""

    clear: bool = False
    """Clear the Final Texture before rendering"""

    instances: int = 1
    """Number of gl_InstanceID's to render per render pass"""

    texture: ShaderTexture = None
    """ShaderTexture Module that this Shader renders to in layers and temporal"""

    def build(self):
        self.texture = ShaderTexture(scene=self.scene, name=self.name, track=True)
        self.fragment_variable(OutVariable("vec4", "fragColor"))
        self.vertex_variable(InVariable("vec2", "vertex_position"))
        self.vertex_variable(InVariable("vec2", "vertex_gluv"))
        self.passthrough(ShaderVariable("vec2", "fragCoord"))
        self.passthrough(ShaderVariable("vec2", "stxy"))
        self.passthrough(ShaderVariable("vec2", "glxy"))
        self.passthrough(ShaderVariable("vec2", "stuv"))
        self.passthrough(ShaderVariable("vec2", "astuv"))
        self.passthrough(ShaderVariable("vec2", "gluv"))
        self.passthrough(ShaderVariable("vec2", "agluv"))
        self.passthrough(FlatVariable("int", "instance"))

        # Add a fullscreen center-(0, 0) uv rectangle
        for x, y in itertools.product((-1, 1), (-1, 1)):
            self.add_vertice(x=x, y=y, u=x, v=y)

        # Load default vertex and fragment shaders
        self.vertex   = (SHADERFLOW.RESOURCES.VERTEX/"Default.glsl")
        self.fragment = (SHADERFLOW.RESOURCES.FRAGMENT/"Default.glsl")

    # # Variable handling

    vertex_variables: OrderedSet = Factory(OrderedSet)
    """Variables metaprogramming that will be added to the Vertex Shader"""

    fragment_variables: OrderedSet = Factory(OrderedSet)
    """Variables metaprogramming that will be added to the Fragment Shader"""

    def vertex_variable(self, variable: ShaderVariable) -> None:
        self.vertex_variables.add(variable)

    def fragment_variable(self, variable: ShaderVariable) -> None:
        self.fragment_variables.add(variable)

    def common_variable(self, variable: ShaderVariable) -> None:
        self.vertex_variable(variable)
        self.fragment_variable(variable)

    def passthrough(self, variable: ShaderVariable) -> None:
        self.vertex_variable(variable.copy(direction="out"))
        self.fragment_variable(variable.copy(direction="in"))

    # # Vertices

    vertices: List[float] = Factory(list)
    """Vertices of the shader. More often than not, a Fullscreen Quad"""

    vbo: moderngl.Buffer = None
    """Buffer object for the vertices of the shader"""

    vao: moderngl.VertexArray = None
    """State object for the 'rendering' of the shader"""

    def add_vertice(self, x: float=0, y: float=0, u: float=0, v: float=0) -> None:
        self.vertices.extend((x, y, u, v))

    @property
    def vao_definition(self) -> Tuple[str]:
        """Outputs: ("2f 2f", "render_vertex", "coords_vertex")"""
        sizes, names = [], []
        for variable in self.vertex_variables:
            if variable.direction == "in":
                sizes.append(variable.size_string)
                names.append(variable.name)
        return (" ".join(sizes), *names)

    # # Metaprogramming

    _include_regex = re.compile(r'^\s*#include\s+"(.+)"\s*$', re.MULTILINE)
    """Finds all whole lines `#include "file"` directives in the shader"""

    def _build_shader(self,
        content: LoadableString,
        variables: Iterable[ShaderVariable],
        *, _type: str
    ) -> str:
        """Build the final shader from the contents provided"""
        separator: str = ("// " + "-"*96 + "|\n")
        code: List[LoadableString] = list()

        @contextlib.contextmanager
        def section(name: str=""):
            code.append(f"\n\n{separator}")
            code.append(f"// Metaprogramming ({name})\n")
            yield None

        # Must define version first; fixed headers
        code.append(f"#version {self.version}")
        code.append(f"#define {_type}")

        with section("Variables"):
            code.extend(item.declaration for item in variables)

        # Fixme: Inject defines after content includes; deprecate this
        with section("Include - ShaderFlow"):
            code.append(SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"ShaderFlow.glsl")

        # Add all modules includes to the shader
        for module in self.scene.modules:
            for defines in module.defines():
                code.append(defines)

            for include in filter(None, module.includes()):
                with section(f"Include - {module.__class__.__name__}@{module.uuid}"):
                    code.append(include)

        # Add shader content itself
        with section("Content"):
            code.append(content)

        # Join all parts for includes post-processing
        code: str = '\n'.join(map(LoaderString, code))

        # Solve includes recursively until no more are found
        while (match := ShaderProgram._include_regex.search(code)):
            replaces, include = match.group(0), match.group(1)

            # Optimization: Skip already included to avoid clutter
            if (tag := f"// Include - {include}") in code:
                code = code.replace(replaces, "")
                continue

            # Note: Breaks to guarantee order of includes
            for directory in self.include_directories:
                if (path := next(directory.rglob(include))):
                    code = code.replace(replaces, dedent(f"""
                        {separator}{tag}{separator}
                        {path.read_text("utf-8")}
                    """))
                    self._watchshader(path)
                    break
            else:
                raise FileNotFoundError(f"Include file {include} not found in include directories")

        return code

    # # Hot reloading

    include_directories: OrderedSet[Path] = Factory(lambda: OrderedSet((
        SHADERFLOW.RESOURCES.SHADERS,
    )))

    def _watchshader(self, path: Path) -> Any:
        from watchdog.events import FileSystemEventHandler

        @define(eq=False)
        class Handler(FileSystemEventHandler):
            shader: ShaderProgram
            def on_modified(self, event):
                if (not self.shader.scene.freewheel):
                    self.shader.scene.scheduler.once(self.shader.compile)

        # Add the Shader Path to the watchdog for changes. Only ignore 'File Too Long'
        # exceptions when non-path strings as we can't get max len easily per system
        try:
            if (path := BrokenPath.get(path)).exists():
                WATCHDOG.schedule(Handler(self), path)
        except OSError as error:
            if error.errno != errno.ENAMETOOLONG:
                raise error

        return path

    # # Vertex shader

    _vertex: Union[Path, str] = ""
    """The 'User Content' of the Vertex Shader, interted after the Metaprogramming.
    A Path value will be watched for changes and shaders will be automatically reloaded"""

    def make_vertex(self, content: str) -> Self:
        return self._build_shader(
            content=LoaderString(content),
            variables=self.vertex_variables,
            _type="VERTEX"
        )

    @property
    def vertex(self) -> str:
        return self.make_vertex(self._vertex)

    @vertex.setter
    def vertex(self, value: Union[Path, str]):
        self._watchshader(value)
        self._vertex = value

    # # Fragment shader

    _fragment: Union[Path, str] = ""
    """The 'User Content' of the Fragment Shader, interted after the Metaprogramming.
    A Path value will be watched for changes and shaders will be automatically reloaded"""

    def make_fragment(self, content: str) -> Self:
        return self._build_shader(
            content=LoaderString(content),
            variables=self.fragment_variables,
            _type="FRAGMENT"
        )

    @property
    def fragment(self) -> str:
        return self.make_fragment(self._fragment)

    @fragment.setter
    def fragment(self, value: Union[Path, str]):
        self._watchshader(value)
        self._fragment = value

    # # Rendering

    program: moderngl.Program = None
    """ModernGL 'Compiled Shaders' object"""

    def compile(self, _vertex: str=None, _fragment: str=None) -> Self:
        self.log_info("Compiling shaders")

        # Add pipeline variable definitions
        for variable in self.full_pipeline():
            self.common_variable(variable)

        # Metaprogram either injected or proper shaders
        fragment = self.make_fragment(_fragment or self._fragment)
        vertex = self.make_vertex(_vertex or self._vertex)

        try:
            self.program = self.scene.opengl.program(vertex, fragment)
        except _moderngl.Error as error:
            ShaderDumper(
                shader=self,
                error=str(error),
                vertex=vertex,
                fragment=fragment
            ).dump()

            if (_vertex or _fragment):
                raise RuntimeError(self.log_error("Recursion on Missing Texture Shader Loading"))

            self.log_error("Error compiling shaders, loading missing texture shader")
            self.compile(
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

    # # Uniforms

    def set_uniform(self, name: str, value: Any=None) -> None:
        if (self.program is None):
            raise RuntimeError(self.log_error("Shader hasn't been compiled yet"))
        if (value is not None) and (uniform := self.program.get(name, None)):
            uniform.value = denum(value)

    def get_uniform(self, name: str) -> Optional[Any]:
        return self.program.get(name, None)

    # # Module

    SKIP_GPU: bool = (os.getenv("SKIP_GPU", "0") == "1")
    """Do not render shaders, useful for benchmarking raw Python performance"""

    def render_to_fbo(self, fbo: moderngl.Framebuffer, clear: bool=True) -> None:
        if self.SKIP_GPU:
            return
        fbo.use()
        clear or fbo.clear()
        self.vao.render(
            moderngl.TRIANGLE_STRIP,
            instances=self.instances
        )

    def use_pipeline(self, pipeline: Iterable[ShaderVariable], *, _index: int=0) -> None:
        for variable in pipeline:
            # if variable not in self.fragment_variables:
            #     self.load_shaders()
            if (variable.type == "sampler2D"):
                self.set_uniform(variable.name, _index)
                variable.value.use(_index)
                _index += 1
                continue
            self.set_uniform(variable.name, variable.value)

    def render(self) -> None:

        # Optimization: Final shader doesn't need the full pipeline
        if self.texture.final:
            self.use_pipeline(self.scene.shader.texture.pipeline())
            self.render_to_fbo(self.texture.fbo, clear=False)
            return None

        self.use_pipeline(self.full_pipeline())

        # Optimization: Only the iLayer uniform changes
        for layer, box in enumerate(self.texture.row(0)):
            self.set_uniform("iLayer", layer)
            self.render_to_fbo(fbo=box.fbo, clear=box.clear)

        self.texture.roll()

    def update(self) -> None:
        self.render()

    def handle(self, message: ShaderMessage) -> None:
        if isinstance(message, ShaderMessage.Shader.Compile):
            self.compile()
        elif isinstance(message, ShaderMessage.Shader.Render):
            self.render()

    def __ui__(self) -> None:
        if imgui.button("Reload"):
            self.compile()
        imgui.same_line()
        if imgui.button("Dump"):
            self.dump_shaders()
        if imgui.tree_node("Pipeline"):
            for variable in self.full_pipeline():
                imgui.text(f"{variable.name.ljust(16)}: {variable.value}")
            imgui.tree_pop()
