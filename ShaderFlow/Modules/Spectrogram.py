from . import *


class BrokenAudioFourierMagnitude:
    """Given an raw FFT, interpret the complex number as some size"""
    Amplitude = lambda x: numpy.abs(x)
    Power     = lambda x: x*x.conjugate()


class BrokenAudioFourierVolume:
    """Convert the FFT into the final spectrogram's magnitude bin"""
    dBFsTremx = (lambda x: 10*(numpy.log10(x+0.1) + 1)/1.0414)
    dBFs      = (lambda x: 10*numpy.log10(x))
    Sqrt      = (lambda x: numpy.sqrt(x))
    Linear    = (lambda x: x)


class BrokenAudioSpectrogramInterpolation:
    """Interpolate the FFT values, discrete to continuous"""
    #
    # I can explain this better later, but the idea is here:
    # • https://www.desmos.com/calculator/vvixdoooty
    # • https://en.wikipedia.org/wiki/Whittaker%E2%80%93Shannon_interpolation_formula
    #
    # Sinc(x) is already normalized (divided by the area, pi) as in sinc(x) = sin(pi*x)/(pi*x).
    #
    # The general case for a interpolation formula is to normalize some function f(x) by its area.
    # For example, in the case of exp(-x^2) as the function, its area is the  magical sqrt(pi)
    # as seen in @3b1b https://www.youtube.com/watch?v=cy8r7WSuT1I
    #

    @staticmethod
    # Note: A value above 1.54 is recommended
    def make_euler(end: float=1.54) -> Callable:
        return (lambda x: numpy.exp(-(2*x/end)**2) / (end*SQRT_PI))

    @staticmethod
    @functools.lru_cache
    def Dirac(x):
        dirac = numpy.zeros(x.shape)
        dirac[numpy.round(x) == 0] = 1
        return dirac

    Euler = make_euler(end=1.2)
    Sinc  = (lambda x: numpy.sinc(x))


class BrokenAudioSpectrogramScale:
    """Functions that defines the y scale of the spectrogram. Tuples of f(x) and f^-1(x)"""

    # Octave, matches the piano keys
    # Todo: Make a generic base exponent?
    Octave = (
        lambda x: (numpy.log(x)/numpy.log(2)),
        lambda x: (2**x)
    )

    # Personally not a big fan
    MEL = (
        lambda x: 2595 * numpy.log10(1 + x/700),
        lambda x: 700 * (10**(x/2595) - 1),
    )


class BrokenAudioSpectrogramWindow:

    @functools.lru_cache
    def hann_poisson_window(N, alpha=2) -> numpy.ndarray:
        """
        Generate a Hann-Poisson window

        Parameters:
            N: The number of window samples
            alpha: Slope of the exponential

        Returns:
            numpy.array: Window samples
        """
        n = numpy.arange(N)
        hann    = 0.5 * (1 - numpy.cos(2 * numpy.pi * n / N))
        poisson = numpy.exp(-alpha * numpy.abs(N - 2*n) / N)
        return hann * poisson

    @functools.lru_cache
    def hanning(size: int) -> numpy.ndarray:
        """Returns a hanning window of the given size"""
        return numpy.hanning(size)

    @functools.lru_cache
    def none(size: int) -> numpy.ndarray:
        """Returns a none window of the given size"""
        return numpy.ones(size)


@define(slots=False)
class BrokenSpectrogram:
    audio: BrokenAudio = Factory(BrokenAudio)

    fft_n:              int      = Field(default=12, converter=int)
    """2^n FFT size, higher values, higher frequency resolution, less responsiveness"""

    sample_rateio:      int      = Field(default=1, converter=int)
    """Resample the input data by a factor, int for FFT optimizations"""

    # Spectrogram properties
    scale:        Tuple[callable] = BrokenAudioSpectrogramScale.Octave
    interpolation:      callable  = BrokenAudioSpectrogramInterpolation.Euler
    magnitude_function: callable  = BrokenAudioFourierMagnitude.Power
    window_function:    callable  = BrokenAudioSpectrogramWindow.hanning
    volume:             callable  = BrokenAudioFourierVolume.Sqrt

    spectrogram_frequencies: numpy.ndarray = None
    spectrogram_matrix:      numpy.ndarray = None

    # # Fourier

    @property
    def fft_size(self) -> Samples:
        return int(2**(self.fft_n) * self.sample_rateio)

    @property
    def fft_bins(self) -> int:
        return int(self.fft_size/2 + 1)

    @property
    def fft_frequencies(self) -> Union[numpy.ndarray, Hertz]:
        return numpy.fft.rfftfreq(self.fft_size, 1/(self.audio.samplerate*self.sample_rateio))

    def fft(self) -> numpy.ndarray:
        data = self.audio.get_last_n_samples(int(2**self.fft_n))

        # Resample the data
        if self.sample_rateio != 1:
            data = numpy.array([samplerate.resample(x, self.sample_rateio, 'linear') for x in data])

        return self.magnitude_function(
            numpy.fft.rfft(self.window_function(self.fft_size) * data)
        ).astype(self.audio.dtype)

    # # Spectrogram

    def next(self) -> numpy.ndarray:
        return self.volume([
            self.spectrogram_matrix @ channel
            for channel in self.fft()
        ])

    @property
    def spectrogram_bins(self) -> int:
        return self.spectrogram_matrix.shape[0]

    def make_spectrogram_matrix(self,
        minimum_frequency: float=20,
        maximum_frequency: float=20000,
        bins: int=1000,
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:
        """
        Gets a transformation matrix that multiplied with self.fft yields "spectrogram bins" in custom scale

        The idea to get the center frequencies on the custom scale is to compute the following:
        $$ center_frequencies = T^-1(linspace(T(min), T(max), n)) $$

        Where T(f) transforms a frequency to some scale (for example octave or melodic)

        And then create many band-pass filters, each one centered on the center frequencies using
        Whittaker-Shannon's interpolation formula per row of the matrix, considering the FFT bins as
        a one-hertz-frequency function to interpolate, we find "the around frequencies" !
        """
        log.info(f"Making Spectrogram Matrix ({minimum_frequency:.2f}Hz -> {maximum_frequency:.2f}Hz) with {bins} bins)")

        # Get the linear space on the custom scale -> "frequencies to scale"
        transform_linspace = numpy.linspace(
            self.scale[0](minimum_frequency),
            self.scale[0](maximum_frequency),
            bins,
        )

        # Get the center frequencies on the octave scale -> "scale to frequencies", revert the transform
        self.spectrogram_frequencies = self.scale[1](transform_linspace)
        linear = numpy.arange(self.fft_bins)

        # Whittaker-Shannon interpolation formula per row of the matrix
        self.spectrogram_matrix = numpy.array([
            self.interpolation(theoretical_index - linear)
            for theoretical_index in (self.spectrogram_frequencies/self.fft_frequencies[1])
        ], dtype=self.audio.dtype)

        # Zero out near-zero values
        self.spectrogram_matrix[numpy.abs(self.spectrogram_matrix) < 1e-5] = 0

        # Create a scipy sparse for much faster matrix multiplication
        self.spectrogram_matrix = scipy.sparse.csr_matrix(self.spectrogram_matrix)

        return (self.spectrogram_frequencies, self.spectrogram_matrix)

    def make_spectrogram_matrix_piano(self,
        start: BrokenPianoNote,
        end:   BrokenPianoNote,
        extra: int=0,
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:

        log.info(f"Making Spectrogram Piano Matrix from notes ({start.name} - {end.name})")

        return self.make_spectrogram_matrix(
            minimum_frequency=start.frequency,
            maximum_frequency=end.frequency,
            bins=((end.note - start.note) + 1) * (extra + 1),
        )

# -------------------------------------------------------------------------------------------------|

@define
class ShaderFlowSpectrogram(ShaderFlowModule, BrokenSpectrogram):
    name:     str  = "iSpectrogram"
    length:   int  = 1024
    offset:   int  = 0
    smooth:   bool = False
    texture:  ShaderFlowTexture  = None
    dynamics: ShaderFlowDynamics = None
    still:    bool = False

    def __attrs_post_init__(self):
        self.make_spectrogram_matrix()

    def __create_texture__(self):
        self.texture.from_raw(
            size=(self.length, self.spectrogram_bins),
            components=self.audio.channels,
            dtype="f4",
        )

    def __build__(self):
        self.dynamics = ShaderFlowDynamics(frequency=4, zeta=1, response=0)
        self.texture = self.add(ShaderFlowTexture(name=f"{self.name}", mipmaps=False))
        self.texture.filter = ("linear" if self.smooth else "nearest")
        self.__create_texture__()

    def __setup__(self):
        self.__create_texture__()

    def __update__(self):
        data = self.next().T.reshape(2, -1)
        self.offset = (self.offset + 1) % self.length
        self.dynamics.target = data
        self.dynamics.next(dt=abs(self.scene.dt))
        self.texture.write(
            viewport=(self.offset, 0, 1, self.spectrogram_bins),
            data=self.dynamics.value,
        )

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",   f"{self.name}Length", self.length)
        yield ShaderVariable("uniform", "int",   f"{self.name}Bins",   self.spectrogram_bins)
        yield ShaderVariable("uniform", "float", f"{self.name}Offset", self.offset/self.length)
        yield ShaderVariable("uniform", "int",   f"{self.name}Smooth", self.smooth)
        yield ShaderVariable("uniform", "float", f"{self.name}Min",    self.spectrogram_frequencies[0])
        yield ShaderVariable("uniform", "float", f"{self.name}Max",    self.spectrogram_frequencies[-1])
        yield ShaderVariable("uniform", "bool",  f"{self.name}Still",  self.still)
