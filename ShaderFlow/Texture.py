from collections import deque
from typing import Any, Deque, Iterable, List, Optional, Self, Tuple, Type, Union

import moderngl
import numpy
import PIL
from attr import Factory, define, field

from Broken import BrokenEnum, Nothing
from Broken.Loaders import LoadableImage, LoaderImage
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Variable import ShaderVariable, Uniform


def numpy2mgltype(type: Union[numpy.dtype, str]) -> str:
    if isinstance(type, str):
        return type
    if isinstance(type, numpy.dtype):
        type = type.type
    return {
        numpy.uint8:   "f1",
        numpy.float16: "f2",
        numpy.float32: "f4",
        numpy.uint16:  "u2",

        # Fixme: usampler2D, isampler2D?
        # numpy.uint32:  "u4",
        # numpy.int8:    "i1",
        # numpy.int16:   "i2",
        # numpy.int32:   "i4",
    }.get(type)

class TextureFilter(BrokenEnum):
    # Fixme: Disallow bad combinations of filter and types
    Nearest = "nearest"
    Linear  = "linear"

class Anisotropy(BrokenEnum):
    """Anisotropy levels to use on textures"""
    x1  = 1
    x2  = 2
    x4  = 4
    x8  = 8
    x16 = 16

@define
class TextureBox:
    """Holds a Framebuffer and bound Texture on the TextureMatrix"""
    texture: moderngl.Texture = None
    fbo:     moderngl.Framebuffer = None
    clear:   bool  = False
    data:    bytes = field(default=None, repr=False)
    empty:   bool  = True

    def release(self) -> Self:
        (self.texture or Nothing()).release()
        (self.fbo     or Nothing()).release()

@define
class ShaderTexture(ShaderModule):
    name: str = None

    def __post__(self):
        self.make()
        self.apply()

    # ------------------------------------------|
    # Special

    final: bool = field(default=False, converter=bool)
    """Is this bound to the final FSSAA ShaderObject?"""

    _track: bool = field(default=False, converter=bool)
    """Should this ShaderTexture match the resolution of the Scene?"""

    @property
    def track(self) -> bool:
        return self._track

    @track.setter
    def track(self, value: bool):
        if (self._track == value):
            return
        self._track = value
        self.make()

    # ------------------------------------------|

    # Filter

    _filter: TextureFilter = TextureFilter.Linear

    @property
    def filter(self) -> TextureFilter:
        return TextureFilter.get(self._filter)

    @filter.setter
    def filter(self, value: TextureFilter):
        self._filter = TextureFilter.get(value)
        self.apply()

    # Anisotropy

    _anisotropy: Anisotropy = Anisotropy.x16

    @property
    def anisotropy(self) -> Anisotropy:
        return Anisotropy.get(self._anisotropy)

    @anisotropy.setter
    def anisotropy(self, value: Anisotropy):
        self._anisotropy = Anisotropy.get(value)
        self.apply()

    # Mipmaps

    _mipmaps: bool = field(default=False, converter=bool)

    @property
    def mipmaps(self) -> bool:
        return self._mipmaps

    @mipmaps.setter
    def mipmaps(self, value: bool):
        if (self._mipmaps == value):
            return
        self._mipmaps = value
        self.apply()

    # ModernGL Filter

    @property
    def moderngl_filter(self) -> int:
        return dict(
            linear=moderngl.LINEAR,
            nearest=moderngl.NEAREST,
            linear_mipmap=moderngl.LINEAR_MIPMAP_LINEAR,
            nearest_mipmap=moderngl.NEAREST_MIPMAP_NEAREST,
        ).get(self.filter.value + ("_mipmap"*self.mipmaps))

    # Dtype

    _dtype: numpy.dtype = numpy.uint8

    @property
    def dtype(self) -> numpy.dtype:
        return self._dtype

    @dtype.setter
    def dtype(self, value: numpy.dtype):
        self._dtype = value
        self.make()

    # Repeat X

    _repeat_x: bool = field(default=True, converter=bool)

    @property
    def repeat_x(self) -> bool:
        return self._repeat_x

    @repeat_x.setter
    def repeat_x(self, value: bool):
        if (self._repeat_x == value):
            return
        self._repeat_x = value
        self.apply()

    # Repeat Y

    _repeat_y: bool = field(default=True, converter=bool)

    @property
    def repeat_y(self) -> bool:
        return self._repeat_y

    @repeat_y.setter
    def repeat_y(self, value: bool):
        if (self._repeat_y == value):
            return
        self._repeat_y = value
        self.apply()

    # Repeat XY

    def repeat(self, value: bool) -> Self:
        self.repeat_x = self.repeat_y = bool(value)
        return self.apply()

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
        value = int(value)
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
        value = int(value)
        if (self._height == value):
            return
        self._height = value
        self.make()

    # Size (Width, Height)

    @property
    def resolution(self) -> Tuple[int, int]:
        if not self.track:
            return (self.width, self.height)
        if self.final:
            return self.scene.resolution
        return self.scene.render_resolution

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

    # Components

    _components: int = field(default=4, converter=int)

    @property
    def components(self) -> int:
        """Number of color channels per pixel (1 Grayscale, 2 RG, 3 RGB, 4 RGBA)"""
        return self._components

    @components.setter
    def components(self, value: int):
        if (self._components == value):
            return
        self._components = value
        self.make()

    # Bytes size and Zero filling

    @property
    def zeros(self) -> numpy.ndarray:
        return numpy.zeros((*self.size, self.components), dtype=self.dtype)

    @property
    def size_t(self) -> int:
        """Size of the texture data in bytes (width * height * components)"""
        return self.width * self.height * self.components

    # ------------------------------------------|

    # Matrix

    _matrix: Deque[Deque[TextureBox]] = Factory(deque)
    """Matrix of previous frames (temporal) and their layers (layers)"""

    @property
    def matrix(self) -> Deque[Deque[TextureBox]]:
        return self._matrix

    # Temporal

    _temporal: int = field(default=1, converter=int)
    """Number of previous frames to be stored"""

    @property
    def temporal(self) -> int:
        return self._temporal

    @temporal.setter
    def temporal(self, value: int):
        if (self._temporal == value):
            return
        self._temporal = value
        self.make()

    # Layers

    _layers: int = field(default=1, converter=int)
    """Number of layers to be stored, useful in single-shader multipass"""

    @property
    def layers(self) -> int:
        return self._layers

    @layers.setter
    def layers(self, value: int):
        if (self._layers == value):
            return
        self._layers = value
        self.make()

    # ------------------------------------------|

    def _pop_fill(self, list: Union[List, Deque], fill: Type[Any], length: int) -> List:
        """Pop right or fill until a list's length is met"""
        while len(list) > length:
            list.pop()
        while len(list) < length:
            list.append(fill())
        return list

    def _populate(self) -> Iterable[Tuple[int, int, TextureBox]]:
        self._pop_fill(self.matrix, deque, self.temporal)
        for row in self.matrix:
            self._pop_fill(row, TextureBox, self.layers)
        return self.boxes

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

        # Recreate texture boxes to match new length
        for (_, _, box) in self.boxes:
            box.release()
        for (_, _, box) in self._populate():
            box.texture = self.scene.opengl.texture(
                components=self.components,
                dtype=numpy2mgltype(self.dtype),
                size=self.size,
            )
            box.fbo = self.scene.opengl.framebuffer(
                color_attachments=[box.texture]
            )
        return self.apply()

    def apply(self) -> Self:
        for (_, _, box) in self.boxes:
            if self.mipmaps:
                box.texture.build_mipmaps()
            box.texture.filter     = (self.moderngl_filter, self.moderngl_filter)
            box.texture.anisotropy = self.anisotropy.value
            box.texture.repeat_x   = self.repeat_x
            box.texture.repeat_y   = self.repeat_y
        return self

    def box(self, temporal: int=0, layer: int=-1) -> Optional[TextureBox]:
        """Note: Points to the current final box"""
        if (self.temporal <= temporal):
            return None
        if (self.layers <= layer):
            return None
        return self.matrix[temporal][layer]

    def fbo(self) -> moderngl.Framebuffer:
        """Final and most Recent FBO of this Texture"""
        if self.final and self.scene.realtime:
            return self.scene.window.fbo
        return self.box().fbo

    def texture(self) -> moderngl.Texture:
        """Final and most Recent Texture of this Texture"""
        return self.box().texture

    def roll(self, n: int=1) -> Self:
        """Rotate the temporal layers by $n times"""
        self.matrix.rotate(n)
        return self

    # ------------------------------------------|
    # Input and Output

    # Fixme: Convert uint16+ and int8+ to float32?
    def from_numpy(self, data: numpy.ndarray) -> Self:
        unpack = list(data.shape)
        if len(unpack) == 2:
            unpack.append(1)
        self._height, self._width, self._components = unpack
        self._dtype = data.dtype
        self.make()
        self.write(numpy.flip(data, axis=0).tobytes())
        return self

    def from_image(self, image: LoadableImage) -> Self:
        return self.from_numpy(numpy.array(LoaderImage(image)))

    def write(self,
        data: bytes=None,
        *,
        temporal: int=0,
        layer: int=-1,
        viewport: Tuple[int, int, int, int]=None,
    ) -> Self:
        box = self.box(temporal, layer)
        box.texture.write(data, viewport=viewport)
        if not viewport:
            box.data = bytes(data)
        box.empty = False
        return self

    def clear(self, temporal: int=0, layer: int=-1) -> Self:
        return self.write(self.zeros, temporal=temporal, layer=layer)

    def is_empty(self, temporal: int=0, layer: int=-1) -> bool:
        return self.box(temporal, layer).empty

    # ------------------------------------------|

    @property
    def bytes_per_pixel(self) -> int:
        return self.dtype.nbytes * self.components

    def sample_xy(self, x: float, y: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a XY coordinate: Origin at Top Right (0, 0); Bottom Left (width, height)"""
        box   = self.box(temporal=temporal, layer=layer)
        data  = (box.data or box.texture.read())
        start = int((y*self.width + x) * self.bytes_per_pixel)
        return numpy.frombuffer(data, dtype=self.dtype)[start:start + self.bytes_per_pixel]

    def sample_stxy(self, x: float, y: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a XY coordinate: Origin at Bottom left (0, 0); Top right (width, height)"""
        return self.sample_xy(x=x, y=(self.height - y - 1), temporal=temporal, layer=layer)

    def sample_glxy(self, x: float, y: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a XY coordinate: Origin at Center (0, 0); Any Edge either (±w/2, 0), (0, ±h/2)"""
        return self.sample_xy(x=int(x + (self.width/2)), y=int(y + (self.height/2)), temporal=temporal, layer=layer)

    def sample_uv(self, u: float, v: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a UV coordinate: Origin at Top Right (0, 0); Bottom Left (1, 1)"""
        return self.sample_xy(u*self.width, v*self.height, temporal=temporal, layer=layer)

    def sample_stuv(self, u: float, v: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a UV coordinate: Origin at Bottom Left (0, 0); Top Right (1, 1)"""
        return self.sample_uv(u=u, v=(1-v), temporal=temporal, layer=layer)

    def sample_gluv(self, u: float, v: float, temporal: int=0, layer: int=-1) -> numpy.ndarray:
        """Get the Pixel at a UV coordinate: Origin at Center (0, 0); Any Edge either (±1, 0), (0, ±1)"""
        return self.sample_uv(u=(u/2 + 0.5), v=(v/2 + 0.5), temporal=temporal, layer=layer)

    # ------------------------------------------|
    # Module

    def _coord2name(self, old: int, layer: int) -> str:
        return f"{self.name}{old}x{layer}"

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
        if self.track:
            if isinstance(message, ShaderMessage.Shader.RecreateTextures):
                self.make()

    def pipeline(self) -> Iterable[ShaderVariable]:
        if not self.name:
            return
        yield Uniform("int", "iLayer", None)
        yield Uniform("vec2",  f"{self.name}Size",        self.size)
        yield Uniform("float", f"{self.name}AspectRatio", self.aspect_ratio)
        yield Uniform("int",   f"{self.name}Layers",      self.layers)
        yield Uniform("int",   f"{self.name}Temporal",    self.temporal)
        for (t, b, box) in self.boxes:
            yield Uniform("sampler2D", self._coord2name(t, b), box.texture)

