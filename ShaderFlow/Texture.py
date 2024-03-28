from __future__ import annotations

import re
from collections import deque
from typing import Any, Deque, Iterable, List, Optional, Self, Tuple, Type, Union

import moderngl
import numpy
import PIL
from attr import Factory, define, field

from Broken.Base import Ignore, Maybe
from Broken.BrokenEnum import BrokenEnum
from Broken.Loaders.LoaderPIL import LoadableImage, LoaderImage
from ShaderFlow.Message import Message
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Variable import ShaderVariable


class TextureType(BrokenEnum):

    # Float
    f1 = numpy.uint8
    """Alias for uint8, GL_UNSIGNED_BYTE"""
    f2 = numpy.float16
    """Float16 bits = 2 bytes, GL_HALF_FLOAT"""
    f4 = numpy.float32
    """Float32 bits = 4 bytes, GL_FLOAT"""

    # # Integers

    # Normal
    u1 = numpy.uint8
    u2 = numpy.uint16
    u4 = numpy.uint32
    i1 = numpy.int8
    i2 = numpy.int16
    i4 = numpy.int32

    # Normalized
    nu1 = numpy.uint8
    nu2 = numpy.uint16
    nu4 = numpy.uint32
    ni1 = numpy.int8
    ni2 = numpy.int16
    ni4 = numpy.int32

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
    """Holds a Framebuffer and bound Texture on the Matrix"""
    texture: moderngl.Texture = None
    fbo:     moderngl.Framebuffer = None
    clear:   bool  = False
    data:    bytes = None
    empty:   bool  = True

    def release(self) -> Self:
        (self.texture or Ignore()).release()
        (self.fbo     or Ignore()).release()

@define
class ShaderTexture(ShaderModule):
    name: str = None

    def __post__(self):
        self.make()
        self.apply()

    # ------------------------------------------|
    # Filters, Types Repeat, Mipmaps

    _filter: TextureFilter = TextureFilter.Linear

    @property
    def filter(self) -> TextureFilter:
        return TextureFilter.get(self._filter)
    @filter.setter
    def filter(self, value: TextureFilter):
        self._filter = TextureFilter.get(value)
        self.apply()

    _anisotropy: Anisotropy = Anisotropy.x16

    @property
    def anisotropy(self) -> Anisotropy:
        return Anisotropy.get(self._anisotropy)
    @anisotropy.setter
    def anisotropy(self, value: Anisotropy):
        self._anisotropy = Anisotropy.get(value)
        self.apply()

    @property
    def moderngl_filter(self) -> int:
        return dict(
            linear=moderngl.LINEAR,
            nearest=moderngl.NEAREST,
            linear_mipmap=moderngl.LINEAR_MIPMAP_LINEAR,
            nearest_mipmap=moderngl.NEAREST_MIPMAP_NEAREST,
        ).get(self.filter.value + ("_mipmap"*self.mipmaps))

    _dtype: TextureType = TextureType.f4

    @property
    def dtype(self) -> TextureType:
        return TextureType.get(self._dtype)
    @dtype.setter
    def dtype(self, value: TextureType):
        self._dtype = TextureType.get(value)
        self.make()

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

    _repeat_x: bool = field(default=True, converter=bool)
    _repeat_y: bool = field(default=True, converter=bool)

    @property
    def repeat_x(self) -> bool:
        return self._repeat_x
    @property
    def repeat_y(self) -> bool:
        return self._repeat_y

    @repeat_x.setter
    def repeat_x(self, value: bool):
        if (self._repeat_x == value):
            return
        self._repeat_x = value
        self.apply()
    @repeat_y.setter
    def repeat_y(self, value: bool):
        if (self._repeat_y == value):
            return
        self._repeat_y = value
        self.apply()

    def repeat(self, value: bool) -> Self:
        self.repeat_x = self.repeat_y = bool(value)
        return self.apply()

    # ------------------------------------------|
    # Resolution

    _width:  int = field(default=1, converter=int)
    _height: int = field(default=1, converter=int)

    @property
    def width(self) -> int:
        if not self.track:
            return self._width
        return self.resolution[0]
    @property
    def height(self) -> int:
        if not self.track:
            return self._height
        return self.resolution[1]

    @width.setter
    def width(self, value: int):
        value = int(value)
        if (self._width == value):
            return
        self._width = value
        self.make()
    @height.setter
    def height(self, value: int):
        value = int(value)
        if (self._height == value):
            return
        self._height = value
        self.make()

    @property
    def aspect_ratio(self) -> float:
        return self.width/(self.height or 1)

    @property
    def resolution(self) -> Tuple[int, int]:
        if not self.track:
            return (self.width, self.height)
        if self.final:
            return self.scene.resolution
        return self.scene.render_resolution

    @property
    def size(self) -> Tuple[int, int]:
        return self.resolution

    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        if not self.track:
            self.width, self.height = value

    @size.setter
    def size(self, value: Tuple[int, int]) -> None:
        self.resolution = value

    _components: int = field(default=4, converter=int)

    @property
    def components(self) -> int:
        return self._components
    @components.setter
    def components(self, value: int):
        if (self._components == value):
            return
        self._components = value
        self.make()

    _track: bool = field(default=False, converter=bool)

    @property
    def track(self) -> bool:
        return self._track
    @track.setter
    def track(self, value: bool):
        if (self._track == value):
            return
        self._track = value
        self.make()

    @property
    def zeros(self) -> numpy.ndarray:
        return numpy.zeros((*self.size, self.components), dtype=self.dtype.value)

    @property
    def length(self) -> int:
        """Length of the texture in bytes"""
        return self.width * self.height * self.components

    # ------------------------------------------|
    # Matrix and Special

    _temporal: int = field(default=1, converter=int)

    @property
    def temporal(self) -> int:
        return self._temporal
    @temporal.setter
    def temporal(self, value: int):
        if (self._temporal == value):
            return
        self._temporal = value
        self.make()

    _layers: int = field(default=1, converter=int)

    @property
    def layers(self) -> int:
        return self._layers
    @layers.setter
    def layers(self, value: int):
        if (self._layers == value):
            return
        self._layers = value
        self.make()

    _matrix: Deque[Deque[TextureBox]] = Factory(deque)

    @property
    def matrix(self) -> Deque[Deque[TextureBox]]:
        return self._matrix

    _final: bool = field(default=False, converter=bool)

    @property
    def final(self) -> bool:
        return self._final
    @final.setter
    def final(self, value: bool):
        self._final = value

    # ------------------------------------------|
    # Matrix operations

    def _pop_fill(self, list: Union[List, Deque], fill: Type[Any], length: int) -> List:
        """Pop right or fill until a list's length is met"""
        while len(list) > length:
            list.pop()
        while len(list) < length:
            list.append(fill())
        return list

    def _populate(self) -> Self:
        self._pop_fill(self.matrix, deque, self.temporal)
        for row in self.matrix:
            self._pop_fill(row, TextureBox, self.layers)

    @property
    def boxes(self) -> Iterable[Tuple[int, int, TextureBox]]:
        for T, temporal in enumerate(self.matrix):
            for B, box in enumerate(temporal):
                yield (T, B, box)

    def make(self) -> Self:
        self._populate()
        for (_, _, Box) in self.boxes:
            Box.release()
            Box.texture = self.scene.opengl.texture(
                components=self.components,
                dtype=self.dtype.name,
                size=self.size,
            )
            Box.fbo = self.scene.opengl.framebuffer(
                color_attachments=[Box.texture]
            )
        return self.apply()

    def apply(self) -> Self:
        for (_, _, Box) in self.boxes:
            Maybe(Box.texture.build_mipmaps, self.mipmaps)
            Box.texture.filter     = (self.moderngl_filter, self.moderngl_filter)
            Box.texture.anisotropy = self.anisotropy.value
            Box.texture.repeat_x   = self.repeat_x
            Box.texture.repeat_y   = self.repeat_y
        return self

    def get_box(self, temporal: int=0, layer: int=-1) -> Optional[TextureBox]:
        """Note: Points to the current final box"""
        if (self.temporal <= temporal):
            return
        if (self.layers <= layer):
            return
        return self.matrix[temporal][layer]

    def fbo(self) -> moderngl.Framebuffer:
        """Final and most Recent FBO of this Texture"""
        if self.final and self.scene.realtime:
            return self.scene.opengl.screen
        return self.get_box().fbo

    def texture(self) -> moderngl.Texture:
        """Final and most Recent Texture of this Texture"""
        return self.get_box().texture

    def roll(self, n: int=1) -> Self:
        self.matrix.rotate(n)
        return self

    # ------------------------------------------|
    # Input and Output

    def from_image(self, image: LoadableImage) -> Self:
        image = LoaderImage(image)
        image = image.transpose(PIL.Image.FLIP_TOP_BOTTOM)
        self.width, self.height = image.size
        self.components = len(image.getbands())
        self.dtype = TextureType.get(numpy.array(image).dtype.str[1:].replace("u", "f"))
        self.make()
        self.write(image.tobytes())
        return self

    def from_numpy(self, data: numpy.ndarray) -> Self:
        size = data.shape
        if len(size) == 3:
            components = size[2]
            size = size[:2][::-1]
        else:
            components = 1
        self.width, self.height = size
        self.components = components

        # Get proper numpy dtype "float32" -> "f4"
        # Split until the number, can be float, int, double
        alpha, number = re.match(r"([a-z]+)(\d+)", str(data.dtype)).groups()
        self.dtype = TextureType.get(f"{alpha[0]}{int(number)//8}")
        # print("Got dtype", f"{alpha[0]}{int(number)//8}", self.dtype)

        self.make()
        self.write(data)
        return self

    def write(self,
        data: bytes=None,
        *,
        temporal: int=0,
        layer: int=-1,
        viewport: Tuple[int, int, int, int]=None,
    ) -> Self:
        Box = self.get_box(temporal, layer)
        Box.texture.write(data, viewport=viewport)
        if not viewport:
            Box.data = data
        Box.empty = False
        return self

    def clear(self, temporal: int=0, layer: int=-1) -> Self:
        return self.write(self.zeros, temporal=temporal, layer=layer)

    def is_empty(self, temporal: int=0, layer: int=-1) -> bool:
        return self.get_box(temporal, layer).empty

    # ------------------------------------------|
    # Module

    def _coord2name(self, old: int, layer: int) -> str:
        return f"{self.name}{old}x{layer}"

    def defines(self) -> Iterable[str]:
        # Define last frames as plain name (iTex0x(-1) -> iTex, iTex1x(-1) -> iTex1)
        for old in range(self.temporal):
            yield f"#define {self.name}{old or ''} {self.name}{old}x{self.layers-1}"

    def handle(self, message: Message):
        if self.track:
            if isinstance(message, Message.Window.Resize):
                self.make()
            elif isinstance(message, Message.Shader.RecreateTextures):
                self.make()

    def pipeline(self) -> Iterable[ShaderVariable]:
        if not self.name:
            return

        # Common
        yield ShaderVariable("uniform", "vec2",  f"{self.name}Size",        self.size)
        yield ShaderVariable("uniform", "float", f"{self.name}AspectRatio", self.aspect_ratio)
        yield ShaderVariable("uniform", "int",   f"{self.name}Layers",      self.layers)
        yield ShaderVariable("uniform", "int",   f"{self.name}Temporal",    self.temporal)

        # Matrix
        for (T, B, Box) in self.boxes:
            yield ShaderVariable("uniform", "sampler2D", self._coord2name(T, B), Box.texture)

        # Special
        yield ShaderVariable("uniform", "int", "iLayer", 0)
