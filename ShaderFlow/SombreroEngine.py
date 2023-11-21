from . import *


@attrs.define
class SombreroEngine(SombreroModule):
    shader: SombreroShader = attrs.field(factory=SombreroShader)
    textures: dict[SombreroTexture] = attrs.field(factory=dict)

    # ModernGL
    program:          moderngl.Program     = None
    texture:          moderngl.Texture     = None
    __fbo__:          moderngl.Framebuffer = None
    vao:              moderngl.VertexArray = None
    vbo:              moderngl.Buffer      = None
    clear:            bool                 = True
    instances:        int                  = 1

    # Should this instance render finally to the window
    main:             bool                 = False

    def create_texture_fbo(self):
        self.texture = self.context.opengl.texture(size=self.context.resolution, components=4, samples=self.context.msaa)
        self.fbo     = self.context.opengl.framebuffer(color_attachments=[self.texture])

    # # Main Sombrero instance handling

    @property
    def fbo(self) -> moderngl.Framebuffer:
        if self.main:
            return self.context.window.fbo

        if not self.__fbo__:
            self.create_texture_fbo()

        return self.__fbo__

    @fbo.setter
    def fbo(self, value: moderngl.Framebuffer) -> None:
        if self.main:
            return
        self.__fbo__ = value

    def render_to_window(self, value: bool=True) -> Self:
        """Should / make this Sombrero instance render to the window?"""
        self.main = value
        return self

    # # Child and mapping it as texture

    def child(self) -> Self:
        return self.__class__(scene=self.scene)

    def as_texture(self, name: str) -> SombreroTexture:
        """Create a SombreroTexture from this Sombrero instance"""
        return SombreroTexture(name=name).from_sombrero(self)

    # # Uniforms

    def set_uniform(self, name: str, value: Any) -> Self:
        """Send an uniform to the shader by name and value"""
        if name in self.program:
            self.program[name].value = value
        return self

    def get_uniform(self, name) -> Option[Any, None]:
        """Get a uniform from the shader by name"""
        return self.program[name].get(value, None)

    # # Rendering

    def load_shaders(self, vertex: str=Unchanged, fragment: str=Unchanged) -> None:
        """Reload the shaders after some change of variables or content"""
        log.trace(f"({self.suuid}) Reloading shaders, pipeline:")

        # Add pipeline variable definitions
        for variable in self.full_pipeline():
            self.shader.fragment_variable(variable)
            log.trace(f"• {variable}")
        log.trace("")

        # Render the vertices that are defined on the shader
        self.vbo = self.context.opengl.buffer(self.shader.vertices)

        # Set new optional shaders
        self.shader.vertex   = vertex   or self.shader.__vertex__
        self.shader.fragment = fragment or self.shader.__fragment__

        # Create the Moderngl Program
        self.program = self.context.opengl.program(
            fragment_shader=self.shader.fragment,
            vertex_shader=self.shader.vertex,
        )

        # Create the Vertex Array Object
        self.vao = self.context.opengl.vertex_array(
            self.program,
            [(self.vbo, *self.shader.vao_definition)],
            skip_errors=True
        )

    def update(self) -> None:
        self.render()

    @property
    def __texture_modules__(self) -> list[SombreroTexture]:
        """Get SombreroTexture modules bound to this instance"""
        return [module for module in self.bound if isinstance(module, SombreroTexture)]

    def as_texture(self, name: str) -> SombreroTexture:
        """Create a SombreroTexture from this Sombrero instance"""
        return self.scene.add(SombreroTexture(name=name)).from_engine(self)

    def render(self, read: bool=False) -> Option[None, bytes]:

        # Set indexes to textures
        for index, module in enumerate(self.__texture_modules__):
            module.texture.use(index)
            module.index = index

        # Pipe the pipeline
        for variable in self.full_pipeline():
            log.trace(f"({self.suuid}) • {variable.name} = {variable.value}")
            self.set_uniform(variable.name, variable.value)

        # Set render target
        self.fbo.use()

        if self.clear:
            self.fbo.clear()

        # Render the shader
        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.instances)

        # Optionally read the pixels
        return self.fbo.read() if read else None
