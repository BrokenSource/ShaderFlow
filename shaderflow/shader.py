from __future__ import annotations

import contextlib
import errno
import itertools
import os
import re
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional, Self, Union

import _moderngl
import moderngl
import numpy as np
from attrs import Factory, define
from imgui_bundle import imgui
from ordered_set import OrderedSet
from watchdog.observers import Observer

import shaderflow
from shaderflow import logger
from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.texture import ShaderTexture
from shaderflow.variable import (
    FlatVariable,
    InVariable,
    OutVariable,
    ShaderVariable,
)

# Shared watchdog instance
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
    def lines(self) -> list[str]:
        return self.code.splitlines()

    def dump(self):
        directory = shaderflow.directories.user_log_path
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
                div = (">" if (i+start+1 == lineno) else "|")
                code.append(f"({i+start+1:3d}) {div} {line}")

            rich.print(Panel(
                Syntax(code='\n'.join(code), lexer="glsl"),
                title=f"({errno} at Module #{self.shader.uuid}, Line {lineno}): {message}",
            ))
            break

@define
class ShaderProgram(ShaderModule):
    version: int = 330
    """OpenGL Version to use for the shader"""

    clear: bool = True
    """Clear the final texture before rendering"""

    instances: int = 1
    """Number of gl_InstanceID's to render per render pass"""

    texture: ShaderTexture = None
    """ShaderTexture Module that this Shader renders to in layers and temporal"""

    def build(self):
        self.texture = ShaderTexture(scene=self.scene, name=self.name, track=True)
        self.fragment_variable(OutVariable("vec4", "fragColor"))
        self.vertex_variable(InVariable("vec2", "vertex_position"))
        self.vertex_variable(InVariable("vec2", "vertex_gluv"))
        self.traverse_variable(ShaderVariable("vec2", "fragCoord"))
        self.traverse_variable(ShaderVariable("vec2", "stxy"))
        self.traverse_variable(ShaderVariable("vec2", "glxy"))
        self.traverse_variable(ShaderVariable("vec2", "stuv"))
        self.traverse_variable(ShaderVariable("vec2", "astuv"))
        self.traverse_variable(ShaderVariable("vec2", "gluv"))
        self.traverse_variable(ShaderVariable("vec2", "agluv"))
        self.traverse_variable(FlatVariable("int", "instance"))

        # Add a fullscreen center-(0, 0) uv rectangle
        for x, y in itertools.product((-1, 1), (-1, 1)):
            self.add_vertice(x=x, y=y, u=x, v=y)

        # Load default vertex and fragment shaders
        self.vertex   = (shaderflow.resources/"shaders"/"vertex"/"default.glsl")
        self.fragment = (shaderflow.resources/"shaders"/"fragment"/"default.glsl")

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
        self.fragment_variable(variable)
        self.vertex_variable(variable)

    def traverse_variable(self, variable: ShaderVariable) -> None:
        self.fragment_variable(variable.copy(direction="in"))
        self.vertex_variable(variable.copy(direction="out"))

    # # Vertices

    vertices: list[float] = Factory(list)
    """Vertices of the shader. More often than not, a Fullscreen Quad"""

    vbo: moderngl.Buffer = None
    """Buffer object for the vertices of the shader"""

    vao: moderngl.VertexArray = None
    """State object for the 'rendering' of the shader"""

    def add_vertice(self, x: float=0, y: float=0, u: float=0, v: float=0) -> None:
        self.vertices.extend((x, y, u, v))

    @property
    def vao_definition(self) -> tuple[str]:
        """Outputs: ("2f 2f", "render_vertex", "coords_vertex")"""
        sizes, names = [], []
        for variable in self.vertex_variables:
            if variable.direction == "in":
                sizes.append(variable.size_string)
                names.append(variable.name)
        return (" ".join(sizes), *names)

    # # Metaprogramming

    include_directories: OrderedSet[Path] = Factory(lambda: OrderedSet((
        (shaderflow.resources/"shaders"),
    )))

    _include_regex = re.compile(r'^\s*#include\s+"(.+)"\s*$', re.MULTILINE)
    """Finds all whole lines `#include "file"` directives in the shader"""

    # Todo: Overhaul metaprogramming (includes, defines, unspaghetti)
    def _build_shader(self,
        content: str,
        variables: Iterable[ShaderVariable],
        *, _type: str
    ) -> str:
        """Build the final shader from the contents provided"""
        separator: str = ("// " + "-"*96 + "|\n")
        code: deque[str] = deque()

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
            code.append((shaderflow.resources/"shaders"/"include"/"shaderflow.glsl").read_text())

        # Add all modules includes to the shader
        for module in self.scene.modules:
            for defines in module.defines():
                code.append(defines)

            for include in filter(None, module.includes()):
                with section(f"Include - {type(module).__name__}@{module.uuid}"):
                    if isinstance(include, Path):
                        code.append(include.read_text())
                    else:
                        code.append(include)

        # Add shader content itself
        with section("Content"):
            if isinstance(content, Path):
                code.append(content.read_text())
                self._watchshader(content)
            else:
                code.append(str(content))

        # Join all parts for includes post-processing
        code: str = '\n'.join(filter(None, code))

        return code

    # # Hot reloading

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
            if (path := Path(path)).exists():
                WATCHDOG.schedule(Handler(self), path)
        except OSError as error:
            if error.errno != errno.ENAMETOOLONG:
                raise error

        return path

    # # Vertex shader

    _vertex: Union[Path, str] = ""
    """The 'User Content' of the Vertex Shader, interted after the Metaprogramming.
    A Path value will be watched for changes and shaders will be automatically reloaded"""

    def make_vertex(self, content: str) -> str:
        return self._build_shader(
            content=content,
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

    def make_fragment(self, content: str) -> str:
        return self._build_shader(
            content=content,
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
                raise RuntimeError("Recursion on Missing Texture Shader Loading")

            logger.error("Error compiling shaders, loading missing texture shader")
            self.compile(
                _vertex  =(shaderflow.resources/"shaders"/"vertex"/"default.glsl").read_text(),
                _fragment=(shaderflow.resources/"shaders"/"fragment"/"missing.glsl").read_text()
            )

        # Render the vertices that are defined on the shader
        self.vbo = self.scene.opengl.buffer(np.array(self.vertices, dtype="f4"))
        self.vao = self.scene.opengl.vertex_array(
            self.program, [(self.vbo, *self.vao_definition)],
            skip_errors=True
        )

        return self

    # # Uniforms

    def set_uniform(self, name: str, value: Any=None) -> None:
        if (self.program is None):
            raise RuntimeError("Shader hasn't been compiled yet")
        if (value is not None) and (uniform := self.program.get(name, None)):
            uniform.value = value

    def get_uniform(self, name: str) -> Optional[Any]:
        return self.program.get(name, None)

    # # Module

    SKIP_GPU: bool = os.environ.get("SKIP_GPU") == "1"
    """Do not render shaders, useful for benchmarking raw Python performance"""

    def render_to_fbo(self, fbo: moderngl.Framebuffer, clear: bool=True) -> None:
        if self.SKIP_GPU:
            return
        fbo.use()
        if clear: fbo.clear()
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
            self.set_uniform("iResolution", self.scene.resolution)
            self.set_uniform("iSubsample",  self.scene.subsample)
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
