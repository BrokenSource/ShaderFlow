import math
import time
import warnings
from collections import deque
from pathlib import Path
from typing import Any, Deque, Generator, Iterable, List, Optional, Self, Tuple

import numpy
from attr import Factory, define

from Broken import (
    BrokenEnum,
    BrokenPath,
    BrokenPlatform,
    BrokenThread,
    Nothing,
    log,
)
from Broken.Externals.FFmpeg import BrokenAudioReader, BrokenFFmpeg
from Broken.Types import Channels, Hertz, Samples, Seconds
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Modules.Dynamics import ShaderDynamics

try:
    import soundcard
except OSError as exception:
    raise ImportError(log.error('\n'.join((
        f"Original ImportError: {exception}\n\n",
        "Couldn't import 'soundcard' library, probably due missing audio shared libraries (libpulse)",
        "• If you're on Linux, consider installing 'pulseaudio' or 'pipewire-pulse' packages",
        "• Shouldn't happen elsewhere, get support at (https://github.com/bastibe/SoundCard)"
    ))))

# Disable runtime warnings on SoundCard, it's ok to read nothing on Windows
if BrokenPlatform.OnWindows:
    warnings.filterwarnings("ignore", category=soundcard.SoundcardRuntimeWarning)

# ------------------------------------------------------------------------------------------------ #

def fuzzy_string_search(string: str, choices: List[str], many: int=1, minimum_score: int=0) -> list[tuple[str, int]]:
    """Fuzzy search a string in a list of strings, returns a list of matches"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        import thefuzz.process
        result = thefuzz.process.extract(string, choices, limit=many)
        if many == 1:
            return result[0]
        return result

def root_mean_square(data) -> float:
    return numpy.sqrt(numpy.mean(numpy.square(data)))

# ------------------------------------------------------------------------------------------------ #

class BrokenAudioMode(BrokenEnum):
    Realtime = "realtime"
    File     = "file"

@define(slots=False)
class BrokenAudio:
    mode: BrokenAudioMode = BrokenAudioMode.Realtime.field()
    dtype: numpy.dtype = numpy.float32

    data: numpy.ndarray = None
    """Progressive audio data, shape: (channels, samples)"""

    tell: int = 0
    """The number of samples to read from the audio so far"""

    def __post__(self):
        BrokenThread.new(self._play_thread,   daemon=True)
        BrokenThread.new(self._record_thread, daemon=True)
        self.create_buffer()

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
            data: The new data of shape: (channels, length)

        Returns:
            The data that was written, if any
        """
        if (data := numpy.array(data, dtype=self.dtype)).any():
            length = data.shape[1]
            self.data = numpy.roll(self.data, -length, axis=1)
            self.data[:, -length:] = data
            self.tell += length
            return data

    def get_data_between_samples(self, start: Samples, end: Samples) -> numpy.ndarray:
        return self.data[:, int(start):int(end)]

    def get_data_between_seconds(self, start: Seconds, end: Seconds) -> numpy.ndarray:
        return self.get_data_between_samples(start*self.samplerate, end*self.samplerate)

    def get_last_n_samples(self, n: Samples, *, offset: Samples=0) -> numpy.ndarray:
        return self.data[:, (-1)*(int(n+offset) + 1) : (-1)*(int(offset) + 1)]

    def get_last_n_seconds(self, n: Seconds) -> numpy.ndarray:
        return self.get_last_n_samples(n*self.samplerate)

    # ------------------------------------------|
    # Sample Rate

    _samplerate: Hertz = 44100

    @property
    def samplerate(self) -> Hertz:
        """How many data points per second the audio is sampled at. Defaults to 44100"""
        return self._samplerate or 44100

    @samplerate.setter
    def samplerate(self, value: Hertz):
        self._samplerate = value
        self.create_buffer()

    # ------------------------------------------|
    # Channels

    _channels: int = 2

    @property
    def channels(self) -> int:
        """Number of audio streams (channels). Two is stereo, one is mono. Defaults to 2"""
        return self._channels or 2

    @channels.setter
    def channels(self, value: int):
        self._channels = value
        self.create_buffer()

    # ------------------------------------------|
    # History

    _buffer_seconds: Seconds = 30.0

    @property
    def buffer_seconds(self) -> Seconds:
        """Buffer length in seconds. Cheap on ram and fast, ideally have a decent side"""
        # Note: To convince yourself, (48000 Hz) * (2 Channels) * (30 sec) * (f32=4 bytes) = 11 MB
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
        self._file = BrokenPath.get(value)
        if self._file and not (self._file.exists()):
            return log.minor(f"Audio File doesn't exist ({value})")
        self.samplerate   = BrokenFFmpeg.get_audio_samplerate(self.file, echo=False)
        self.channels     = BrokenFFmpeg.get_audio_channels(self.file, echo=False)
        self._file_reader = BrokenAudioReader(path=self.file)
        self._file_stream = self._file_reader.stream
        self.mode         = BrokenAudioMode.File
        self.close_recorder()

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

    def list_recorders(self) -> None:
        """List and print all available Audio recording devices"""
        log.info("Recording Devices:")
        for i, device in enumerate(BrokenAudio.recorders()):
            log.info(f"• ({i:2d}) Recorder: '{device.name}'")

    def list_speakers(self) -> None:
        """List and print all available Audio playback devices"""
        log.info("Playback Devices:")
        for i, device in enumerate(BrokenAudio.speakers()):
            log.info(f"• ({i:2d}) Speaker: '{device.name}'")

    def __fuzzy__(self, name: str, devices: Iterable[str]) -> Optional[str]:
        device_name = fuzzy_string_search(name, devices)[0]
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
        (self.speaker or Nothing()).__exit__(None, None, None)

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
        (self.speaker or Nothing()).__exit__(None, None, None)
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
        (self.recorder or Nothing()).__exit__(None, None, None)
        self.recorder = None
        return self

    def record(self, numframes: int=None) -> Optional[numpy.ndarray]:
        """Record a number of samples from the recorder. 'None' records all"""
        if not self.recorder:
            return None
        return self.add_data(self.recorder.record(numframes=numframes).T)

    def _record_thread(self) -> None:
        while True:
            try:
                if (self.record() is None):
                    time.sleep(0.01)
            except Exception:
                pass

    # # Playing

    _play_queue: Deque[numpy.ndarray] = Factory(deque)

    def play(self, data: numpy.ndarray) -> None:
        """Add a numpy array to the play queue. for non-blocking playback"""
        if not self.speaker_device:
            return None
        self._play_queue.append(data)

    def _play_thread(self) -> None:
        while True:
            if (self._play_queue and self.speaker):
                self.speaker.play(self._play_queue.popleft().T)
                continue
            time.sleep(0.01)

    # ------------------------------------------|
    # Properties utils

    @property
    def stereo(self) -> bool:
        """Is this Audio object stereo?"""
        return (self.channels == 2)

    @property
    def mono(self) -> bool:
        """Is this Audio object mono?"""
        return (self.channels == 1)

    @property
    def duration(self) -> Seconds:
        if self.mode == BrokenAudioMode.Realtime:
            return math.inf
        if self.mode == BrokenAudioMode.File:
            return BrokenFFmpeg.get_audio_duration(self.file)

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderAudio(BrokenAudio, ShaderModule):

    # Todo: Move to a ShaderAudioProcessing class
    volume: ShaderDynamics = None
    std:    ShaderDynamics = None
    final:  bool = True

    def __post__(self):
        self.volume = ShaderDynamics(
            scene=self.scene, name=f"{self.name}Volume",
            frequency=2, zeta=1, response=0, value=0
        )
        self.std = ShaderDynamics(
            scene=self.scene, name=f"{self.name}STD",
            frequency=10, zeta=1, response=0, value=0
        )

    def commands(self):
        return

        # Common commands
        self.scene.typer.command(self.list_recorders, panel=self.__class__.__name__)
        self.scene.typer.command(self.list_speakers, panel=self.__class__.__name__)

        # Proper commands
        self.scene.typer.command(self.open_recorder, name=f"{self.name}-recorder", panel=f"{self.__class__.__name__}: {self.name}")
        self.scene.typer.command(self.open_speaker, name=f"{self.name}-speaker", panel=f"{self.__class__.__name__}: {self.name}")

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

    def ffhook(self, ffmpeg: BrokenFFmpeg) -> None:
        if BrokenPath.get(self.file).exists():
            ffmpeg.input(path=self.file)

    def update(self):
        try:
            if self._file_stream:
                self._file_reader.chunk = self.scene.rdt
                data = next(self._file_stream).T
                self.add_data(data)
                self.play(data)
        except StopIteration:
            pass

        self.volume.target = 2 * root_mean_square(self.get_last_n_seconds(0.1)) * (2**0.5)
        self.std.target    = numpy.std(self.get_last_n_seconds(0.1))

# ------------------------------------------------------------------------------------------------ #
