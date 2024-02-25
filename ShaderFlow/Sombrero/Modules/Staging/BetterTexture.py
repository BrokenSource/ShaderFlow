from .. import *


class SombreroTextureDtype(BrokenEnum):

    # Float
    f1 = numpy.float32
    f2 = numpy.float16
    f4 = numpy.float64

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


@define
class SombreroTextureContainer:
    texture: moderngl.Texture = None
    fbo:     moderngl.Framebuffer = None
    data:    bytes = None


@define
class BetterTexture:

    # ------------------------------------------|
    # Initiating textures

    def __attrs_post_init__(self):
        self.__make__()

    @property
    def zeros(self) -> bytes:
        return numpy.zeros((*self.size, self.components), dtype=self.dtype).tobytes()

    def __make__(self) -> None:
        if not self.__do_make__:
            return

        # Pop right and fill until length is correct
        while len(self.stack) > self.layers:
            self.stack.pop()
        while len(self.stack) < self.layers:
            self.stack.append(SombreroTextureContainer())

        # Create many containers
        for this in self.stack:
            this.texture = self.scene.opengl.texture(
                data=this.data or self.zeros,
                components=self.components,
                dtype=self.dtype,
                size=self.size,
            )
            this.fbo = self.scene.opengl.framebuffer(color_attachments=[this.texture])

        self.__apply__()

    def rotate(self, n: int) -> None:
        self.stack.rotate(n)

    # ------------------------------------------|
    # Applying Filters

    @property
    def moderngl_filter(self) -> int:
        return dict(
            linear=moderngl.LINEAR,
            nearest=moderngl.NEAREST,
            linear_mipmap=moderngl.LINEAR_MIPMAP_LINEAR,
            nearest_mipmap=moderngl.NEAREST_MIPMAP_NEAREST,
        ).get(self.filter.value + ("_mipmap" * self.mipmaps))

    def __apply__(self, *ig, **nore):
        for texture in self.stack:
            texture.build_mipmaps() if self.mipmaps else None
            texture.filter     = (self.moderngl_filter,) * 2
            texture.anisotropy = self.anisotropy
            texture.repeat_x   = self.repeat
            texture.repeat_y   = self.repeat

    # ------------------------------------------|
    # Properties

    anisotropy: SombreroTextureAnisotropy = SombreroTextureAnisotropy.x16.Field(on_setattr=__apply__)
    filter:     SombreroTextureFilter     = SombreroTextureFilter.Linear .Field(on_setattr=__apply__)
    dtype:      numpy.dtype = Field(default=numpy.float32, converter=numpy.dtype, on_setattr=__make__)
    mipmaps:    bool = Field(default=True,  converter=bool, on_setattr=__apply__)
    repeat:     bool = Field(default=True,  converter=bool, on_setattr=__apply__)
    components: int  = Field(default=3,     converter=int,  on_setattr=__make__)
    layers:     int  = Field(default=1,     converter=int,  on_setattr=__make__)
    width:      int  = Field(default=1,     converter=int,  on_setattr=__make__)
    height:     int  = Field(default=1,     converter=int,  on_setattr=__make__)
    module:     bool = Field(default=False, converter=bool)
    stack:      Deque[SombreroTextureContainer] = Factory(deque)

    @property
    def texture(self) -> moderngl.Texture:
        return self.stack[0].texture

    @property
    def fbo(self) -> moderngl.Framebuffer:
        return self.stack[0].fbo

    @property
    def resolution(self) -> Tuple[int, int]:
        return self.width, self.height

    @resolution.setter
    def resolution(self, value: Tuple[int, int]) -> None:
        self.width, self.height = value

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    # ------------------------------------------|
    # Input and Output

    def write(self,
        data: bytes=None,
        *,
        layer: int=0,
        viewport: Tuple[int, int, int, int]=None,
    ) -> Self:
        container = self.stack[layer]
        container.data = container.texture.read() if viewport else data
        container.texture.write(data, viewport=viewport)

    def read(self, *args, **kwargs) -> bytes:
        return self.texture.read(*args, **kwargs)

    def __iter__(self) -> Iterable[ShaderVariable]:
        yield from (ShaderVariable(qualifier="uniform", type="sampler2D", name=f"{self.name}{i}") for i in range(self.layers))
        yield ShaderVariable(qualifier="uniform", type="vec2",  name=f"{self.name}Size",        value=self.size)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.name}AspectRatio", value=self.aspect_ratio)
