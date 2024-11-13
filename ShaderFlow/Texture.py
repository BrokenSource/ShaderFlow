from collections import deque
from typing import Any, Deque, Iterable, Optional, Self, Tuple, Union

import moderngl
import numpy
from attr import Factory, define, field

from Broken import BrokenEnum, Nothing, list_get, pop_fill
from Broken.Loaders import LoadableImage, LoaderImage
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Variable import ShaderVariable, Uniform


# Fixme: usampler2D, isampler2D?
def numpy2mgltype(type: Union[numpy.dtype, str]) -> str:
    if isinstance(type, str):
        return type
    if isinstance(type, numpy.dtype):
        type = type.type
    return {
        numpy.uint8:   "f1",
        numpy.uint16:  "u2",
        numpy.float16: "f2",
        numpy.float32: "f4",
    }.get(type)


class TextureFilter(BrokenEnum):
    # Fixme: Disallow bad combinations of filter and types
    Nearest = "nearest"
    Linear  = "linear"


class Anisotropy(BrokenEnum):
    x1  = 1
    x2  = 2
    x4  = 4
    x8  = 8
    x16 = 16


@define
class TextureBox:
    texture: moderngl.Texture = None
    fbo:     moderngl.Framebuffer = None
    data:    bytes = field(default=None, repr=False)
    clear:   bool  = False
    empty:   bool  = True

    def release(self) -> Self:
        (self.texture or Nothing()).release()
        (self.fbo     or Nothing()).release()


@define
class ShaderTexture(ShaderModule):
    name: str = None

    def __post__(self):
        self.make()

    # ------------------------------------------|

    def __smart__(self, attr, value, method) -> Any:
        if (converter := attr.converter):
            value = converter(value)
        if getattr(self, attr.name) != value:
            self.__setstate__({attr.name: value})
            method()
        return value

    def __apply__(self, attr, value) -> Any:
        return self.__smart__(attr, value, self.apply)

    def __make__(self, attr, value) -> Any:
        return self.__smart__(attr, value, self.make)

    # ------------------------------------------|

    final: bool = field(default=False, converter=bool)
    """Is this bound to the final FSSAA ShaderObject?"""

    track: float = field(default=0.0, converter=float, on_setattr=__make__)
    """Match the scene's resolution times this factor on this texture"""

    filter: TextureFilter = TextureFilter.Linear.field(on_setattr=__apply__)
    """The interpolation filter applied to the texture when sampling on the GPU"""

    anisotropy: Anisotropy = Anisotropy.x16.field(on_setattr=__apply__)
    """Anisotropic filter level, improves texture quality at oblique angles"""

    mipmaps: bool = field(default=False, converter=bool, on_setattr=__apply__)
    """Compute mipmaps for this texture, improves quality at large distances"""

    repeat_x: bool = field(default=True, converter=bool, on_setattr=__apply__)
    """Should the texture repeat on the X axis when out of bounds or clamp"""

    repeat_y: bool = field(default=True, converter=bool, on_setattr=__apply__)
    """Should the texture repeat on the Y axis when out of bounds or clamp"""

    def repeat(self, value: bool) -> Self:
        """Syntatic sugar for setting both repeat_x and repeat_y"""
        self.repeat_x = self.repeat_y = bool(value)
        return self.apply()

    @property
    def moderngl_filter(self) -> int:
        return dict(
            linear=moderngl.LINEAR,
            nearest=moderngl.NEAREST,
            linear_mipmap=moderngl.LINEAR_MIPMAP_LINEAR,
            nearest_mipmap=moderngl.NEAREST_MIPMAP_NEAREST,
        ).get(self.filter.value + ("_mipmap"*self.mipmaps))

    # ------------------------------------------|

    # Width

    _width: int = field(default=1, converter=int)

    @property
    def width(self) -> int:
        if not self.track:
            return self._width
        return self.resolution[0]

    @width.setter
    def width(self, value: int):
        if (self._width == value):
            return
        self._width = value
        self.make()

    # Height

    _height: int = field(default=1, converter=int)

    @property
    def height(self) -> int:
        if not self.track:
            return self._height
        return self.resolution[1]

    @height.setter
    def height(self, value: int):
        if (self._height == value):
            return
        self._height = value
        self.make()

    components: int = field(default=4, converter=int, on_setattr=__make__)
    """Number of color channels per pixel (1 Grayscale, 2 RG, 3 RGB, 4 RGBA)"""

    dtype: numpy.dtype = field(
        default=numpy.uint8,
        converter=numpy.dtype,
        on_setattr=__make__)
    """Data type of the texture for each pixel channel"""

    @property
    def resolution(self) -> Tuple[int, int]:
        if not self.track:
            return (self._width, self._height)
        def scale(data):
            return tuple(max(1, int(x*self.track)) for x in data)
        if self.final:
            return scale(self.scene.resolution)
        return scale(self.scene.render_resolution)

    @resolution.setter
    def resolution(self, value: Tuple[int, int]):
        if not self.track:
            self.width, self.height = value

    @property
    def size(self) -> Tuple[int, int]:
        return self.resolution

    @size.setter
    def size(self, value: Tuple[int, int]):
        self.resolution = value

    @property
    def aspect_ratio(self) -> float:
        return self.width/(self.height or 1)

    # Bytes size and Zero filling

    @property
    def zeros(self) -> numpy.ndarray:
        return numpy.zeros((*self.size, self.components), dtype=self.dtype)

    @property
    def size_t(self) -> int:
        """Size of the texture data in bytes"""
        return (self.width * self.height * self.bytes_per_pixel)

    @property
    def bytes_per_pixel(self) -> int:
        return (self.dtype.itemsize * self.components)

    # ------------------------------------------|

    matrix: Deque[Deque[TextureBox]] = Factory(deque)
    """Matrix of previous frames (temporal) and their layers (layers)"""

    temporal: int = field(default=1, converter=int, on_setattr=__make__)
    """Number of previous frames to be stored"""

    layers: int = field(default=1, converter=int, on_setattr=__make__)
    """Number of layers to be stored, useful in single-shader multipass"""

    @property
    def boxes(self) -> Iterable[Tuple[int, int, TextureBox]]:
        for t, temporal in enumerate(self.matrix):
            for b, box in enumerate(temporal):
                yield (t, b, box)

    def row(self, n: int=0) -> Iterable[TextureBox]:
        yield from self.matrix[n]

    def make(self) -> Self:
        if (max(self.size) > (limit := self.scene.opengl.info['GL_MAX_VIEWPORT_DIMS'][0])):
            raise Exception(f"Texture size too large for this OpenGL context: {self.size} > {limit}")

        # Populate the matrix with current size
        for row in pop_fill(self.matrix, deque, self.temporal):
            pop_fill(row, TextureBox, self.layers)

        # Recreate texture boxes
        for (_, _, box) in self.boxes:
            box.release()
            box.texture = self.scene.opengl.texture(
                components=self.components,
                dtype=numpy2mgltype(self.dtype),
                size=self.size)
            box.fbo = self.scene.opengl.framebuffer(
                color_attachments=[box.texture])

            # Rewrite previous data if same size
            if box.data and (self.size_t == len(box.data)):
                box.texture.write(box.data)

        return self.apply()

    def apply(self) -> Self:
        """Apply filters and flags to all textures"""
        for (_, _, box) in self.boxes:
            if self.mipmaps:
                box.texture.build_mipmaps()
            box.texture.filter     = (self.moderngl_filter, self.moderngl_filter)
            box.texture.anisotropy = self.anisotropy.value
            box.texture.repeat_x   = self.repeat_x
            box.texture.repeat_y   = self.repeat_y
        return self

    def get_box(self, temporal: int=0, layer: int=-1) -> Optional[TextureBox]:
        """Note: Points to the current final box"""
        return list_get(list_get(self.matrix, temporal), layer)

    @property
    def fbo(self) -> moderngl.Framebuffer:
        """Final and most Recent FBO of this Texture"""
        if (self.final and self.scene.realtime):
            return self.scene.window.fbo
        return self.get_box().fbo

    @property
    def texture(self) -> moderngl.Texture:
        """Final and most Recent Texture of this Texture"""
        return self.get_box().texture

    def roll(self, n: int=1) -> Self:
        """Rotate the temporal layers by $n times"""
        self.matrix.rotate(n)
        return self

    # ------------------------------------------|
    # Input and Output

    def write(self,
        data: bytes=None,
        *,
        temporal: int=0,
        layer: int=-1,
        viewport: Tuple[int, int, int, int]=None,
    ) -> Self:
        box = self.get_box(temporal, layer)
        box.texture.write(data, viewport=viewport)
        if (not viewport):
            box.data = bytes(data)
        box.empty = False
        return self

    def from_numpy(self, data: numpy.ndarray) -> Self:
        unpack = list(data.shape)
        if len(unpack) == 2:
            unpack.append(1)
        self._height, self._width, self.components = unpack
        self.dtype = data.dtype
        self.make()
        self.write(numpy.flip(data, axis=0).tobytes())
        return self

    def from_image(self, image: LoadableImage) -> Self:
        return self.from_numpy(numpy.array(LoaderImage(image)))

    def clear(self, temporal: int=0, layer: int=-1) -> Self:
        return self.write(self.zeros, temporal=temporal, layer=layer)

    def is_empty(self, temporal: int=0, layer: int=-1) -> bool:
        return self.get_box(temporal, layer).empty

    # Todo: Sampling functions with numpy index ranges

    # ------------------------------------------|
    # Module

    def _coord2name(self, temporal: int, layer: int) -> str:
        return f"{self.name}{temporal}x{layer}"

    def defines(self) -> Iterable[str]:
        if not self.name:
            return

        # Define last frames as plain name (iTex0x(-1) -> iTex, iTex1x(-1) -> iTex1)
        for temporal in range(self.temporal):
            yield f"#define {self.name}{temporal or ''} {self.name}{temporal}x{self.layers-1}"

        # Function to sample a dynamic temporal, layer
        yield f"\nvec4 {self.name}Texture(int temporal, int layer, vec2 astuv) {{"
        yield "    if (false) return vec4(0);"
        for temporal in range(self.temporal):
            for layer in range(self.layers):
                yield f"    else if (temporal == {temporal} && layer == {layer}) return texture({self._coord2name(temporal, layer)}, astuv);"
        yield "    else {return vec4(0);}"
        yield "}"

    def handle(self, message: ShaderMessage):
        if self.track and isinstance(message, ShaderMessage.Shader.RecreateTextures):
            self.make()

    def pipeline(self) -> Iterable[ShaderVariable]:
        if not self.name:
            return
        yield Uniform("int", "iLayer", None)
        yield Uniform("vec2",  f"{self.name}Size",     self.size)
        # yield Uniform("float", f"{self.name}AspectRatio", self.aspect_ratio)
        yield Uniform("int",   f"{self.name}Layers",   self.layers)
        yield Uniform("int",   f"{self.name}Temporal", self.temporal)
        for (t, b, box) in self.boxes:
            yield Uniform("sampler2D", self._coord2name(t, b), box.texture)

