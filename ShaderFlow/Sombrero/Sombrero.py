from __future__ import annotations

from . import *

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroTexture:
    name: str
    texture: moderngl.Texture
    sombrero: Sombrero = None

# -------------------------------------------------------------------------------------------------|

@attrs.define(slots=False)
class SombreroWindow:
    window: moderngl_window.BaseWindow = None

# -------------------------------------------------------------------------------------------------|

@attrs.define
class Sombrero(SombreroModule, SombreroWindow):
    # A reference to the main instance of SombreroGL
    super: Self = None

    # Children of this instance
    children: list[SombreroTexture] = attrs.field(factory=list)
    shader  : SombreroShader        = attrs.field(factory=SombreroShader)

    # ModernGL
    opengl_context  : moderngl.Context     = None
    program         : moderngl.Program     = None
    texture         : moderngl.Texture     = None
    fbo             : moderngl.Framebuffer = None
    vao             : moderngl.VertexArray = None
    vbo             : moderngl.Buffer      = None
    render_instances: int                  = 1

    def __init__(self, super=None, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)
        self.super = super or self

        # Create window if super else headless texture
        # Get window's FBO or headless texture's FBO
        if not self.is_super:
            self.texture = self.opengl_context.texture(size=self.context.resolution, components=4, samples=self.context.msaa)
            self.fbo     = self.opengl_context.framebuffer(color_attachments=[self.texture])
        else:
            # Build window settings dictionary
            moderngl_window.conf.settings.WINDOW["class"]        = f"moderngl_window.context.{self.context.backend.value}.Window"
            moderngl_window.conf.settings.WINDOW["title"]        = self.context.title
            moderngl_window.conf.settings.WINDOW["vsync"]        = False
            moderngl_window.conf.settings.WINDOW["samples"]      = self.context.msaa
            moderngl_window.conf.settings.WINDOW["size"]         = self.context.resolution
            moderngl_window.conf.settings.WINDOW["aspect_ratio"] = self.context.resolution[0]/self.context.resolution[1]

            # Create window and get context
            self.window         = moderngl_window.create_window_from_settings()
            self.opengl_context = self.window.ctx
            self.fbo            = self.window.fbo

        # Render the vertices that are defined on the shader
        self.vbo = self.opengl_context.buffer(self.shader.vertices)

    @property
    def is_super(self) -> bool:
        """Is this not a child of the main instance?"""
        return self is self.super

    # # Children

    def child(self, *args, **kwargs) -> Self:
        """Create a child of this instance, map as a texture to use it"""
        child = self.__class__(
            super=self.super,
            opengl_context=self.opengl_context,
            registry=self.registry,
            *args, **kwargs,
        )

        # Make Child be on this class's pipeline
        self.bind(child)

    # # Loading shaders

    def load_shaders(self, vertex: str=Unchanged, fragment: str=Unchanged, recursive: bool=True) -> None:
        """Reload the shaders after some change of variables or content"""
        log.info(f"Reloading shaders [Recursive: {recursive}]")

        # Set new optional shaders
        self.shader.vertex   = vertex   or self.shader.__vertex__
        self.shader.fragment = fragment or self.shader.__fragment__

        log.debug(f"Vertex Shader:")
        for i, line in enumerate(self.shader.vertex.splitlines()):
            log.debug(f"(VERTEX  ) {i:03d} | {line}")

        log.debug(f"Fragment Shader:")
        for i, line in enumerate(self.shader.fragment.splitlines()):
            log.debug(f"(FRAGMENT) {i:03d} | {line}")

        # Compile shaders to program
        self.program = self.opengl_context.program(
            vertex_shader=self.shader.vertex,
            fragment_shader=self.shader.fragment,
        )

        # Create Vertex Array Object
        self.vao = self.opengl_context.vertex_array(
            self.program,
            [(self.vbo, *self.shader.vao_definition)],
        )

        if not recursive:
            return

        # Reload children
        for child in self.children:
            child.reload(recursive=True)

    # # Uniforms

    def set_uniform(self, name: str, value: Any) -> Any:
        """Send a uniform to the shader fail-safe if it isn't used"""
        if name in self.program:
            self.program[name].value = value
        return value

    def get_uniform(self, name) -> Option[Any, None]:
        """Get a uniform from the shader fail-safe if it isn't used"""
        return self.program[name].get(value, None)

    # # Rendering

    def clear(self) -> None:
        """Clear the render target"""
        self.fbo.clear(0)

    @property
    def pipeline(self) -> dict[str, Any]:
        """Get the pipeline sent to the shader of this and all modules"""
        data = {}
        for module in self.bound_modules:
            print("Bound", module)
            data = data | module.pipeline()
        return data

    def render(self, read=False) -> Option[None, bytes]:
        """Render the shader, optionally read the pixels"""

        # Render all children
        # for child in self.sombrero_children():
            # child.render()

        # Pipe pipeline
        for name, value in self.pipeline.items():
            self.set_uniform(name, value)

        print(self.bound)

        # Map textures
        # for index, child in enumerate(self.children):
        #     self.set_uniform(child.name, index)
        #     if child.sombrero:
        #         child.sombrero.texture.use(index)
        #     else:
        #         child.texture.use(index)

        # Render the shader
        self.fbo.use()

        # Clear the render target
        self.clear()

        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.render_instances)

        # Swap window buffers
        if self.window:
            self.window.swap_buffers()

        # Optionally read the pixels
        return self.fbo.read() if read else None

