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

@attrs.define
class SombreroTexture(SombreroModule):

    # Variable definition on the shader
    variable:   ShaderVariable = None

    # ModernGL options
    __texture__:    moderngl.Texture = None
    __engine__:     Any              = None
    __filter__:     SombreroTextureFilter     = SombreroTextureFilter.Linear
    __anisotropy__: SombreroTextureAnisotropy = SombreroTextureAnisotropy.x16
    mipmaps:    bool = True

    # Texture index (value) is stored on the ShaderVariable

    @property
    def index(self) -> int:
        return self.variable.value

    @index.setter
    def index(self, value: int) -> None:
        self.variable.value = value

    # Texture name is stored on the ShaderVariable

    @property
    def name(self) -> str:
        return self.variable.name

    @name.setter
    def name(self, value: str) -> None:
        self.variable.name = value

    # # Filter

    @property
    def filter(self) -> str:
        return self.__filter__.value

    @filter.setter
    def filter(self, value: str | SombreroTextureFilter) -> None:
        self.__filter__ = SombreroTextureFilter.smart(value)
        self.apply_options()

    # # Anisotropy

    @property
    def anisotropy(self) -> int:
        return self.__anisotropy__.value

    @anisotropy.setter
    def anisotropy(self, value: int | SombreroTextureAnisotropy) -> None:
        self.__anisotropy__ = SombreroTextureAnisotropy.smart(value)
        self.apply_options()

    # # Initialization

    def __init__(self, name: str, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)

        # Create variable definition
        self.variable = ShaderVariable(
            qualifier="uniform",
            type="sampler2D",
            name=name,
        )

    # # Prioritize Sombrero Texture

    @property
    def texture(self) -> moderngl.Texture | None:
        return self.__engine__.texture if self.__engine__ else self.__texture__

    @texture.setter
    def texture(self, value: moderngl.Texture) -> None:
        if self.__engine__:
            log.warning(f"({self.suuid}) Setting texture to SombreroEngine is forbidden")
            return
        self.__texture__ = value

    # # ModernGL options

    def apply_options(self):

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
        if self.mipmaps:
            self.texture.build_mipmaps()

        # Set anisotropy
        self.texture.anisotropy = self.anisotropy

    # # From methods

    def from_raw(self, size: Tuple[int, int], data: bytes=None, components=3, dtype: str="f1") -> Self:
        """Create a new texture with raw bytes or array of pixels data"""
        self.texture = self.context.opengl.texture(
            size=size,
            components=components,
            data=data or bytes(size[0] * size[1] * components * numpy.dtype(dtype).itemsize),
            dtype=dtype,
        )
        self.apply_options()
        return self

    def from_image(self, image: PilImage) -> Self:
        """Load an Pil Image as a texture"""
        image = BrokenUtils.load_image(image)
        return self.from_raw(
            size=image.size,
            data=image.transpose(PIL.Image.FLIP_TOP_BOTTOM).tobytes(),
            components=len(image.getbands()),
            dtype="f1"
        )

    def from_path(self, path: Path) -> Self:
        """Load an Image from path as a texture"""
        log.trace(f"({self.suuid}) Loading texture from path: {path}")
        return self.from_image(image=PIL.Image.open(path))

    def from_engine(self, engine: Any) -> Self:
        """Use some other Sombrero texture"""
        self.__engine__ = engine
        return self

    def from_moderngl(self, texture: moderngl.Texture) -> Self:
        """Use some other ModernGL texture"""
        self.texture = texture
        return self

    # # Module methods

    def pipeline(self) -> list[ShaderVariable]:
        """The SombreroTexture pipeline tells the shader where to find the texture"""
        return [self.variable]
