from __future__ import annotations

from . import *

# -------------------------------------------------------------------------------------------------|

@attrs.define(slots=False)
class Sombrero(SombreroModule):
    """
    Sombrero, a shader renderer framework - a pun about shadows

    Based on ModernGL, Sombrero wraps it to provide a high level interface to render shaders
    with many features and utilities, such as:

    - A Shader metaprogramming class that modules can use to define their own variables

    - Map textures, images, video to your own shaders, even other shaders as a texture
    """

    # Children of this instance
    shader:   SombreroShader        = attrs.field(factory=SombreroShader)

    # ModernGL
    program:          moderngl.Program     = None
    texture:          moderngl.Texture     = None
    __fbo__:          moderngl.Framebuffer = None
    vao:              moderngl.VertexArray = None
    vbo:              moderngl.Buffer      = None
    clear:            bool                 = True
    instances:        int                  = 1

    # Is this the main Sombrero instance?
    __main__:         bool                 = False

    def __init__(self, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)
        self.create_texture_fbo()

    def create_texture_fbo(self):
        self.texture = self.context.opengl.texture(size=self.context.resolution, components=4, samples=self.context.msaa)
        self.fbo     = self.context.opengl.framebuffer(color_attachments=[self.texture])

    # # Main Sombrero instance handling

    @property
    def fbo(self) -> moderngl.Framebuffer:
        if self.__main__:
            return self.window.window.fbo
        return self.__fbo__

    @fbo.setter
    def fbo(self, value: moderngl.Framebuffer) -> None:
        if self.__main__:
            return
        self.__fbo__ = value

    def render_to_window(self, value: bool=True) -> Self:
        """Should / make this Sombrero instance render to the window?"""
        self.__main__ = value
        return self

    # # Child and mapping it as texture

    def child(self) -> Self:
        child = self.__class__(registry=self.registry)
        self.bind(child)
        return child

    def as_texture(self, name: str) -> SombreroTexture:
        """Create a SombreroTexture from this Sombrero instance"""
        return SombreroTexture(name=name).from_sombrero(self)

    # # Resize

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Window.Resize):
            self.fbo.viewport = (0, 0, message.width, message.height)
            self.create_texture_fbo()

    # # Loading shaders

    def load_shaders(self, vertex: str=Unchanged, fragment: str=Unchanged, recursive: bool=True) -> None:
        """Reload the shaders after some change of variables or content"""
        log.info(f"Reloading shaders [Recursive: {recursive}]")

        # Add modules variable definitions
        for variable in self.pipeline:
            self.shader.new_variable(variable)

        # Render the vertices that are defined on the shader
        self.vbo = self.context.opengl.buffer(self.shader.vertices)

        # Set new optional shaders
        self.shader.vertex   = vertex   or self.shader.__vertex__
        self.shader.fragment = fragment or self.shader.__fragment__

        # Compile shaders to program
        self.program = self.context.opengl.program(
            vertex_shader=self.shader.vertex,
            fragment_shader=self.shader.fragment,
        )

        # Create Vertex Array Object
        self.vao = self.context.opengl.vertex_array(
            self.program,
            [(self.vbo, *self.shader.vao_definition)],
        )

    def __print_shaders__(self) -> None:

        log.debug(f"Vertex Shader:")
        for i, line in enumerate(self.shader.vertex.splitlines()):
            log.debug(f"(VERTEX  ) {i:03d} | {line}")

        log.debug(f"Fragment Shader:")
        for i, line in enumerate(self.shader.fragment.splitlines()):
            log.debug(f"(FRAGMENT) {i:03d} | {line}")

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

    @property
    def pipeline(self) -> list[ShaderVariable]:
        """Get the pipeline of this instance and the bound non-Self modules"""
        return BrokenUtils.flatten([
            module.pipeline for module in self.bound_modules
            if not isinstance(module, self.__class__)
        ])

    def render(self, read=False) -> Option[None, bytes]:
        """
        Render the shader - plus "downwards" children, optionally read the pixels

        Args:
            read: Read the pixels?

        Returns:
            Option[None, bytes]: Pixelss if read=True, None otherwise
        """

        # Render bound sombrero children
        for module in self.bound_modules:
            if isinstance(module, self.__class__):
                module.render()

        # Bind textures - images, other shaders after rendering
        for index, item in enumerate(self.bound_modules):
            if isinstance(item, SombreroTexture):
                item.texture.use(index)
                item.index = index

        # Pipe the pipeline
        for index, item in enumerate(self.pipeline):
            self.set_uniform(item.name, item.value)

        self.fbo.use()

        # Clear screen
        if self.clear:
            self.fbo.clear(0)

        # Enable blend
        self.context.opengl.enable(moderngl.BLEND)

        # Render the shader
        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.instances)

        # Optionally read the pixels
        return self.fbo.read() if read else None

