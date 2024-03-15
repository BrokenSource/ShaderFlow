from . import *


class WaveformReducer(BrokenEnum):
    Average = (lambda x: numpy.sqrt(numpy.mean(numpy.abs(x), axis=2)))
    RMS     = (lambda x: numpy.sqrt(numpy.sqrt(numpy.mean(x**2, axis=2))*SQRT2))
    STD     = (lambda x: numpy.sqrt(numpy.std(x, axis=2)))

@define
class ShaderWaveform(ShaderModule):

    name: str = "iWaveform"
    """Prefix name and Texture name of the Shader Variables"""

    audio: BrokenAudio = None
    """Audio class to read the data from"""

    length: Seconds = 3
    """Horizontal length of the Waveform content"""

    samplerate: Hertz = 180
    """Number of bars per second"""

    reducer: WaveformReducer = WaveformReducer.RMS
    """How to convert a (channels, length, samples) chunks into (channels, length)"""

    smooth: bool = False
    """Enables Linear interpolation on the Texture, not much useful for Bars mode"""

    texture: ShaderTexture = None
    """Internal managed Texture"""

    @property
    def length_samples(self) -> Samples:
        return int(max(1, self.length*self.scene.fps))

    def __post__(self):
        self.texture = ShaderTexture(
            scene=self.scene,
            name=self.name,
            height=1,
            mipmaps=False,
            dtype=TextureType.f4,
        )

    @property
    def chunk_size(self) -> Samples:
        return max(1, int(self.length*self.audio.samplerate/self.points))

    @property
    def points(self) -> int:
        return self.length*self.samplerate

    @property
    def offset(self) -> int:
        return self.audio.read % self.chunk_size

    @property
    def cutoff(self) -> Samples:
        return BrokenUtils.round(
            number=self.audio.buffer_size,
            multiple=self.chunk_size,
            operation=math.floor,
            type=int,
        )

    __same__: SameTracker = Factory(SameTracker)

    def update(self):
        self.texture.filter     = ("linear" if self.smooth else "nearest")
        self.texture.components = self.audio.channels
        self.texture.width      = self.points
        if self.__same__(self.audio.read):
            return
        start  = -(self.chunk_size*self.points + self.offset + 1)
        end    = -(self.offset + 1)
        chunks = self.audio.data[:, start:end]
        chunks = chunks.reshape(self.audio.channels, -1, self.chunk_size)
        chunks = self.reducer(chunks)
        chunks = numpy.ascontiguousarray(chunks.T)
        self.texture.write(chunks)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int", f"{self.name}Length", self.length_samples)
