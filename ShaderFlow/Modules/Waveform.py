from . import *


class WaveformReducer(BrokenEnum):
    Average = (lambda x: numpy.mean(numpy.abs(x), axis=2))
    RMS     = (lambda x: numpy.sqrt(numpy.mean(x**2, axis=2))*SQRT2)
    STD     = (lambda x: numpy.std(x, axis=2))


@define
class ShaderWaveform(ShaderModule):
    name:    str             = "iWaveform"
    texture: Texture         = None
    audio:   BrokenAudio     = Factory(BrokenAudio)
    reducer: WaveformReducer = WaveformReducer.STD
    smooth:  bool    = False
    points:  int     = 400
    slice:   Seconds = 1/100

    def __post__(self):
        self.texture = ShaderTexture(
            scene=self.scene,
            name=self.name,
            height=1,
            mipmaps=False,
            dtype=TextureType.f4,
        )

    @property
    def chunk(self) -> Samples:
        return int(self.slice*self.audio.samplerate)

    @property
    def offset(self) -> int:
        return self.audio.read % self.chunk

    @property
    def cutoff(self) -> Samples:
        return BrokenUtils.round(
            number=self.audio.buffer_size - self.offset,
            multiple=self.chunk,
            operation=math.floor,
            type=int,
        )

    def update(self):
        self.texture.filter     = ("linear" if self.smooth else "nearest")
        self.texture.components = self.audio.channels
        self.texture.width      = self.points
        start  = -(self.chunk*self.points + self.offset + 1)
        end    = -(self.offset + 1)
        chunks = self.audio.data[:, start:end]
        chunks = chunks.reshape(self.audio.channels, -1, self.chunk)
        chunks = self.reducer(chunks)
        chunks = numpy.ascontiguousarray(chunks.T)
        self.texture.write(chunks)
