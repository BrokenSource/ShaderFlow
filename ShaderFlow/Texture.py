from __future__ import annotations

import ShaderFlow

from . import *


class TextureType(BrokenEnum):

    # Float
    f1 = numpy.uint8
    f2 = numpy.uint8
    f4 = numpy.float32

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


class Anisotropy(BrokenEnum):
    """Anisotropy levels to use on textures"""
    x1  = 1
    x2  = 2
    x4  = 4
    x8  = 8
    x16 = 16


@define
class TextureContainer:
    texture: moderngl.Texture = None
    fbo:     moderngl.Framebuffer = None
    clear:   bool  = False
    data:    bytes = None
    empty:   bool  = True

    def release(self) -> Self:
        (self.texture or Ignore()).release()
        (self.fbo     or Ignore()).release()


class TextureFilter(BrokenEnum):
    # Note: _mipmap is automatic
    Nearest = "nearest"
    Linear  = "linear"


@define
class Texture(Module):
    name: str = "iTexture"

    # ------------------------------------------|
    # Initiating textures

    @property
    def zeros(self) -> bytes:
        return numpy.zeros((*self.size, self.components), dtype=self.dtype.value)

    def make(self) -> Self:

        # Pop right and fill until length is correct
        while len(self._stack) > self.layers:
            self._stack.pop()
        while len(self._stack) < self.layers:
            self._stack.append(TextureContainer())

        # Create many containers
        for this in self._stack:
            log.debug(f"{self.who} Creating texture for {self.name}")
            log.debug(f"{self.who} • Size:    {self.size}")
            log.debug(f"{self.who} • Channel: {self.components}")
            log.debug(f"{self.who} • dtype:   {self.dtype}")
            log.debug(f"{self.who} • Layers:  {self.layers}")
            log.debug(f"{self.who} • Repeat:  ({self.repeat_x}, {self.repeat_y})")
            log.debug(f"{self.who} • Filter:  {self.filter}")
            log.debug(f"{self.who} • Aniso:   {self.anisotropy}")
            log.debug(f"{self.who} • Mipmaps: {self.mipmaps}")
            log.debug(f"{self.who} • Track:   {self.track}")
            log.debug(f"{self.who} • Final:   {self.final}")
            this.release()
            this.texture = self.scene.opengl.texture(
                data=this.data,# or self.zeros,
                components=self.components,
                dtype=TextureType.get(self.dtype).name,
                size=self.size,
            )
            this.fbo = self.scene.opengl.framebuffer(
                color_attachments=[this.texture]
            )

        self.apply()
        return self

    def __post__(self):
        self.make()
        self.apply()

    def _make(self, field, value) -> Any:
        if self.__dict__.get(field.name) == value:
            return value
        self.__dict__[field.name] = value
        self.make()
        return value

    def rotate(self, n: int=1) -> None:
        if not self.rolling:
            return
        self._stack.rotate(n)

    # ------------------------------------------|
    # Applying Filters

    @property
    def moderngl_filter(self) -> int:
        return dict(
            linear=moderngl.LINEAR,
            nearest=moderngl.NEAREST,
            linear_mipmap=moderngl.LINEAR_MIPMAP_LINEAR,
            nearest_mipmap=moderngl.NEAREST_MIPMAP_NEAREST,
        ).get(self.filter.value + ("_mipmap"*self.mipmaps))

    def apply(self) -> Self:
        for container in self._stack:
            texture = container.texture
            Maybe(texture.build_mipmaps, self.mipmaps)
            texture.filter     = (self.moderngl_filter, self.moderngl_filter)
            texture.anisotropy = self.anisotropy.value
            texture.repeat_x   = self.repeat_x
            texture.repeat_y   = self.repeat_y
        return self

    def _apply(self, field, value) -> Any:
        if self.__dict__.get(field.name) == value:
            return value
        self.__dict__[field.name] = value
        self.apply()
        return value

    # ------------------------------------------|
    # Properties

    filter:     TextureFilter = TextureFilter.Linear.Field(on_setattr=_apply)
    anisotropy: Anisotropy    = Anisotropy.x16.Field(on_setattr=_apply)
    dtype:      TextureType   = TextureType.f1.Field(on_setattr=_apply)
    mipmaps:    bool = Field(default=False, converter=bool, on_setattr=_apply)
    repeat_x:   bool = Field(default=True,  converter=bool, on_setattr=_apply)
    repeat_y:   bool = Field(default=True,  converter=bool, on_setattr=_apply)
    components: int  = Field(default=4,     converter=int,  on_setattr=_make)
    layers:     int  = Field(default=1,     converter=int,  on_setattr=_make)
    width:      int  = Field(default=1,     converter=int,  on_setattr=_make)
    height:     int  = Field(default=1,     converter=int,  on_setattr=_make)
    final:      bool = Field(default=False, converter=bool, on_setattr=_make)
    track:      bool = Field(default=False, converter=bool, on_setattr=_make)
    rolling:    bool = Field(default=False, converter=bool)
    _stack:     Deque[TextureContainer] = Factory(deque)

    def repeat(self, value: bool) -> Self:
        self.repeat_x = self.repeat_y = value
        return self

    def _get_stack(self, index: int=0) -> Optional[TextureContainer]:
        return self._stack[index] if (index < len(self._stack)) else None

    def __getitem__(self, index: int) -> Optional[TextureContainer]:
        return self._get_stack(index)

    def texture(self, index: int=0) -> Optional[moderngl.Texture]:
        if (container := self._get_stack(index)):
            return container.texture

    def fbo(self, index: int=0) -> Optional[moderngl.Framebuffer]:
        if (index == 0) and self.final and self.scene.realtime:
            return self.scene.opengl.screen
        if (container := self._get_stack(index)):
            return container.fbo

    @property
    def resolution(self) -> Tuple[int, int]:
        if not self.track:
            return (self.width, self.height)
        if self.final:
            self.scene.resolution
        return self.scene.render_resolution

    @property
    def size(self) -> Tuple[int, int]:
        return self.resolution

    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        if self.track or self.final:
            return
        self.width, self.height = value

    @size.setter
    def size(self, value: Tuple[int, int]) -> None:
        self.resolution = value

    @property
    def aspect_ratio(self) -> float:
        return self.width / (self.height or 1)

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
        print("Got dtype", f"{alpha[0]}{int(number)//8}", self.dtype)

        self.make()
        self.write(data)
        return self

    def write(self,
        data: bytes=None,
        *,
        layer: int=0,
        viewport: Tuple[int, int, int, int]=None,
    ) -> Self:
        container = self._stack[layer]
        container.texture.write(data, viewport=viewport)
        if viewport: container.data = data
        container.empty = False
        return self

    def clear(self, layer: int=0) -> Self:
        return self.write(self.zeros, layer=layer)

    def read(self, *args, **kwargs) -> bytes:
        return self.texture.read(*args, **kwargs)

    def is_empty(self, layer: int=0) -> bool:
        return self._stack[layer].empty

    def pipeline(self) -> Iterable[ShaderVariable]:
        for index, container in enumerate(self._stack):
            yield ShaderVariable("uniform", "sampler2D", f"{self.name}{index or ''}", container.texture)
        yield ShaderVariable("uniform", "vec2",  f"{self.name}Size",        self.size)
        yield ShaderVariable("uniform", "float", f"{self.name}AspectRatio", self.aspect_ratio)
        yield ShaderVariable("uniform", "int",   f"iLayer",                 0)
