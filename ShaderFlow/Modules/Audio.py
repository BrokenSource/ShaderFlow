from . import *


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
        self._file = BrokenPath(value)
        if not self._file.exists():
            log.warning(f"Audio File doesn't exist ({value})")
            return
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
class ShaderFlowAudio(ShaderFlowModule, BrokenAudio):

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

    volume: ShaderFlowDynamics = None

    def __build__(self):
        self.volume = self.add(ShaderFlowDynamics(
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
            try:
                self.add_data(next(self.headless_audio).T)
            except StopIteration:
                pass
        self.volume.target = 2 * BrokenUtils.rms(self.get_last_n_seconds(0.1)) * SQRT2
