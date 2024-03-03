from . import *


class ShaderFlowTextureFilter(BrokenEnum):
    """Filters to use on textures"""
    Nearest = "nearest"
    Linear  = "linear"

class ShaderFlowTextureAnisotropy(BrokenEnum):
    """Anisotropy levels to use on textures"""
    x1  = 1
    x2  = 2
    x4  = 4
    x8  = 8
    x16 = 16

@define
class ShaderFlowTexture(ShaderFlowModule):

    # Variable definition on the shader
    variable: ShaderVariable = Factory(ShaderVariable)

    # # Initialization

    def __init__(self,
        name: str,
        filter:     ShaderFlowTextureFilter     = ShaderFlowTextureFilter.Linear,
        anisotropy: ShaderFlowTextureAnisotropy = ShaderFlowTextureAnisotropy.x16,
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

    __data__: bytes = None

    @property
    def is_empty(self) -> bool:
        return not any((
            self.__module__,
            self.__data__
        ))

    def clear(self) -> Self:
        self.texture.write(numpy.zeros((*self.size, self.components), dtype=self.dtype))

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

    # # Anisotropy

    __anisotropy__: ShaderFlowTextureAnisotropy = ShaderFlowTextureAnisotropy.x16

    @property
    def anisotropy(self) -> int:
        return self.__anisotropy__.value

    @anisotropy.setter
    def anisotropy(self, value: int | ShaderFlowTextureAnisotropy) -> Self:
        self.__anisotropy__ = ShaderFlowTextureAnisotropy.get(value)
        log.trace(f"{self.who} Setting Texture Anisotropy to {self.__anisotropy__}")
        return self.__apply_options__()

    # # Filtering

    __mipmaps__: bool = True

    @property
    def mipmaps(self) -> bool:
        return self.__mipmaps__

    @mipmaps.setter
    def mipmaps(self, value: bool) -> Self:
        self.__mipmaps__ = value
        log.trace(f"{self.who} Setting Texture Mipmaps to {value}")
        return self.__apply_options__()

    __filter__: ShaderFlowTextureFilter = ShaderFlowTextureFilter.Linear

    @property
    def filter(self) -> str:
        return self.__filter__.value

    @filter.setter
    def filter(self, value: str | ShaderFlowTextureFilter) -> Self:
        self.__filter__ = ShaderFlowTextureFilter.get(value)
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

    # # Prioritize ShaderFlow Texture

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
            log.warning(f"({self.who}) Setting texture to ShaderFlowEngine is forbidden")
            return
        self.__texture__ = value

    # # Basic options

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
        self.__data__ = data
        self.__texture__.write(data=data, viewport=viewport, level=level, alignment=alignment)
        return self

    def read(self, *args, **kwargs) -> bytes:
        return self.texture.read(*args, **kwargs)

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
        return getattr(self.texture, "dtype", "f4")

    # # From methods

    def from_raw(self,
        data: bytes=None,
        size: Tuple[int, int]=(0, 0),
        components: int=3,
        dtype: str="f4",
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
        self.__data__ = data

        # Create the OpenGL texture
        self.__texture__ = self.scene.opengl.texture(
            data=data,
            size=size,
            components=components,
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
        image = LoaderImage(image)
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

    def from_numpy(self,
        array: numpy.ndarray,
        dtype: str="f4",
        components: int=4,
    ) -> Self:
        """
        Load a numpy array as a texture

        Args:
            array (numpy.ndarray): The array to load

        Returns:
            Self: The current instance with the texture loaded
        """
        self.__module__ = None
        size = array.shape

        if len(size) == 3:
            components = size[2]
            size = size[:2][::-1]

        return self.from_raw(
            size=size,
            data=array.tobytes(),
            components=components,
            dtype=dtype,
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

    def from_module(self, module: ShaderFlowModule) -> Self:
        """
        Use some other ShaderFlowModule's texture
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

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        """The ShaderFlowTexture pipeline tells the shader where to find the texture"""
        yield self.variable
        yield ShaderVariable("uniform", "vec2",  f"i{self.name}Size",        self.size)
        yield ShaderVariable("uniform", "float", f"i{self.name}AspectRatio", self.aspect_ratio)