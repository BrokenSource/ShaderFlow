from . import *


@define
class SombreroSpectrogram(SombreroModule):
    audio:       BrokenAudio = None
    name:        str = "Spectrogram"
    spectrogram: BrokenAudioSpectrogram = None
    length:      int = 1024
    offset:      int = 0
    smooth:      bool = False
    texture:     SombreroTexture = None
    maximum:     SombreroDynamics = None
    minimum:     SombreroDynamics = None

    def __init__(self, audio, *args, **kwargs):
        self.__attrs_init__(audio=audio, *args, **kwargs)
        self.spectrogram = BrokenAudioSpectrogram(audio=self.audio)
        self.spectrogram.make_spectrogram_matrix()

    def __setup__(self) -> Self:
        self.maximum = self.add(SombreroDynamics(name=f"{self.name}Maximum", prefix=self.prefix, frequency=0.2))
        self.minimum = self.add(SombreroDynamics(name=f"{self.name}Minimum", prefix=self.prefix, frequency=0.2))
        self.texture = self.add(SombreroTexture(name=f"{self.prefix}{self.name}", mipmaps=False)).from_raw(
            size=(self.length, self.spectrogram.spectrogram_bins),
            components=self.audio.channels,
            dtype="f4",
        )
        self.texture.filter = "linear" if self.smooth else "nearest"
        return self

    def __update__(self):
        # Calculate next spectrogram, reshape to [(L, R), (L, R)...] "pixels", "fortran-style"
        data = self.spectrogram.spectrogram().T.reshape(2, -1)
        self.offset = (self.offset + 1) % self.length

        # Write spectrogram row to texture
        self.texture.write(data=data, viewport=(self.offset % self.length, 0, 1, self.spectrogram.spectrogram_bins))

        # Update maximum and minimum
        self.maximum.target = numpy.max(data) * 1.3
        self.minimum.target = numpy.min(data) * 1.3

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}{self.name}Length", value=self.length)
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}{self.name}Bins",   value=self.spectrogram.fft_size)
        yield ShaderVariable(qualifier="uniform", type="float", name=f"{self.prefix}{self.name}Offset", value=self.offset/self.length)
        yield ShaderVariable(qualifier="uniform", type="int",   name=f"{self.prefix}{self.name}Smooth", value=self.smooth)