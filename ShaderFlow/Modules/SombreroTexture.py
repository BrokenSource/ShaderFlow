from . import *


class SombreroTextureFilter(BrokenEnum):
    """Filters to use on textures"""
    Nearest = "nearest"
    Linear  = "linear"

@attrs.define
class SombreroTexture(SombreroModule):
    __texture__: moderngl.Texture = None
    sombrero:    Any              = None

    # Variable definition on the shader
    variable:   ShaderVariable = None

    # ModernGL options
    __filter__: SombreroTextureFilter = SombreroTextureFilter.Linear
    anisotropy: int  = 16
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

    # # Initialization

    def __init__(self, name: str, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)

        # Create variable definition
        self.variable = ShaderVariable(
            qualifier="uniform",
            type="sampler2D",
            name=name,
            value=random.randint(0, 1000),
        )

    # # SombreroModule implementation

    @property
    def pipeline(self) -> dict[ShaderVariable]:
        """The SombreroTexture pipeline tells the shader where to find the texture"""
        return self.variable

    def on_message(*args, **kwargs):
        """Textures don't care about messages"""
        pass

    # # Prioritize Sombrero Texture

    @property
    def texture(self) -> moderngl.Texture | None:
        return self.__texture__ or self.sombrero.texture

    @texture.setter
    def texture(self, value: moderngl.Texture) -> None:
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
        # self.apply_options()
        return self

    def from_image(self, image: PilImage) -> Self:
        """Load an Pil Image as a texture"""
        image = BrokenSmart.load_image(image)
        return self.from_raw(
            size=image.size,
            data=image.transpose(PIL.Image.FLIP_TOP_BOTTOM).tobytes(),
            components=len(image.getbands()),
            dtype="f1"
        )

    def from_path(self, path: Path) -> Self:
        """Load an Image from path as a texture"""
        return self.from_image(image=PIL.Image.open(path))

    def from_sombrero(self, sombrero: Any) -> Self:
        """Use some other Sombrero texture"""
        self.sombrero = sombrero
        return self

    def from_moderngl(self, texture: moderngl.Texture) -> Self:
        """Use some other ModernGL texture"""
        self.texture = texture
        return self
