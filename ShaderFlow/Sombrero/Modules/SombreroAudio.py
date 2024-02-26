from . import *

PIANO_NOTES = "C C# D D# E F F# G G# A A# B".split()

@define
class BrokenPianoNote:
    note:     int     = 60
    start:    Seconds = 0
    end:      Seconds = 0
    channel:  int     = 0
    velocity: int     = 100

    # # Initialization

    @classmethod
    def from_index(cls, note: int, **kwargs) -> Self:
        return cls(note=note, **kwargs)

    @classmethod
    def from_name(cls, name: str, **kwargs) -> Self:
        return cls(note=BrokenPianoNote.name_to_index(name), **kwargs)

    @classmethod
    def from_frequency(cls, frequency: float, **kwargs) -> Self:
        return cls(note=BrokenPianoNote.frequency_to_index(frequency), **kwargs)

    # # Conversion

    @staticmethod
    def index_to_name(index: int) -> str:
        return f"{PIANO_NOTES[index % 12]}{index//12 - 1}"

    @staticmethod
    def index_to_frequency(index: int, *, tuning: float=440) -> float:
        return tuning * 2**((index - 69)/12)

    @staticmethod
    def name_to_index(name: str) -> int:
        note, octave = name[:-1], int(name[-1])
        return PIANO_NOTES.index(note) + 12*(octave + 1)

    @staticmethod
    def name_to_frequency(name: str, *, tuning: float=440) -> float:
        return BrokenPianoNote.index_to_frequency(BrokenPianoNote.name_to_index(name), tuning=tuning)

    @staticmethod
    def frequency_to_index(frequency: float, *, tuning: float=440) -> int:
        return round(12*math.log2(frequency/tuning) + 69)

    @staticmethod
    def frequency_to_name(frequency: float, *, tuning: float=440) -> str:
        return BrokenPianoNote.index_to_name(BrokenPianoNote.frequency_to_index(frequency, tuning=tuning))

    # # Utilities

    @property
    def frequency(self) -> float:
        return BrokenPianoNote.index_to_frequency(self.note)

    @frequency.setter
    def frequency(self, value: float):
        self.note = BrokenPianoNote.frequency_to_index(value)

    @property
    def name(self) -> str:
        return BrokenPianoNote.index_to_name(self.note)

    @name.setter
    def name(self, value: str):
        self.note = BrokenPianoNote.name_to_index(value)

    # Black and White

    def is_white(note: int) -> bool:
        return (note % 12) in {0, 2, 4, 5, 7, 9, 11}

    def is_black(note: int) -> bool:
        return (note % 12) in {1, 3, 6, 8, 10}

    @property
    def white(self) -> bool:
        return BrokenPianoNote.is_white(self.note)

    @property
    def black(self) -> bool:
        return BrokenPianoNote.is_black(self.note)

    # Temporal

    @property
    def duration(self):
        return self.end - self.start

    @duration.setter
    def duration(self, value: Seconds):
        self.end = self.start + value

# -------------------------------------------------------------------------------------------------|

@define
class BrokenPianoRoll:
    notes: intervaltree.IntervalTree = Factory(intervaltree.IntervalTree)

    # # Base actions

    def add_notes(self, notes: Union[BrokenPianoNote | Iterable[BrokenPianoNote]]):
        for note in BrokenUtils.flatten(notes):
            self.notes.addi(note.start, note.end, note)

    def get_notes_between(self, start: Seconds, end: Seconds) -> Iterator[BrokenPianoNote]:
        yield from self.notes[start:end]

    def get_notes_at(self, time: Seconds) -> Iterator[BrokenPianoNote]:
        yield from self.notes[time]

    # # Initialization

    @classmethod
    def from_notes(cls, notes: Iterable[BrokenPianoNote]):
        return cls().add_notes(notes)

    @classmethod
    def from_midi(cls, path: Path):
        return cls().add_midi(path)

    # # Utilities

    def add_midi(self, path: Path):
        import mido

        for track in mido.MidiFile(path).tracks:
            for message in track:
                if message.type != "note_on":
                    continue
                self.add_notes(BrokenPianoNote.from_index(
                    note=message.note,
                    start=message.time,
                    end=message.time + message.time,
                    channel=message.channel,
                    velocity=message.velocity,
                ))

    def __iter__(self) -> Iterator[BrokenPianoNote]:
        yield from self.notes

# -------------------------------------------------------------------------------------------------|

class BrokenAudioMode(BrokenEnum):
    Realtime = "realtime"
    File     = "file"

@define(slots=False)
class BrokenAudio:
    mode:  BrokenAudioMode = Field(default=None, converter=BrokenAudioMode.get)
    dtype: numpy.dtype     = numpy.float32
    data:  numpy.ndarray   = None

    def __create_buffer__(self):
        self.data = numpy.zeros(
            (self.channels, self.history_samples),
            dtype=self.dtype
        )

    def __attrs_post_init__(self):
        self.__create_buffer__()


    @property
    def history_samples(self) -> int:
        return self.samplerate*self.history_seconds

    def add_data(self, data: numpy.ndarray) -> Optional[numpy.ndarray]:
        """
        Roll the data to the left by the length of the new data; copy new data to the end

        Note: Channel count must match the buffer's one

        Args:
            `data`: The new data of shape: (channels, length)

        Returns:
            The data that was written
        """
        if (data := numpy.array(data, dtype=self.dtype)).any():
            self.data = numpy.roll(self.data, -data.shape[1], axis=1)
            self.data[:, -data.shape[1]:] = data
            return data

    def get_data_between_samples(self, start: int, end: int) -> numpy.ndarray:
        return self.data[:, int(start):int(end)]

    def get_data_between_seconds(self, start: Seconds, end: Seconds) -> numpy.ndarray:
        return self.get_data_between_samples(start*self.samplerate, end*self.samplerate)

    def get_last_n_samples(self, n: int) -> numpy.ndarray:
        return self.data[:, -int(n):]

    def get_last_n_seconds(self, n: Seconds) -> numpy.ndarray:
        return self.get_last_n_samples(n*self.samplerate)

    # ------------------------------------------|
    # Sample Rate

    _samplerate: Hertz = 44100

    @property
    def samplerate(self) -> Hertz:
        return self._samplerate

    @samplerate.setter
    def samplerate(self, value: Hertz):
        self._samplerate = value
        self.__create_buffer__()

    # ------------------------------------------|
    # Channels

    _channels: int = 2

    @property
    def channels(self) -> int:
        return self._channels

    @channels.setter
    def channels(self, value: int):
        self._channels = value
        self.__create_buffer__()

    # ------------------------------------------|
    # History

    _history_seconds: Seconds = 10

    @property
    def history_seconds(self) -> Seconds:
        return self._history_seconds

    @history_seconds.setter
    def history_seconds(self, value: Seconds):
        self._history_seconds = value
        self.__create_buffer__()

    # ------------------------------------------|
    # File

    _file: Path = None

    @property
    def file(self) -> Path:
        return self._file

    @file.setter
    def file(self, value: Path):
        self._file = value
        log.info(f"Setting Audio File to ({value})")
        self.samplerate = BrokenFFmpeg.get_samplerate(value)
        self.channels   = BrokenFFmpeg.get_audio_channels(value)

    # ------------------------------------------|
    # Soundcard

    recorder: Any = None
    device:   Any = None

    @staticmethod
    def devices() -> Iterable[Any]:
        yield from soundcard.all_microphones(include_loopback=True)

    @staticmethod
    def devices_names() -> Iterable[str]:
        yield from map(lambda device: device.name, BrokenAudio.devices())

    def open_device(self,
        name: str=None,
        *,
        samplerate: Hertz=44100,
        channels: List[int]=None,
        thread: bool=True,
        blocksize: int=512,
    ) -> None:
        """
        Open a SoundCard device for recording real-time audio. Specifics implementation adapted
        from the `soundcard` library Source Code (docstring only)

        Args:
            `name`: The name of the device to open. If None, the first loopback device or default
                microphone is used. The search is fuzzy, so the match does not need to be exact

            `samplerate`: The desired sample rate of the audio

            `channels`: Channels to read from the device.
                • None: Record all available channels
                • List[int]: Record only the specified channels
                • -1: (Linux: Mono mix of all channels) (MacOS: Silence)

            `thread`: Spawn a looping thread to record audio

            `blocksize`: Desired minimum latency in samples, and also the number of recorded
                samples at a time. Lower values reduces latency and increases CPU usage, which
                funnily enough might cause latency issues

        Returns:
            None
        """
        if self.recorder:
            log.minor(f"Recorder already open, closing it")
            self.recorder.__exit__(None, None, None)

        # Search for default loopback device
        if name is None:
            for device in self.devices():
                if not device.isloopback:
                    continue
                self.device = device
                break
            else:
                log.warning(f"No loopback device found, using the Default Microphone")
                self.device = soundcard.default_microphone()
        else:
            log.info(f"Fuzzy string searching for audio capture device with name ({name})")
            fuzzy_name, confidence = BrokenUtils.fuzzy_string_search(name, self.devices_names)

            if fuzzy_name is None:
                log.error(f"Couldn't find any device with name ({name}) out of devices:")
                self.log_available_devices()
                return None

            # Find the device
            self.device = next((device for device in self.devices if device.name == fuzzy_name), None)

        # Open the recorder
        log.info(f"Opening Recorder with Device ({self.device})")
        self.recorder = self.device.recorder(
            samplerate=samplerate,
            channels=channels,
            blocksize=blocksize,
        ).__enter__()

        # Update properties
        self.samplerate = getattr(self.recorder, "_samplerate", samplerate)
        self.channels   = self.device.channels

        # Start the recording thread
        self.record_thread(start=thread)

    def record(self, numframes: int=None) -> Optional[numpy.ndarray]:
        """
        Record a number of samples from the recorder.

        Args:
            `numframes`: The number of samples to record. If None, gets all samples until empty

        Returns:
            The recorded data
        """
        if not self.device:
            raise ValueError("No recorder device initialized")
        return self.add_data(self.recorder.record(numframes=numframes).T)

    def record_thread(self, **kwargs) -> None:
        BrokenThread.new(self.record, daemon=True, loop=True, **kwargs)

    # ------------------------------------------|
    # Properties utils

    @property
    def stereo(self) -> bool:
        return self.channels == 2

    @property
    def mono(self) -> bool:
        return self.channels == 1

    @property
    def duration(self) -> Seconds:
        if self.mode == BrokenAudioMode.Realtime:
            return math.inf
        if self.mode == BrokenAudioMode.File:
            return BrokenFFmpeg.get_audio_duration(self.file)

# -------------------------------------------------------------------------------------------------|

@define
class SombreroAudio(SombreroModule, BrokenAudio):

    # ------------------------------------------|
    # Module

    @property
    def duration(self) -> Seconds:
        if self.scene.realtime:
            return self.scene.time_end
        elif self.scene.rendering:
            return BrokenFFmpeg.get_audio_duration(self.file)

    __headless_audio__: Iterator[numpy.ndarray] = None

    @property
    def headless_audio(self) -> Generator[numpy.ndarray, None, Seconds]:
        self.__headless_audio__ = self.__headless_audio__ or BrokenFFmpeg.get_raw_audio(
            chunk=self.scene.frametime,
            path=self.file,
        )
        return self.__headless_audio__

    volume: SombreroDynamics = None

    def __build__(self):
        self.volume = self.add(SombreroDynamics(
            name=f"i{self.name}Volume",
            frequency=2, zeta=1, response=0, value=0
        ))

    def __setup__(self):
        if self.scene.realtime:
            self.open_device()

    def __ffmpeg__(self, ffmpeg: BrokenFFmpeg) -> None:
        ffmpeg.input(self.file)

    def __update__(self):
        if self.scene.rendering:
            self.add_data(next(self.headless_audio).T)
        self.volume.target = 2 * BrokenUtils.rms(self.get_last_n_seconds(0.1)) * SQRT2

# -------------------------------------------------------------------------------------------------|

class BrokenAudioFourierMagnitude:
    """Given an raw FFT, interpret the complex number as some size"""
    Amplitude = lambda x: numpy.abs(x)
    Power     = lambda x: x*x.conjugate()

# -------------------------------------------------------------------------------------------------|

class BrokenAudioFourierVolume:
    """Convert the FFT into the final spectrogram's magnitude bin"""
    dBFsTremx = (lambda x: 10*(numpy.log10(x+0.1) + 1)/1.0414)
    dBFs      = (lambda x: 10*numpy.log10(x))
    Sqrt      = (lambda x: numpy.sqrt(x))
    Linear    = (lambda x: x)

# -------------------------------------------------------------------------------------------------|

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
    def make_euler(end: float=1.54) -> Callable:
        # Note: A value above 1.54 is recommended
        return (lambda x: numpy.exp(-(2*x/end)**2) / (end*SQRT_PI))

    Euler = make_euler(end=1.54)
    Sinc  = (lambda x: numpy.sinc(x))

# -------------------------------------------------------------------------------------------------|

class BrokenAudioSpectrogramScale:
    """Functions that defines the y scale of the spectrogram. Tuples of f(x) and f^-1(x)"""

    # Octave, matches the piano keys
    # Todo: Make a generic base exponent?
    Octave = (
        lambda x: (12 * numpy.log10(x/440) / numpy.log10(2)),
        lambda x: (440 * 2**(x/12))
    )

    # Personally not a big fan
    MEL = (
        lambda x: 2595 * numpy.log10(1 + x/700),
        lambda x: 700 * (10**(x/2595) - 1),
    )

# -------------------------------------------------------------------------------------------------|

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

# -------------------------------------------------------------------------------------------------|

@define(slots=False)
class BrokenSpectrogram:
    audio: BrokenAudio = Factory(BrokenAudio)

    # 2^n FFT size, higher values, higher frequency resolution, less responsiveness
    fft_n: int = Field(default=12, converter=int)
    magnitude_function: callable = BrokenAudioFourierMagnitude.Power
    window_function:    callable = BrokenAudioSpectrogramWindow.hanning

    # Transformation Matrix functions
    scale:   Tuple[callable] = BrokenAudioSpectrogramScale.Octave
    interpolation: callable  = BrokenAudioSpectrogramInterpolation.Euler

    # Spectrogram properties
    volume: callable = BrokenAudioFourierVolume.Sqrt
    spectrogram_frequencies: numpy.ndarray = None
    spectrogram_matrix:      numpy.ndarray = None

    # # Fourier

    @property
    def fft_size(self) -> Samples:
        return int(2**self.fft_n)

    @property
    def fft_bins(self) -> int:
        return int(self.fft_size/2 + 1)

    @property
    def fft_frequencies(self) -> Union[numpy.ndarray, Hertz]:
        return numpy.fft.rfftfreq(self.fft_size, 1/self.audio.samplerate)

    def fft(self, end: int=-1) -> numpy.ndarray:
        data = self.window_function(self.fft_size) * self.audio.get_last_n_samples(self.fft_size)
        return self.magnitude_function(numpy.fft.rfft(data)).astype(self.audio.dtype)

    # # Spectrogram

    def next(self) -> numpy.ndarray:
        return self.volume(numpy.einsum('ij,kj->ik', self.fft(), self.spectrogram_matrix))

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

        # Whittaker-Shannon interpolation formula per row of the matrix
        self.spectrogram_matrix = numpy.array([
            self.interpolation(theoretical_index - numpy.arange(self.fft_bins))
            for theoretical_index in (self.spectrogram_frequencies/self.fft_frequencies[1])
        ], dtype=self.audio.dtype)

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
class SombreroSpectrogram(SombreroModule, BrokenSpectrogram):
    name:     str              = "iSpectrogram"
    length:   int              = 1024
    offset:   int              = 0
    smooth:   bool             = False
    texture:  SombreroTexture  = None
    dynamics: SombreroDynamics = None

    def __attrs_post_init__(self):
        self.make_spectrogram_matrix()

    def __create_texture__(self):
        self.texture.from_raw(
            size=(self.length, self.spectrogram_bins),
            components=self.audio.channels,
            dtype="f4",
        )

    def __build__(self):
        self.dynamics = self.add(SombreroDynamics(frequency=4, zeta=1, response=0))
        self.texture = self.add(SombreroTexture(name=f"{self.name}", mipmaps=False))
        self.texture.filter = ("linear" if self.smooth else "nearest")
        self.__create_texture__()

    def __setup__(self):
        self.__create_texture__()

    def __update__(self):
        data = self.next().T.reshape(2, -1)
        self.offset = (self.offset + 1) % self.length
        self.dynamics.target = data
        self.texture.write(
            viewport=(self.offset, 0, 1, self.spectrogram_bins),
            data=self.dynamics.value,
        )

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",   f"{self.name}Length", self.length)
        yield ShaderVariable("uniform", "int",   f"{self.name}Bins",   self.spectrogram_bins)
        yield ShaderVariable("uniform", "float", f"{self.name}Offset", self.offset/self.length)
        yield ShaderVariable("uniform", "int",   f"{self.name}Smooth", self.smooth)
