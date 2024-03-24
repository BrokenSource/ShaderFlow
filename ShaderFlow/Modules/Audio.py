from . import *


class BrokenAudioMode(BrokenEnum):
    Realtime = "realtime"
    File     = "file"


@define(slots=False)
class BrokenAudio:
    mode:  BrokenAudioMode = Field(default=None, converter=BrokenAudioMode.get)
    dtype: numpy.dtype     = numpy.float32
    data:  numpy.ndarray   = None

    read: int = 0
    """The number of samples to read from the audio so far"""

    def __post__(self):
        self.create_buffer()
        BrokenThread.new(self._play_thread,   daemon=True)
        BrokenThread.new(self._record_thread, daemon=True)

    @property
    def buffer_size(self) -> Samples:
        return int(self.samplerate*self.buffer_seconds)

    @property
    def shape(self) -> Tuple[Channels, Samples]:
        return (self.channels, self.buffer_size)

    def create_buffer(self):
        self.data = numpy.zeros(self.shape, dtype=self.dtype)

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
            self.read += data.shape[1]
            return data

    def get_data_between_samples(self, start: Samples, end: Samples) -> numpy.ndarray:
        return self.data[:, int(start):int(end)]

    def get_data_between_seconds(self, start: Seconds, end: Seconds) -> numpy.ndarray:
        return self.get_data_between_samples(start*self.samplerate, end*self.samplerate)

    def get_last_n_samples(self, n: Samples) -> numpy.ndarray:
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
        self.create_buffer()

    # ------------------------------------------|
    # Channels

    _channels: int = 2

    @property
    def channels(self) -> int:
        return self._channels

    @channels.setter
    def channels(self, value: int):
        self._channels = value
        self.create_buffer()

    # ------------------------------------------|
    # History

    _buffer_seconds: Seconds = 20.0
    """Buffer length in seconds. Cheap on ram and fast, ideally have a decent side"""

    @property
    def buffer_seconds(self) -> Seconds:
        return self._buffer_seconds

    @buffer_seconds.setter
    def buffer_seconds(self, value: Seconds):
        self._buffer_seconds = value
        self.create_buffer()

    # ------------------------------------------|
    # File

    _file: Path = None
    _file_reader: BrokenAudioReader = None
    _file_stream: Generator[Tuple[Seconds, numpy.ndarray], None, Seconds] = None

    @property
    def file(self) -> Path:
        return self._file

    @file.setter
    def file(self, value: Path):
        self._file = BrokenPath(value, valid=True)
        if (self._file is None):
            log.warning(f"Audio File doesn't exist ({value})")
            return
        self.samplerate = BrokenFFmpeg.get_samplerate(self._file, echo=False)
        self.channels   = BrokenFFmpeg.get_audio_channels(self._file, echo=False)
        self.mode       = BrokenAudioMode.File
        self.close_recorder()

        # Create Broken readers
        self._file_reader = BrokenAudioReader(path=self._file)
        self._file_stream = self._file_reader.stream

    # ------------------------------------------|
    # Soundcard

    recorder_device: Any = None
    recorder: Any = None

    speaker_device: Any = None
    speaker: Any = None

    @staticmethod
    def recorders() -> Iterable[Any]:
        yield from soundcard.all_microphones(include_loopback=True)

    @staticmethod
    def speakers() -> Iterable[Any]:
        yield from soundcard.all_speakers()

    @staticmethod
    def recorders_names() -> Iterable[str]:
        yield from map(lambda device: device.name, BrokenAudio.recorders())

    @staticmethod
    def speakers_names() -> Iterable[str]:
        yield from map(lambda device: device.name, BrokenAudio.speakers())

    def __fuzzy__(self, name: str, devices: Iterable[str]) -> Optional[str]:
        device_name = BrokenUtils.fuzzy_string_search(name, devices)[0]
        return next(filter(lambda x: x.name == device_name, devices), None)

    def open_speaker(self,
        name: str=None,
        *,
        samplerate: Hertz=None,
    ) -> Self:
        """
        Open a SoundCard device for playing real-time audio.

        Args:
            name: The name of the device to open. If None, the default speaker is used. The search
                is fuzzy, so the match does not need to be exact

            samplerate: If None, gets self.samplerate

        Returns:
            Self, Fluent interface
        """
        (self.speaker or Ignore()).__exit__(None, None, None)

        # Search for the Speaker
        if name is None:
            self.speaker_device = soundcard.default_speaker()
        else:
            self.speaker_device = self.__fuzzy__(name, self.speakers_names)

        # Open the speaker
        log.info(f"Opening Speaker with Device ({self.speaker_device})")
        self.speaker = self.speaker_device.player(
            samplerate=samplerate or self.samplerate,
        ).__enter__()
        return self

    def close_speaker(self) -> Self:
        (self.speaker or Ignore()).__exit__(None, None, None)
        self.speaker = None
        return self

    def open_recorder(self,
        name: str=None,
        *,
        samplerate: Hertz=44100,
        channels: List[int]=None,
        blocksize: int=512,
    ) -> Self:
        """
        Open a SoundCard device for recording real-time audio. Specifics implementation adapted
        from the `soundcard` library Source Code (docstring only)

        Args:
            name: The name of the device to open. If None, the first loopback device or default
                microphone is used. The search is fuzzy, so the match does not need to be exact

            samplerate: The desired sample rate of the audio

            channels: Channels to read from the device.
                • None: Record all available channels
                • List[int]: Record only the specified channels
                • -1: (Linux: Mono mix of all channels) (MacOS: Silence)

            blocksize: Desired minimum latency in samples, and also the number of recorded
                samples at a time. Lower values reduces latency and increases CPU usage, which
                funnily enough might cause latency issues

        Returns:
            Self, Fluent interface
        """
        self.close_recorder()

        # Search for default loopback device
        if name is None:
            for device in self.recorders():
                if device.isloopback:
                    self.recorder_device = device
                    break
            self.recorder_device = (self.recorder_device or soundcard.default_microphone())
        else:
            self.recorder_device = self.__fuzzy__(name, self.recorders_names())

        # Open the recorder
        log.info(f"Opening Recorder with Device ({self.recorder_device})")
        self.recorder = self.recorder_device.recorder(
            samplerate=samplerate,
            channels=channels,
            blocksize=blocksize,
        ).__enter__()

        # Update properties
        self.samplerate = getattr(self.recorder, "_samplerate", samplerate)
        self.channels   = self.recorder_device.channels
        self.mode       = BrokenAudioMode.Realtime
        return self

    def close_recorder(self) -> Self:
        (self.recorder or Ignore()).__exit__(None, None, None)
        self.recorder = None
        return self

    def record(self, numframes: int=None) -> Optional[numpy.ndarray]:
        """Record a number of samples from the recorder. 'None' records all"""
        if not self.recorder:
            return None
        return self.add_data(self.recorder.record(numframes=numframes).T)

    def _record_thread(self) -> None:
        while True:
            if (self.record() is None):
                time.sleep(0.01)

    # # Playing

    _play_queue: Deque[numpy.ndarray] = Factory(deque)

    def play(self, data: numpy.ndarray) -> None:
        """Add a numpy array to the play queue. for non-blocking playback"""
        if not self.speaker_device:
            return None
        self._play_queue.append(data)

    def _play_thread(self) -> None:
        while True:
            if not self._play_queue:
                time.sleep(0.01)
                continue
            self.speaker.play(self._play_queue.popleft().T)

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
class ShaderAudio(BrokenAudio, ShaderModule):

    # Todo: Move to a ShaderAudioProcessing class
    volume:  ShaderDynamics = None
    std:     ShaderDynamics = None
    final:   bool = True

    def __post__(self):
        self.volume = ShaderDynamics(
            scene=self.scene, name=f"{self.name}Volume",
            frequency=2, zeta=1, response=0, value=0
        )
        self.std = ShaderDynamics(
            scene=self.scene, name=f"{self.name}STD",
            frequency=10, zeta=1, response=0, value=0
        )

    @property
    def duration(self) -> Seconds:
        return BrokenFFmpeg.get_audio_duration(self.file) or self.scene.duration

    def setup(self):
        self.file = self.file
        if (self.final and self.scene.realtime):
            if (self.mode == BrokenAudioMode.File):
                self.open_speaker()
            else:
                self.open_recorder()

    def ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        if self.final:
            ffmpeg.input(self.file)

    def update(self):
        try:
            if self._file_stream:
                self._file_reader.chunk = self.scene.frametime
                data = next(self._file_stream).T
                self.add_data(data)
                self.play(data)
        except StopIteration:
            pass

        self.volume.target = 2 * BrokenUtils.rms(self.get_last_n_seconds(0.1)) * SQRT2
        self.std.target    = numpy.std(self.get_last_n_seconds(0.1))

# -------------------------------------------------------------------------------------------------|
