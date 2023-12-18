from . import *


@attrs.define
class SombreroEngine(SombreroModule):
    shader: SombreroShader = attrs.field(factory=SombreroShader)
    textures: dict[SombreroTexture] = attrs.field(factory=dict)

    # ModernGL attributes
    program:          moderngl.Program     = None
    __texture__:      moderngl.Texture     = None
    __fbo__:          moderngl.Framebuffer = None
    vao:              moderngl.VertexArray = None
    vbo:              moderngl.Buffer      = None
    clear:            bool                 = True
    instances:        int                  = 1

    # Should this instance render finally to the window
    final:            bool                 = False

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
        # Todo: Talk to ModernGL devs about this, headless to resize its own FBO?
        if self.final:
            self.context.window._fbo = self.context.opengl.framebuffer(
                color_attachments=self.context.opengl.texture(self.context.resolution, 4),
                depth_attachment=self.context.opengl.depth_texture(self.context.resolution),
            )
            return

        # Release the old objects
        if self.__texture__:
            self.__texture__.release()
        if self.__fbo__:
            self.__fbo__.release()

        # Create new ones
        self.texture = self.context.opengl.texture(size=self.context.render_resolution, components=4)
        self.fbo     = self.context.opengl.framebuffer(color_attachments=[self.texture])

    # # Frame buffer object

    @property
    def fbo(self) -> moderngl.Framebuffer:
        if self.final:
            return self.context.window.fbo
        if not self.__fbo__:
            self.create_texture_fbo()
        return self.__fbo__

    @fbo.setter
    def fbo(self, value: moderngl.Framebuffer) -> None:
        if self.final:
            return
        self.__fbo__ = value

    # # Uniforms

    # Fixme: This workaround is needed because of the early .load_shaders
    __UNIFORMS_KNOWN__: Set[str] = attrs.field(factory=set)

    def set_uniform(self, name: str, value: Any) -> None:
        """Send an uniform to the shader by name and value"""
        if (uniform := self.program.get(name, None)) and (value is not None):
            uniform.value = value

        else:
            # Workaround: Early .load_shaders won't have the full modules and pipeline
            # Fixme: This might prompt a lot of shader reloads on the first frame
            if name not in self.__UNIFORMS_KNOWN__:
                log.success(f"{self.who} Found Variable ({name}) on pipeline, reloading shaders")
                self.__UNIFORMS_KNOWN__.add(name)
                self.load_shaders()
                self.set_uniform(name, value)

    def get_uniform(self, name: str) -> Any | None:
        """Get a uniform from the shader by name"""
        return self.program.get(name, None)

    # # Wrap around the shader

    @property
    def fragment(self) -> str:
        return self.shader.fragment

    @fragment.setter
    def fragment(self, value: str) -> None:
        self.load_shaders(fragment=value)

    @property
    def vertex(self) -> str:
        return self.shader.vertex

    @vertex.setter
    def vertex(self, value: str) -> None:
        self.load_shaders(vertex=value)

    # # Rendering

    def dump_shaders(self, error: str=""):
        log.action(f"{self.who} Dumping shaders to {SHADERFLOW.DIRECTORIES.DUMP/self.suuid}")
        (SHADERFLOW.DIRECTORIES.DUMP/f"{self.suuid}.frag").write_text(self.shader.fragment)
        (SHADERFLOW.DIRECTORIES.DUMP/f"{self.suuid}.vert").write_text(self.shader.vertex)
        # rich.print(self, file=(SHADERFLOW.DIRECTORIES.DUMP/f"{self.suuid}.who").open("w"))
        if error:
            (SHADERFLOW.DIRECTORIES.DUMP/f"{self.suuid}.err").write_text(error)

    def load_shaders(self,
        vertex:   str | Path=Unchanged,
        fragment: str | Path=Unchanged,
        _missing: bool=False,
    ) -> Self:
        """Reload the shaders after some change of variables or content"""
        log.info(f"{self.who} Reloading shaders")

        # Load shaders from files if Path instance
        vertex   = vertex.read_text()   if isinstance(vertex, Path)   else vertex
        fragment = fragment.read_text() if isinstance(fragment, Path) else fragment

        # Add pipeline variable definitions
        for module in self.connected:
            for variable in module.pipeline():
                self.__UNIFORMS_KNOWN__.add(variable.name)
                self.shader.common_variable(variable)

        # Set new optional shaders
        self.shader.vertex   = vertex   or self.shader.__vertex__
        self.shader.fragment = fragment or self.shader.__fragment__

        # Add all modules includes to the shader
        for module in self.connected:
            for name, include in module.includes().items():
                self.shader.include(name, include)

        try:
            # Create the Moderngl Program - Compile shaders
            self.program = self.context.opengl.program(
                fragment_shader=self.shader.fragment,
                vertex_shader=self.shader.vertex,
            )

        # On shader compile error - Load missing texture, dump faulty shaders
        except Exception as error:

            if _missing:
                log.error(f"{self.who} Error compiling missing texture shader, aborting")
                exit(1)

            self.dump_shaders(error=str(error))
            log.error(f"{self.who} Error compiling shaders, loading missing texture shader")

            # Load missing texture shader
            self.load_shaders(
                fragment=SHADERFLOW.RESOURCES.FRAGMENT/"Missing.glsl",
                vertex=SHADERFLOW.RESOURCES.VERTEX/"Default.glsl",
                _missing=True,
            )

        # Render the vertices that are defined on the shader
        self.vbo = self.context.opengl.buffer(self.shader.vertices)

        # Create the Vertex Array Object
        self.vao = self.context.opengl.vertex_array(
            self.program,
            [(self.vbo, *self.shader.vao_definition)],
            skip_errors=True
        )

        return self

    # # Textures

    @property
    def texture_modules(self) -> Generator:
        """Get SombreroTexture modules bound to this instance"""
        yield from filter(lambda module: isinstance(module, SombreroTexture), self.connected)

    def new_texture(self, *args, **kwargs) -> SombreroTexture:
        return self.add(SombreroTexture(*args, **kwargs))

    # # SombreroModule

    def update(self) -> None:
        if not self.program:
            self.load_shaders()
        self.render()

    def render(self, read: bool=False) -> None | bytes:

        # Set indexes to textures
        for index, module in enumerate(self.texture_modules):
            module.texture.use(index)
            module.index = index

        # Pipe the pipeline
        for module in self.connected:
            for variable in module.pipeline():
                self.set_uniform(variable.name, variable.value)

        # Set render target
        self.fbo.use()

        if self.clear:
            self.fbo.clear()

        # Render the shader
        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.instances)

        # Optionally read the pixels
        return self.fbo.read() if read else None

    def handle(self, message: SombreroMessage) -> None:

        # Resize window action
        if isinstance(message, SombreroMessage.Window.Resize):
            self.create_texture_fbo()

            # The final Engine has to update the Window FBO
            if self.final:
                self.fbo.viewport = (0, 0, message.width, message.height)

        # Recreate textures action
        if isinstance(message, SombreroMessage.Engine.RecreateTextures):
            self.create_texture_fbo()

        # Reload shaders action
        if isinstance(message, SombreroMessage.Engine.ReloadShaders):
            self.load_shaders()