from __future__ import annotations

from . import *

ModernglImguiIntegration = moderngl_window.integrations.imgui.ModernglWindowRenderer

# -------------------------------------------------------------------------------------------------|

@attrs.define(slots=False)
class SombreroWindow:
    window: moderngl_window.BaseWindow = None

    window_should_close: bool = False
    strict: bool = False
    window_render_func              : BrokenRelay = attrs.Factory(BrokenRelay)
    window_resize_func              : BrokenRelay = attrs.Factory(BrokenRelay)
    window_close_func               : BrokenRelay = attrs.Factory(BrokenRelay)
    window_iconify_func             : BrokenRelay = attrs.Factory(BrokenRelay)
    window_key_event_func           : BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_position_event_func: BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_press_event_func   : BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_release_event_func : BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_drag_event_func    : BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_scroll_event_func  : BrokenRelay = attrs.Factory(BrokenRelay)
    window_unicode_char_entered_func: BrokenRelay = attrs.Factory(BrokenRelay)
    window_files_dropped_event_func : BrokenRelay = attrs.Factory(BrokenRelay)
    window_on_generic_event_func    : BrokenRelay = attrs.Factory(BrokenRelay)

# -------------------------------------------------------------------------------------------------|

@attrs.define(slots=False)
class Sombrero(SombreroModule, SombreroWindow):
    """
    Sombrero, a shader renderer framework - a pun about shadows

    Based on ModernGL, Sombrero wraps it to provide a high level interface to render shaders
    with many features and utilities, such as:

    - A Shader metaprogramming class that modules can use to define their own variables

    - Map textures, images, video to your own shaders, even other shaders as a texture
    """

    # A reference to the main instance of SombreroGL
    super: Self = None

    # Children of this instance
    shader:   SombreroShader        = attrs.field(factory=SombreroShader)
    children: list[SombreroTexture] = attrs.field(factory=list)
    textures: list[ShaderVariable]  = attrs.field(factory=list)
    window:   moderngl_window.BaseWindow = None

    # ModernGL
    opengl_context:   moderngl.Context     = None
    program:          moderngl.Program     = None
    texture:          moderngl.Texture     = None
    fbo:              moderngl.Framebuffer = None
    vao:              moderngl.VertexArray = None
    vbo:              moderngl.Buffer      = None
    clear:            bool                 = True
    instances:        int                  = 1

    # Imgui
    imgui:            ModernglImguiIntegration = None

    def __init__(self, super=None, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)
        self.super = super or self

        # Child: create fbo with attatched texture
        if not self.is_super:
            self.child_recreate_texture()

        # Super: create window, use its fbo
        else:
            # Build window settings dictionary
            moderngl_window.conf.settings.WINDOW["class"]        = f"moderngl_window.context.{self.context.backend}.Window"
            moderngl_window.conf.settings.WINDOW["title"]        = self.context.title
            moderngl_window.conf.settings.WINDOW["vsync"]        = False
            moderngl_window.conf.settings.WINDOW["samples"]      = self.context.msaa
            moderngl_window.conf.settings.WINDOW["size"]         = self.context.resolution
            moderngl_window.conf.settings.WINDOW["aspect_ratio"] = self.context.resolution[0]/self.context.resolution[1]

            # Create window and get context
            self.window         = moderngl_window.create_window_from_settings()
            self.opengl_context = self.window.ctx
            self.fbo            = self.window.fbo

            if self.context.backend != SombreroBackend.Headless:
                imgui.create_context()
                self.imgui = ModernglImguiIntegration(self.window)

            # Add Window callbacks and share them
            self.window.render_func               = self.window_render_func
            self.window.resize_func               = self.window_resize_func.bind(self._resize)
            self.window.close_func                = self.window_close_func
            self.window.iconify_func              = self.window_iconify_func
            # self.window.key_event_func            = self.window_key_event_func.bind(self.keyboard.key_event_func)
            self.window.mouse_position_event_func = self.window_mouse_position_event_func
            self.window.mouse_press_event_func    = self.window_mouse_press_event_func
            self.window.mouse_release_event_func  = self.window_mouse_release_event_func
            self.window.mouse_drag_event_func     = self.window_mouse_drag_event_func
            self.window.mouse_scroll_event_func   = self.window_mouse_scroll_event_func
            self.window.unicode_char_entered_func = self.window_unicode_char_entered_func
            self.window.files_dropped_event_func  = self.window_files_dropped_event_func
            self.window.on_generic_event_func     = self.window_on_generic_event_func

        # Render the vertices that are defined on the shader
        self.vbo = self.opengl_context.buffer(self.shader.vertices)

    def child_recreate_texture(self) -> None:
        self.texture = self.opengl_context.texture(size=self.context.resolution, components=4, samples=self.context.msaa)
        self.fbo     = self.opengl_context.framebuffer(color_attachments=[self.texture])

    @property
    def is_super(self) -> bool:
        """Is this not a child of the main instance?"""
        return self is self.super

    @property
    def is_child(self) -> bool:
        """Is this a child of the main instance?"""
        return not self.is_super

    # # Children

    def child(self, *args, **kwargs) -> Self:
        """Create a child of this instance, map as a texture to use it"""
        return BrokenUtils.append_return(self.children,
            self.__class__(
                super=self.super,
                opengl_context=self.opengl_context,
                registry=self.registry,
                *args, **kwargs,
            )
        )

    # # Resize

    def _resize(self, width: int, height: int) -> None:
        """Resize the window"""

        # Main class holds the window
        if self.is_super:
            self.relay(SombreroMessage.Window.Resize(width=width, height=height))

        # Do nothing in Strict mode
        if self.strict:
            log.trace("Resizing does nothing strict mode")
            return

        # Set internal resolution
        self.context.resolution = (width, height)

        # Resize Imgui
        if self.imgui:
            self.imgui.resize(width, height)

        for child in self.children:
            child._resize(width, height)
            child.child_recreate_texture()

        # Set new window viewport
        (self.window or self).fbo.viewport = (0, 0, width, height)

    # # Loading shaders

    def load_shaders(self, vertex: str=Unchanged, fragment: str=Unchanged, recursive: bool=True) -> None:
        """Reload the shaders after some change of variables or content"""
        log.info(f"Reloading shaders [Recursive: {recursive}]")

        # Add modules variable definitions
        for variable in self.pipeline:
            self.shader.new_variable(variable)

        # Set new optional shaders
        self.shader.vertex   = vertex   or self.shader.__vertex__
        self.shader.fragment = fragment or self.shader.__fragment__

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

        # Reload children
        for child in recursive * self.children:
            child.load_shaders(recursive=True)

    def __print_shaders__(self) -> None:

        log.debug(f"Vertex Shader:")
        for i, line in enumerate(self.shader.vertex.splitlines()):
            log.debug(f"(VERTEX  ) {i:03d} | {line}")

        log.debug(f"Fragment Shader:")
        for i, line in enumerate(self.shader.fragment.splitlines()):
            log.debug(f"(FRAGMENT) {i:03d} | {line}")

    # # Textures

    def new_texture(self,
        name: str,
        filter: "linear" | "nearest" = "linear",
        anisotropy: int=16,
        mipmaps: bool=True,
        recurse: bool=False,
    ) -> TextureFactory:
        """
        Create a new texture from many sources and add to the shader pipeline

        Args:
            name: Name of the texture on the GLSL code as sampler2D
            filter: Filter to use, one of "linear" or "nearest"
            anisotropy: Anisotropy level to use (1, 2, 4, 8, 16)
            mipmaps: Create mipmaps? They are used for better quality on far away objects
            recurse: Map this texture to all children recursively?

        Returns:
            TextureFactory: Factory to create the texture, call one of its methods
        """

        def manage_texture(texture: moderngl.Texture | ShaderVariable=None, sombrero: Sombrero=None) -> None:

            if isinstance(texture, ShaderVariable):
                return texture

            # A sombrero texture might be recreated, temporarily set to current one
            # Note: On some pre-or-on render method we must update the texture
            if not sombrero:

                # Get the ModernGL filter to use
                gl_filter = {
                    "linear":         moderngl.LINEAR,
                    "nearest":        moderngl.NEAREST,
                    "nearest-mipmap": moderngl.NEAREST_MIPMAP_NEAREST,
                    "linear-mipmap":  moderngl.LINEAR_MIPMAP_LINEAR,
                }.get(filter + ("-mipmap" if mipmaps else ""))

                # Set the texture filter
                texture.filter = (gl_filter, gl_filter)

                # Build mipmaps
                if mipmaps: texture.build_mipmaps()

                # Set anisotropy
                texture.anisotropy = anisotropy

            # Add Texture definition to pipeline, contains the data
            variable = ShaderVariable(
                qualifier="uniform",
                type="sampler2D",
                name=name,
                texture=texture,
                sombrero=sombrero,
            )

            # Add variable to pipeline
            self.textures.append(variable)

            # Map texture to children recursively
            for child in recurse * self.children:
                BrokenUtils.recurse(child.new_texture).from_shadervariable(variable)

            return variable

        class TextureFactory:
            def from_raw(size: Tuple[int, int], data: bytes=None, components=3, dtype: str="f1") -> ShaderVariable:
                """Create a new texture with raw bytes or array of pixels data"""
                return manage_texture(self.opengl_context.texture(
                    size=size,
                    components=components,
                    data=data or bytes(size[0] * size[1] * components * numpy.dtype(dtype).itemsize),
                    dtype=dtype,
                ))

            def from_image(image: PilImage) -> ShaderVariable:
                """Load an Pil Image as a texture"""
                image = BrokenSmart.load_image(image)
                return TextureFactory.from_raw(
                    size=image.size,
                    data=image.transpose(PIL.Image.FLIP_TOP_BOTTOM).tobytes(),
                    components=len(image.getbands()),
                    dtype="f1"
                )

            def from_path(path: Path) -> ShaderVariable:
                """Load an Image from path as a texture"""
                return TextureFactory.from_image(image=PIL.Image.open(path))

            def from_sombrero(sombrero: Sombrero) -> ShaderVariable:
                """Use some other Sombrero texture"""
                return manage_texture(sombrero=sombrero)

            def from_moderngl(texture: moderngl.Texture) -> ShaderVariable:
                """Use some other ModernGL texture"""
                return manage_texture(texture)

            def from_shadervariable(variable: ShaderVariable) -> ShaderVariable:
                """Use some other ShaderVariable texture"""
                return manage_texture(variable)

        return TextureFactory

    # # Uniforms

    def set_uniform(self, name: str, value: Any) -> Self:
        """
        Send an uniform to the shader

        Args:
            name: Name of the uniform
            value: Value of the uniform

        Returns:
            Self: Fluent interface
        """
        if name in self.program:
            self.program[name].value = value
        return self

    def get_uniform(self, name) -> Option[Any, None]:
        """
        Get a uniform from the shader

        Args:
            name: Name of the uniform

        Returns:
            Option[Any, None]: Value of the uniform
        """
        return self.program[name].get(value, None)

    # # Rendering

    @property
    def pipeline(self) -> list[ShaderVariable]:
        """Get the pipeline of this instance and its children"""
        return BrokenUtils.flatten(
            [module.pipeline for module in self.bound_modules],
            self.textures,
        )

    def render(self, read=False) -> Option[None, bytes]:
        """
        Render the shader - plus "downwards" children, optionally read the pixels

        Args:
            read: Read the pixels?

        Returns:
            Option[None, bytes]: Pixelss if read=True, None otherwise
        """

        # Render all children
        for child in self.children:
            child.render()

        log.trace(f"Rendering {self.short_hash}")

        # Pipe the pipeline, map textures
        for index, item in enumerate(self.pipeline):

            # Item is a texture - plain or from a sombrero
            if item.sombrero or item.texture:

                # Update the Sombrero texture on the variable
                if item.sombrero:
                    item.texture = item.sombrero.texture

                # Use and bind texture index
                item.texture.use(index)
                item.value = index

            # Send the variable value to the shader
            self.set_uniform(item.name, item.value)
            log.trace(f"· {str(item.name).ljust(16)}: {item.value}")

        self.fbo.use()

        # Clear screen
        if self.clear:
            self.fbo.clear(0)

        # Enable blend
        self.opengl_context.enable(moderngl.BLEND)

        # Render the shader
        self.vao.render(moderngl.TRIANGLE_STRIP, instances=self.instances)

        # Swap window buffers
        if self.window:
            self.window.swap_buffers()

        # Optionally read the pixels
        return self.fbo.read() if read else None

