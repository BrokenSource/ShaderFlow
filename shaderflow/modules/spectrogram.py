import functools
from collections.abc import Callable, Iterable
from math import pi
from typing import Union

import cachetools
import numpy as np
import scipy
from attr import Factory, define, field

from broken import log
from broken.core.trackers import SameTracker
from broken.types import Hertz, Samples, Seconds
from shaderflow.common.notes import BrokenPianoNote
from shaderflow.module import ShaderModule
from shaderflow.modules.audio import BrokenAudio
from shaderflow.modules.dynamics import DynamicNumber
from shaderflow.texture import ShaderTexture
from shaderflow.variable import ShaderVariable, Uniform


class BrokenAudioFourierMagnitude:
    """Given an raw FFT, interpret the complex number as some size"""
    def Amplitude(x: np.ndarray) -> np.ndarray:
        return np.abs(x)

    def Power(x: np.ndarray) -> np.ndarray:
        return x*x.conjugate()

class BrokenAudioFourierVolume:
    """Convert the FFT into the final spectrogram's magnitude bin"""

    def dBFS(x: np.ndarray) -> np.ndarray:
        return 10*np.log10(x)

    def Sqrt(x: np.ndarray) -> np.ndarray:
        return np.sqrt(x)

    def Linear(x: np.ndarray) -> np.ndarray:
        return x

    def dBFsTremx(x: np.ndarray) -> np.ndarray:
        return 10*(np.log10(x+0.1) + 1)/1.0414


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

    # Note: A value above 1.54 is recommended
    def make_euler(end: float=1.54) -> Callable:
        return (lambda x: np.exp(-(2*x/end)**2) / (end*(pi**0.5)))

    def Dirac(x):
        dirac = np.zeros(x.shape)
        dirac[np.round(x) == 0] = 1
        return dirac

    Euler = make_euler(end=1.2)

    def Sinc(x: np.ndarray) -> np.ndarray:
        return np.abs(np.sinc(x))


class BrokenAudioSpectrogramScale:
    """Functions that defines the y scale of the spectrogram. Tuples of f(x) and f^-1(x)"""

    # Octave, matches the piano keys
    # Todo: Make a generic base exponent?
    Octave = (
        lambda x: (np.log(x)/np.log(2)),
        lambda x: (2**x)
    )

    # Personally not a big fan
    MEL = (
        lambda x: 2595 * np.log10(1 + x/700),
        lambda x: 700 * (10**(x/2595) - 1),
    )


class BrokenAudioSpectrogramWindow:

    @functools.lru_cache
    def hann_poisson_window(N: int, alpha: float=2) -> np.ndarray:
        """
        Generate a Hann-Poisson window

        Args:
            N: The number of window samples
            alpha: Slope of the exponential

        Returns:
            np.array: Window samples
        """
        n = np.arange(N)
        hann    = 0.5 * (1 - np.cos(2 * np.pi * n / N))
        poisson = np.exp(-alpha * np.abs(N - 2*n) / N)
        return hann * poisson

    @functools.lru_cache
    def hanning(size: int) -> np.ndarray:
        """Returns a hanning window of the given size"""
        return np.hanning(size)

    @functools.lru_cache
    def none(size: int) -> np.ndarray:
        """Returns a none window of the given size"""
        return np.ones(size)


@define(slots=False)
class BrokenSpectrogram:
    audio: BrokenAudio = Factory(BrokenAudio)

    fft_n: int = field(default=12, converter=int)
    """2^n FFT size, higher values, higher frequency resolution, less responsiveness"""

    sample_rateio: int = field(default=1, converter=int)
    """Resample the input data by a factor, int for FFT optimizations"""

    # Spectrogram properties
    scale:        tuple[callable] = BrokenAudioSpectrogramScale.Octave
    interpolation:      callable  = BrokenAudioSpectrogramInterpolation.Euler
    magnitude_function: callable  = BrokenAudioFourierMagnitude.Power
    window_function:    callable  = BrokenAudioSpectrogramWindow.hanning
    volume:             callable  = BrokenAudioFourierVolume.Sqrt

    def __cache__(self) -> int:
        return hash((
            self.fft_n,
            self.minimum_frequency,
            self.maximum_frequency,
            self.spectrogram_bins,
            self.sample_rateio,
            self.magnitude_function,
            self.interpolation,
            self.scale,
            self.volume,
        ))

    # # Fourier

    @property
    def fft_size(self) -> Samples:
        return int(2**(self.fft_n) * self.sample_rateio)

    @property
    def fft_bins(self) -> int:
        return int(self.fft_size/2 + 1)

    @property
    def fft_frequencies(self) -> Union[np.ndarray, Hertz]:
        return np.fft.rfftfreq(self.fft_size, 1/(self.audio.samplerate*self.sample_rateio))

    def fft(self) -> np.ndarray:
        data = self.audio.get_last_n_samples(int(2**self.fft_n))

        # Optionally resample the data
        if self.sample_rateio != 1:
            try:
                import samplerate
            except ModuleNotFoundError:
                raise RuntimeError('\n'.join((
                    "Please install 'samplerate' dependency for resampling:"
                    "• Find it at: (https://pypi.org/project/samplerate)"
                )))
            data = np.array([samplerate.resample(x, self.sample_rateio, 'linear') for x in data])

        return self.magnitude_function(
            np.fft.rfft(self.window_function(self.fft_size) * data)
        ).astype(self.audio.dtype)

    # # Spectrogram

    def next(self) -> np.ndarray:
        return self.spectrogram_matrix.dot(self.fft().T).T
        return self.volume([
            self.spectrogram_matrix @ channel
            for channel in self.fft()
        ])

    minimum_frequency: Hertz = 20.0
    maximum_frequency: Hertz = 20000.0
    spectrogram_bins:  int   = 1000

    @property
    def spectrogram_frequencies(self) -> np.ndarray:
        return self.scale[1](np.linspace(
            self.scale[0](self.minimum_frequency),
            self.scale[0](self.maximum_frequency),
            self.spectrogram_bins,
        ))

    @property
    @cachetools.cached(cache={}, key=lambda self: self.__cache__())
    def spectrogram_matrix(self) -> scipy.sparse.csr_matrix:
        """
        Gets a transformation matrix that multiplied with self.fft yields "spectrogram bins" in custom scale

        The idea to get the center frequencies on the custom scale is to compute the following:
        $$ center_frequencies = T^-1(linspace(T(min), T(max), n)) $$

        Where T(f) transforms a frequency to some scale (done in self.spectrogram_frequencies)

        And then create many band-pass filters, each one centered on the center frequencies using
        Whittaker-Shannon's interpolation formula per row of the matrix, considering the FFT bins as
        a one-hertz-frequency function to interpolate, we find "the around frequencies" !
        """

        # Whittaker-Shannon interpolation formula per row of the matrix
        matrix = np.array([
            self.interpolation(theoretical_index - np.arange(self.fft_bins))
            for theoretical_index in (self.spectrogram_frequencies/self.fft_frequencies[1])
        ], dtype=self.audio.dtype)

        # Zero out near-zero values
        matrix[np.abs(matrix) < 1e-5] = 0

        # Create a scipy sparse for much faster matrix multiplication
        return scipy.sparse.csr_matrix(matrix)

    def from_notes(self,
        start: BrokenPianoNote,
        end: BrokenPianoNote,
        bins: int=1000,
        piano: bool=False,
        tuning: Hertz=440,
    ):
        start = BrokenPianoNote.get(start, tuning=tuning)
        end   = BrokenPianoNote.get(end, tuning=tuning)
        log.info(f"Making Spectrogram Piano Matrix from notes ({start.name} - {end.name})")
        self.minimum_frequency = start.frequency
        self.maximum_frequency = end.frequency
        if not piano:
            self.spectrogram_bins = bins
        else:
            # The advertised number of bins should start and end on a note
            half_semitone = 2**(0.5/12)
            self.spectrogram_bins = ((end.note - start.note) + 1)
            self.minimum_frequency /= half_semitone
            self.maximum_frequency *= half_semitone

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderSpectrogram(BrokenSpectrogram, ShaderModule):
    name: str = "iSpectrogram"
    """Prefix name and Texture name of the Shader Variables"""

    length: Seconds = 5
    """Horizontal length of the Spectrogram content"""

    offset: Samples = 0
    """Modulus of total samples written by length, used for scrolling mode"""

    smooth: bool = False
    """Enables Linear interpolation on the Texture, not useful for Bars mode"""

    scrolling: bool = False
    """"""

    dynamics: DynamicNumber = None
    """Apply Dynamics to the FFT data"""

    texture: ShaderTexture = None
    """Internal managed Texture"""

    @property
    def length_samples(self) -> Samples:
        return int(max(1, self.length*self.scene.fps))

    @property
    def _row_shape(self) -> tuple[int, int]:
        return (self.audio.channels, self.spectrogram_bins)

    @property
    def _row_zeros(self) -> np.ndarray:
        return np.zeros(self._row_shape, dtype=np.float32)

    def __post__(self):
        self.dynamics = DynamicNumber(
            frequency=4, zeta=1, response=0,
            dtype=np.float32,
        )
        self.texture = ShaderTexture(
            scene=self.scene,
            name=self.name,
            dtype=np.float32,
            repeat_y=False,
        )

    __same__: SameTracker = Factory(SameTracker)

    def update(self):
        self.texture.components = self.audio.channels
        self.texture.filter = ("linear" if self.smooth else "nearest")
        self.texture.height = self.spectrogram_bins
        self.texture.width = self.length_samples
        self.offset = (self.offset + 1) % self.length_samples
        if (self.dynamics.value.shape != (self._row_shape)):
            self.dynamics.set(self._row_zeros)
        if not self.__same__(self.audio.tell):
            self.dynamics.target = self.next().T.reshape(2, -1)
        self.dynamics.next(dt=abs(self.scene.dt))
        self.texture.write(
            viewport=(self.offset, 0, 1, self.spectrogram_bins),
            data=self.dynamics.value.astype(np.float32),
        )

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",   f"{self.name}Length", self.length_samples)
        yield Uniform("int",   f"{self.name}Bins",   self.spectrogram_bins)
        yield Uniform("float", f"{self.name}Offset", self.offset/self.length_samples)
        yield Uniform("int",   f"{self.name}Smooth", self.smooth)
        yield Uniform("float", f"{self.name}Min",    self.spectrogram_frequencies[0])
        yield Uniform("float", f"{self.name}Max",    self.spectrogram_frequencies[-1])
        yield Uniform("bool",  f"{self.name}Scroll", self.scrolling)
