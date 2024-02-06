from . import *


class SombreroTextureFilter(BrokenEnum):
    """Filters to use on textures"""
    Nearest = "nearest"
    Linear  = "linear"

class SombreroTextureAnisotropy(BrokenEnum):
    """Anisotropy levels to use on textures"""
    x1  = 1
    x2  = 2
    x4  = 4
    x8  = 8
    x16 = 16

@define
class SombreroTexture(SombreroModule):

    # Variable definition on the shader
    variable: ShaderVariable = field(factory=ShaderVariable)

    # # Initialization

    def __init__(self,
        name: str,
        filter:     str | SombreroTextureFilter     = SombreroTextureFilter.Linear,
        anisotropy: int | SombreroTextureAnisotropy = SombreroTextureAnisotropy.x16,
        mipmaps:    bool=True,
        *args, **kwargs
    ):
        self.__attrs_init__(*args, **kwargs)

        # Apply options
        self.filter     = filter
        self.anisotropy = anisotropy
        self.mipmaps    = mipmaps

        # Create variable definition
        self.variable.qualifier = "uniform"
        self.variable.type      = "sampler2D"
        self.variable.name      = name

    @property
    def is_empty(self) -> bool:
        return not any((
            self.__module__,
            self.__data__
        ))

    # # Repeat texture

    __repeat_x__: bool = True
    __repeat_y__: bool = True

    @property
    def repeat_x(self) -> bool:
        return self.__repeat_x__

    @repeat_x.setter
    def repeat_x(self, value: bool) -> None:
        self.__repeat_x__ = value
        log.trace(f"{self.who} Setting Texture Repeat X to {value}")
        self.__apply_options__()

    @property
    def repeat_y(self) -> bool:
        return self.__repeat_y__

    @repeat_y.setter
    def repeat_y(self, value: bool) -> None:
        self.__repeat_y__ = value
        log.trace(f"{self.who} Setting Texture Repeat Y to {value}")
        self.__apply_options__()

    def repeat(self, value: bool) -> Self:
        self.repeat_x = value
        self.repeat_y = value
        return self

    # # Texture name and index - sync with the ShaderVariable

    @property
    def index(self) -> int:
        return self.variable.value

    @index.setter
    def index(self, value: int) -> int:
        self.variable.value = value
        return value

    @property
    def name(self) -> str:
        return self.variable.name

    @name.setter
    def name(self, value: str) -> Self:
        # Fixme: We should reload the shaders?
        self.variable.name = value
        return self

    # # Anisotropy

    __anisotropy__: SombreroTextureAnisotropy = SombreroTextureAnisotropy.x16

    @property
    def anisotropy(self) -> int:
        return self.__anisotropy__.value

    @anisotropy.setter
    def anisotropy(self, value: int | SombreroTextureAnisotropy) -> Self:
        self.__anisotropy__ = SombreroTextureAnisotropy.get(value)
        log.trace(f"{self.who} Setting Texture Anisotropy to {self.__anisotropy__}")
        return self.__apply_options__()

    # # Filter

    __filter__:  SombreroTextureFilter = SombreroTextureFilter.Linear
    __mipmaps__: bool                  = True

    # Mipmaps

    @property
    def mipmaps(self) -> bool:
        return self.__mipmaps__

    @mipmaps.setter
    def mipmaps(self, value: bool) -> Self:
        self.__mipmaps__ = value
        log.trace(f"{self.who} Setting Texture Mipmaps to {value}")
        return self.__apply_options__()

    # Filter

    @property
    def filter(self) -> str:
        return self.__filter__.value

    @filter.setter
    def filter(self, value: str | SombreroTextureFilter) -> Self:
        self.__filter__ = SombreroTextureFilter.get(value)
        log.trace(f"{self.who} Setting Texture Filter to {self.__filter__}")
        return self.__apply_options__()


    # # Apply Texture options

    def __apply_options__(self) -> Self:
        """
        OpenGL filters must be defined also based on mipmaps
        """
        if not self.texture:
            return

        # Get the ModernGL filter to use
        filter = {
            "linear":         moderngl.LINEAR,
            "nearest":        moderngl.NEAREST,
            "nearest-mipmap": moderngl.NEAREST_MIPMAP_NEAREST,
            "linear-mipmap":  moderngl.LINEAR_MIPMAP_LINEAR,
        }.get(self.filter + ("-mipmap" * self.mipmaps))

        # Set the texture filter
        self.texture.filter = (filter, filter)

        # Build mipmaps
        if self.__mipmaps__:
            self.texture.build_mipmaps()

        # Set anisotropy
        self.texture.anisotropy = self.anisotropy

        # Set repeat
        self.texture.repeat_x = self.repeat_x
        self.texture.repeat_y = self.repeat_y

        return self

    # # Prioritize Sombrero Texture

    __texture__: moderngl.Texture = None
    __module__:  Any              = None

    @property
    def texture(self) -> moderngl.Texture | None:
        if self.__module__:
            return self.__module__.texture
        return self.__texture__

    @texture.setter
    def texture(self, value: moderngl.Texture) -> None:
        if self.__module__:
            log.warning(f"({self.who}) Setting texture to SombreroEngine is forbidden")
            return
        self.__texture__ = value

    # # Basic options

    # A copy of the last written data
    __data__: bytes = None

    def write(self,
        data: bytes=None,
        viewport: Tuple[int, int, int, int]=None,
        level: int=0,
        alignment: int=1
    ) -> Self:
        """
        Write data to the internal texture, wrapper for moderngl.Texture.write

        Args:
            data:      The data to write, bytes, must match the viewport
            viewport:  The viewport to write to, defaults to full texture (0, 0, width, height)
            level:     The mipmap level to write to
            alignment: The alignment of the data

        Returns:
            Self: Fluent interface
        """
        # Fixme: Optimization to not copy the whole data when viewport ?
        self.__data__ = self.__texture__.read() if viewport else data
        self.__texture__.write(data=data, viewport=viewport, level=level, alignment=alignment)
        return self

    def read(self, *args, **kwargs) -> bytes:
        return self.texture.read(*args, **kwargs)

    # Note: The methods below are "safe"y when a texture is created but not initialized
    # Note: The parameter .is_empty still works, as we never wrote to __data__

    @property
    def width(self) -> int:
        return getattr(self.texture, "width", 1)

    @property
    def height(self) -> int:
        return getattr(self.texture, "height", 1)

    @property
    def size(self) -> Tuple[int, int]:
        return getattr(self.texture, "size", (1, 1))

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def components(self) -> int:
        return getattr(self.texture, "components", 3)

    @property
    def dtype(self) -> str:
        return getattr(self.texture, "dtype", "f1")

    # # From methods

    def from_raw(self,
        data: bytes=None,
        size: Tuple[int, int]=(0, 0),
        components: int=3,
        dtype: str="f4"
    ) -> Self:
        """
        Create a new texture with raw bytes or array of pixels data

        Args:
            size:       The size of the texture
            data:       The raw bytes or array of pixels data
            components: The number of components per pixel
            dtype:      The data type of the pixels

        Returns:
            Self: The current instance with the texture loaded
        """

        # Copy of the last data written
        self.__data__ = data

        # Create the OpenGL texture
        self.__texture__ = self.scene.opengl.texture(
            size=size,
            components=components,
            data=self.__data__,
            dtype=dtype,
        )

        self.__apply_options__()
        return self

    def from_image(self, image: Image) -> Self:
        """
        Load an instantiated PIL Image as a texture

        Args:
            image (Image): The image to load

        Returns:
            Self: The current instance with the texture loaded
        """
        log.trace(f"{self.who} Using texture from Image: {image}")
        image = BrokenUtils.load_image(image)
        self.__module__ = None
        return self.from_raw(
            size=image.size,
            data=image.transpose(PIL.Image.FLIP_TOP_BOTTOM).tobytes(),
            components=len(image.getbands()),
            dtype=numpy.array(image).dtype.str[1:].replace("u", "f")
        )

    def from_pil(self, image: Image) -> Self:
        """Wraps around .from_image"""
        self.from_image(image)

    def from_numpy(self, array: numpy.ndarray) -> Self:
        """
        Load a numpy array as a texture

        Args:
            array (numpy.ndarray): The array to load

        Returns:
            Self: The current instance with the texture loaded
        """
        self.__module__ = None
        return self.from_raw(
            size=array.shape[:2],
            data=array.tobytes(),
            components=array.shape[2] if len(array.shape) > 2 else 1,
            dtype=array.dtype.str[1:].replace("u", "f")
        )

    def from_path(self, path: Path) -> Self:
        """
        Load an Image from path as a texture

        Args:
            path (Path): The path to the image

        Returns:
            Self: The current instance with the texture loaded
        """
        log.trace(f"({self.who}) Loading texture from path: {path}")
        return self.from_image(path)

    def from_module(self, module: SombreroModule) -> Self:
        """
        Use some other SombreroModule's texture
        Note: The `module` must have a .texture attribute

        Args:
            module: The module to use the texture from

        Returns:
            Self: The current instance
        """
        log.trace(f"{self.who} Using texture from module: {module.who}")
        self.__texture__ = None
        self.__module__  = module
        return self

    def from_moderngl(self, texture: moderngl.Texture) -> Self:
        """
        Use a ModernGL texture directly

        Args:
            texture: The ModernGL texture to use

        Returns:
            Self: The current instance
        """
        log.trace(f"{self.who} Using texture from ModernGL: {texture}")
        self.__texture__ = texture
        self.__module__  = None
        self.__apply_options__()
        return self

    # # Module methods

    def pipeline(self) -> Iterable[ShaderVariable]:
        """The SombreroTexture pipeline tells the shader where to find the texture"""
        yield self.variable
        yield ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.name}Size",        value=self.size)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.name}AspectRatio", value=self.aspect_ratio)

    def handle(self, message: SombreroMessage):

        # When recreating the Window,
        if isinstance(message, SombreroMessage.Engine.RecreateTextures):
            if self.__module__:
                return

            self.from_raw(
                size=self.size,
                data=self.__data__,
                components=self.components,
                dtype=self.dtype,
            )

            self.__apply_options__()
