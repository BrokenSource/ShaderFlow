from __future__ import annotations

from . import *


@define
class SombreroEngine(SombreroModule):
    version:            str                  = "330"
    program:            moderngl.Program     = None
    __texture__:        moderngl.Texture     = None
    __fbo__:            moderngl.Framebuffer = None
    vao:                moderngl.VertexArray = None
    vbo:                moderngl.Buffer      = None
    clear:              bool                 = False
    final:              bool                 = False
    instances:          int                  = 1
    vertices:           List[float]          = Factory(list)
    vertex_variables:   set[ShaderVariable]  = Factory(set)
    fragment_variables: set[ShaderVariable]  = Factory(set)

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
        self.vertex_variable(variable(direction="out").copy())
        self.fragment_variable(variable(direction="in").copy())

    @property
    def vao_definition(self) -> Tuple[str]:
        """("2f 2f", "render_vertex", "coords_vertex")"""
        sizes, names = [], []
        for variable in self.vertex_variables:
            if variable.direction == ShaderVariableDirection.In.value:
                sizes.append(variable.size_string)
                names.append(variable.name)
        return (" ".join(sizes), *names)

    def __attrs_post_init__(self):
        """Set default values for some variables"""
        self.fragment_variable("out vec4 fragColor")
        self.vertex_variable("in vec2 vertex_position")
        self.vertex_variable("in vec2 vertex_gluv")
        self.vertex_io("flat int instance")
        self.vertex_io("vec2 gluv")
        self.vertex_io("vec2 stuv")
        self.vertex_io("vec2 astuv")
        self.vertex_io("vec2 agluv")

        # Add a fullscreen center-(0, 0) uv rectangle
        for x, y in itertools.product((-1, 1), (-1, 1)):
            self.add_vertice(x=x, y=y, u=x, v=y)

        # Load default vertex and fragment shaders
        self.__vertex__   = LoaderString(SHADERFLOW.RESOURCES.VERTEX/  "Default.glsl")
        self.__fragment__ = LoaderString(SHADERFLOW.RESOURCES.FRAGMENT/"Default.glsl")

    def __build_shader__(self, content: str, variables: Iterable[ShaderVariable]) -> str:
        """Build the final shader from the contents provided"""
        shader = []

        @contextmanager
        def section(name: str=""):
            shader.append("\n\n// " + "-"*96 + "|")
            shader.append(f"// Sombrero Section: ({name})\n")
            yield

        shader.append(f"#version {self.version}")

        # Add variable definitions
        with section("Variables"):
            for variable in variables:
                shader.append(variable.declaration)

        with section(f"Include - Sombrero"):
            shader.append(SHADERFLOW.RESOURCES.SHADERS_INCLUDE/"Sombrero.glsl")

        # Add all modules includes to the shader
        for module in self.scene.modules:
            for include in filter(None, module.includes()):
                with section(f"Include - {module.who}"):
                    shader.append(include)

        # Add shader content itself
        with section("Content"):
            shader.append(content)

        return '\n'.join(map(LoaderString, shader))

    # # Vertex shader content

    __vertex__: str = ""

    @property
    def vertex(self) -> str:
        return self.__build_shader__(self.__vertex__, self.vertex_variables)

    @vertex.setter
    def vertex(self, value: str) -> None:
        self.__vertex__ = LoaderString(value)
        self.load_shaders()

    # # Fragment shader content

    __fragment__: str = ""

    @property
    def fragment(self) -> str:
        return self.__build_shader__(self.__fragment__, self.fragment_variables)

    @fragment.setter
    def fragment(self, value: str) -> None:
        self.__fragment__ = LoaderString(value)
        self.load_shaders()

    # # Texture

    @property
    def texture(self) -> moderngl.Texture:
        if not self.__texture__:
            self.create_texture_fbo()
        return self.__texture__

    @texture.setter
    def texture(self, value: moderngl.Texture) -> None:
        self.__texture__ = value

    def create_texture_fbo(self):
        # Recreate the Headless window FBO, as it doesn't answer to self.window.size
        if self.final:
            return

        # Release the old objects
        if self.__texture__:
            self.__texture__.release()
        if self.__fbo__:
            self.__fbo__.release()

        # Create new ones
        self.texture = self.scene.opengl.texture(size=self.scene.render_resolution, components=4)
        self.fbo     = self.scene.opengl.framebuffer(color_attachments=[self.texture])

    # # Frame buffer object

    @property
    def fbo(self) -> moderngl.Framebuffer:
        if self.final:
            return self.scene.window.fbo
        if not self.__fbo__:
            self.create_texture_fbo()
        return self.__fbo__

    @fbo.setter
    def fbo(self, value: moderngl.Framebuffer) -> None:
        if self.final:
            return
        self.__fbo__ = value

    # # Uniforms

    def set_uniform(self, name: str, value: Any=None) -> None:
        """Send an uniform to the shader by name and value"""
        # Note: Denum safety, called hundreds of times: No noticeable performance impact (?)
        if (value is not None) and (uniform := self.program.get(name, None)):
            uniform.value = BrokenUtils.denum(value)

    def get_uniform(self, name: str) -> Any | None:
        """Get a uniform from the shader by name"""
        return self.program.get(name, None)

    # # Rendering

    def dump_shaders(self, error: str=""):
        import rich
        log.action(f"{self.who} Dumping shaders to {SHADERFLOW.DIRECTORIES.DUMP}")
        (SHADERFLOW.DIRECTORIES.DUMP/f"{self.uuid}-frag.glsl").write_text(self.fragment)
        (SHADERFLOW.DIRECTORIES.DUMP/f"{self.uuid}-vert.glsl").write_text(self.vertex)
        (SHADERFLOW.DIRECTORIES.DUMP/f"{self.uuid}-error.md" ).write_text(error)
        multiprocessing.Process(target=functools.partial(rich.print, self, file=(SHADERFLOW.DIRECTORIES.DUMP/f"{self.uuid}-module.prop").open("w"))).start()

    def load_shaders(self) -> Self:
        """Reload the shaders after some change of variables or content"""
        log.debug(f"{self.who} Reloading shaders")

        # Add pipeline variable definitions
        for variable in self.__modules_pipeline__():
            self.common_variable(variable)

        try:
            # Create the Moderngl Program - Compile shaders
            self.program = self.scene.opengl.program(
                fragment_shader=self.fragment,
                vertex_shader=self.vertex,
            )

        # On shader compile error - Load missing texture, dump faulty shaders
        except Exception as error:
            self.dump_shaders(error=str(error))
            log.error(f"{self.who} Error compiling shaders, loading missing texture shader")
            self.fragment = LoaderString(SHADERFLOW.RESOURCES.FRAGMENT/"Missing.glsl")
            self.vertex   = LoaderString(SHADERFLOW.RESOURCES.VERTEX/"Default.glsl")

        # Render the vertices that are defined on the shader
        self.vbo = self.scene.opengl.buffer(numpy.array(self.vertices, dtype="f4"))

        # Create the Vertex Array Object
        self.vao = self.scene.opengl.vertex_array(
            self.program, [(self.vbo, *self.vao_definition)],
            skip_errors=True
        )

        return self

    # # Textures

    def new_texture(self, *args, **kwargs) -> SombreroTexture:
        return self.add(SombreroTexture(*args, **kwargs))

    # # SombreroModule

    def __ui__(self) -> None:
        if imgui.button("Reload"):
            self.load_shaders()
        imgui.same_line()
        if imgui.button("Dump"):
            self.dump_shaders()

        if imgui.tree_node("Pipeline"):
            for variable in self.__modules_pipeline__():
                imgui.text(f"{variable.name.ljust(16)}: {variable.value}")
            imgui.tree_pop()

    def __modules_pipeline__(self) -> Iterable[ShaderVariable]:
        for module in self.scene.modules:
            yield from module._pipeline()

    def __update__(self) -> None:
        if not self.program:
            self.load_shaders()
        self.render()

    def render(self) -> None:

        # Set and use textures at some index
        for index, module in enumerate(self.find(SombreroTexture)):
            module.texture.use(index)
            module.index = index

        # Optimization: Final shader doesn't need uniforms
        if not self.final:
            for variable in self.__modules_pipeline__():
                self.set_uniform(variable.name, variable.value)

        # Set render target
        self.fbo.use()

        # Some performance improvement in not clearing
        if self.clear:
            self.fbo.clear()

        # Render the shader
        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.instances)

    def __handle__(self, message: SombreroMessage) -> None:
        if isinstance(message, SombreroMessage.Window.Resize):
            self.create_texture_fbo()
            if self.final:
                self.fbo.viewport = (0, 0, message.width, message.height)

        if isinstance(message, SombreroMessage.Engine.RecreateTextures):
            self.create_texture_fbo()

        if isinstance(message, SombreroMessage.Engine.ReloadShaders):
            self.load_shaders()

        if isinstance(message, SombreroMessage.Engine.Render):
            self.render()
