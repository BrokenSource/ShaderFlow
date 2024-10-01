import hashlib
import itertools
import shutil
import struct
import tempfile
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

import numpy
from attr import Factory, define
from halo import Halo

from Broken import BROKEN, BrokenPath, BrokenPlatform, log, shell
from Broken.Externals.FFmpeg import BrokenFFmpeg
from Broken.Types import BPM, Seconds
from ShaderFlow.Common.Notes import BrokenPianoNote
from ShaderFlow.Module import ShaderModule
from ShaderFlow.Modules.Dynamics import DynamicNumber
from ShaderFlow.Texture import ShaderTexture
from ShaderFlow.Variable import ShaderVariable, Uniform

MAX_CHANNELS = 32
MAX_ROLLING = 256
MAX_NOTE = 128

@define
class ShaderPiano(ShaderModule):
    name: str = "iPiano"
    """Texture name prefixes for this Module"""

    tempo: Deque[Tuple[Seconds, BPM]] = Factory(deque)
    """List of tempo changes at (seconds, bpm)"""

    keys_texture: ShaderTexture = None
    """Velocities texture, X is MIDI index, Y is Velocity, size (MAX_NOTE, 1)"""

    channel_texture: ShaderTexture = None
    """Channel being played texture, X is MIDI index, Y is Channel, size (MAX_NOTE, 1)"""

    roll_texture: ShaderTexture = None
    """Piano roll'ling notes main texture'. The X coordinate is the MIDI index, pixels contains data
    (start, end, channel, velocity), of each playing key on the Y. Size (MAX_ROLLING, MAX_NOTE)"""

    time_offset: Seconds = 0
    """Offset the notes being played search from the current time"""

    roll_time: Seconds = 2
    """How long the notes are visible, 'roll for'"""

    height: float = 0.275
    """Height of the piano in the shader (0-1)"""

    black_ratio: float = 0.6
    """How long are black keys compared to white keys"""

    global_minimum_note: int = MAX_NOTE
    """The lowest note in the loaded notes"""

    global_maximum_note: int = 0
    """The highest note in the loaded notes"""

    extra_side_keys: int = 6
    """Display the dynamic range plus this many keys on each side"""

    future_range_lookup: Seconds = 2
    """Lookup notes in (roll_time + this) for setting the dynamic ranges"""

    release_before_end: Seconds = 0.05
    """Workaround for the transition between close/glued to be perceived"""

    key_press_dynamics: DynamicNumber = Factory(lambda: DynamicNumber(
        value=numpy.zeros(MAX_NOTE, dtype=numpy.float32),
        frequency=4, zeta=0.4, response=0, precision=0
    ))

    note_range_dynamics: DynamicNumber = Factory(lambda: DynamicNumber(
        value=numpy.zeros(2, dtype=numpy.float32),
        frequency=0.05, zeta=1/(2**0.5), response=0,
    ))

    tree: Dict[int, Dict[int, Deque[BrokenPianoNote]]] = Factory(dict)
    """Internal data structure for storing the notes"""

    @property
    def lookup_time(self) -> Seconds:
        """The full lookup time we should care for future notes (rolling+future range)"""
        return (self.roll_time + self.future_range_lookup)

    # # Internal

    def build(self):
        self.keys_texture    = ShaderTexture(scene=self.scene, name=f"{self.name}Keys").from_numpy(self._empty_keys())
        self.channel_texture = ShaderTexture(scene=self.scene, name=f"{self.name}Chan").from_numpy(self._empty_keys())
        self.roll_texture    = ShaderTexture(scene=self.scene, name=f"{self.name}Roll").from_numpy(self._empty_roll())
        self.tempo_texture   = ShaderTexture(scene=self.scene, name=f"{self.name}Tempo").from_numpy(numpy.zeros((100, 1, 2), numpy.float32))

    def _empty_keys(self) -> numpy.ndarray:
        return numpy.zeros((1, MAX_NOTE), dtype=numpy.float32)

    def _empty_roll(self) -> numpy.ndarray:
        return numpy.zeros((MAX_NOTE, MAX_ROLLING, 4), dtype=numpy.float32)

    # # Data structure

    @staticmethod
    def _ranges(start: Seconds, end: Seconds) -> Iterable[int]:
        return range(int(start), int(end)+1)

    def clear(self):
        self.tree.clear()

    def add_note(self, note: Optional[BrokenPianoNote]) -> None:
        if note is None:
            return
        for index in self._ranges(note.start, note.end):
            self.tree.setdefault(note.note, dict()).setdefault(index, deque()).append(note)
        self.update_global_ranges(note.note)

    @property
    def notes(self) -> Iterable[BrokenPianoNote]:
        for block in self.tree.values():
            for notes in block.values():
                yield from notes

    @property
    def duration(self) -> float:
        return max((note.end for note in self.notes), default=0)

    def __iter__(self) -> Iterable[BrokenPianoNote]:
        return self.notes

    def notes_between(self, index: int, start: Seconds, end: Seconds) -> Iterable[BrokenPianoNote]:
        exists = set()
        for other in self._ranges(start, end):
            for note in self.tree.get(index, dict()).get(other, deque()):
                if (note.start > end):
                    continue
                if (id(note) in exists):
                    continue
                exists.add(id(note))
                yield note

    def update_global_ranges(self, note: int) -> None:
        self.global_minimum_note = min(self.global_minimum_note, note)
        self.global_maximum_note = max(self.global_maximum_note, note)

    @property
    def maximum_velocity(self) -> Optional[int]:
        return max((note.velocity for note in self.notes), default=None)

    @property
    def minimum_velocity(self) -> Optional[int]:
        return min((note.velocity for note in self.notes), default=None)

    def normalize_velocities(self, minimum: int=100, maximum: int=100) -> None:
        ma, mi = (self.maximum_velocity, self.minimum_velocity)

        # Safe against (minimum-maximum=0)
        def new(velocity: int) -> int:
            if (ma != mi):
                int((velocity - mi)/(ma - mi)*(maximum - minimum) + minimum)
            return int((maximum + minimum) / 2)

        for note in self.notes:
            note.velocity = new(note.velocity)

    def load_midi(self, path: Path):
        import pretty_midi

        if not (path := BrokenPath.get(path)).exists():
            self.log_warning(f"Input Midi file not found ({path})")
            return

        with Halo(log.info(f"Loading Midi file at ({path})")):
            midi = pretty_midi.PrettyMIDI(str(path))
            for channel, instrument in enumerate(midi.instruments):
                if instrument.is_drum:
                    pass
                for note in instrument.notes:
                    self.add_note(BrokenPianoNote(
                        note=note.pitch,
                        start=note.start,
                        end=note.end,
                        channel=channel,
                        velocity=note.velocity,
                    ))
            # Add tempo changes
            for when, tempo in zip(*midi.get_tempo_changes()):
                self.tempo.append((when, tempo))

        self.tempo_texture.clear()

        for offset, (when, tempo) in enumerate(self.tempo):
            self.tempo_texture.write(data=struct.pack("ff", when, tempo), viewport=(0, offset, 1, 1))

    # # Core Logic

    # A (MAX_MIDI Notes x MAX_CHANNELS Channels) matrix of the end-most note being played
    _playing_matrix: List[List[Optional[BrokenPianoNote]]] = Factory(lambda: [[None]*MAX_CHANNELS for _ in range(MAX_NOTE)])

    def update(self):

        # Utilities and trackers
        time = (self.scene.time + self.time_offset)
        upcoming = set()

        # # Get and update pressed keys
        self.key_press_dynamics.target.fill(0)
        roll = self._empty_roll()

        # Channel '-1' means the note is not being played !
        channels = (self._empty_keys() - 1)

        # Optimization: No need to check for the entire range 😉
        for midi in range(self.global_minimum_note, self.global_maximum_note+1):
            simultaneous = 0

            for note in self.notes_between(midi, time, time+self.lookup_time):
                upcoming.add(midi)

                # Ignore notes out of the viewport
                if (note.start >= time+self.roll_time):
                    continue

                # Build a 2D Grid of the piano keys being played
                # • Coordinate: (Note, #offset) @ (Start, End, Channel, Velocity)
                if (simultaneous < MAX_ROLLING):
                    roll[note.note, simultaneous] = (note.start, note.end, note.channel, note.velocity)
                    simultaneous += 1

                # Skip non-playing notes
                if not (note.start <= time <= note.end):
                    continue

                # Workaround: Don't play the full note, so close notes velocities are perceived twice
                _note_too_small = (note.end - note.start) < self.release_before_end
                _shorter_note = (time < (note.end - self.release_before_end))

                if (_shorter_note or _note_too_small):
                    self.key_press_dynamics.target[midi] = note.velocity

                # Either way, the channel must be colored
                channels[0][midi] = note.channel

                # Find empty slots or notes that will end soon, replace and play
                other = self._playing_matrix[midi][note.channel]
                if (other is None) or (other.end > note.end):
                    play_velocity = int(128*((note.velocity/128)**0.5))
                    self.fluid_key_down(midi, play_velocity, note.channel)
                    self._playing_matrix[midi][note.channel] = note

            # Find notes that are not being played
            for channel in range(MAX_CHANNELS * self.scene.realtime):
                if (other := self._playing_matrix[midi][channel]) and (other.end < time):
                    self._playing_matrix[midi][channel] = None
                    self.fluid_key_up(midi, other.channel)

        # Dynamic zoom velocity based on future lookup
        self.note_range_dynamics.frequency = 0.5/self.lookup_time

        # Set dynamic note range to the globals on the start
        if sum(self.note_range_dynamics.value) == 0:
            self.note_range_dynamics.value[:] = (self.global_minimum_note, self.global_maximum_note)

        # Set new targets for dynamic keys
        self.note_range_dynamics.target[:] = (
            min(upcoming, default=self.global_minimum_note),
            max(upcoming, default=self.global_maximum_note)
        )

        # Write to keys textures
        self.note_range_dynamics.next(dt=abs(self.scene.dt))
        self.key_press_dynamics.next(dt=abs(self.scene.dt))
        self.keys_texture.write(data=self.key_press_dynamics.value)
        self.roll_texture.write(data=roll)
        self.channel_texture.write(data=channels)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int",   f"{self.name}GlobalMin",  self.global_minimum_note)
        yield Uniform("int",   f"{self.name}GlobalMax",  self.global_maximum_note)
        yield Uniform("vec2",  f"{self.name}Dynamic",    self.note_range_dynamics.value)
        yield Uniform("float", f"{self.name}RollTime",   self.roll_time)
        yield Uniform("float", f"{self.name}Extra",      self.extra_side_keys)
        yield Uniform("float", f"{self.name}Height",     self.height)
        yield Uniform("int",   f"{self.name}Limit",      MAX_ROLLING)
        yield Uniform("float", f"{self.name}BlackRatio", self.black_ratio)

    # # Fluidsynth

    fluidsynth: Any = None
    soundfont:  Any = None

    def fluid_load(self, sf2: Path, driver: str=("pulseaudio" if BrokenPlatform.OnLinux else None)) -> None:
        if not (sf2 := BrokenPath.get(sf2)).exists():
            self.log_warning(f"Couldn't load SoundFont from path ({sf2}), will not have Real Time MIDI Audio")
            return

        # Download FluidSynth for Windows
        if BrokenPlatform.OnWindows:
            FLUIDSYNTH = "https://github.com/FluidSynth/fluidsynth/releases/download/v2.3.4/fluidsynth-2.3.4-win10-x64.zip"
            BrokenPath.add_to_path(BrokenPath.extract(BrokenPath.download(FLUIDSYNTH), BROKEN.DIRECTORIES.EXTERNALS), recurse=True)
        elif BrokenPlatform.OnMacOS:
            if not shutil.which("fluidsynth"):
                shell("brew", "install", "fluidsynth")
        elif BrokenPlatform.OnLinux:
            self.log_warning("Please install FluidSynth in your Package Manager if needed")

        import fluidsynth
        self.fluidsynth = fluidsynth.Synth()
        with Halo(log.info(f"Loading FluidSynth SoundFont ({sf2.name})")):
            self.soundfont = self.fluidsynth.sfload(str(sf2))
        self.fluidsynth.set_reverb(1, 1, 80, 1)
        self.fluidsynth.start(driver=driver)
        for channel in range(MAX_CHANNELS):
            self.fluid_select(channel, 0, 0)

    def fluid_select(self, channel: int=0, bank: int=0, preset: int=0) -> None:
        if self.fluidsynth and self.scene.realtime:
            self.fluidsynth.program_select(channel, self.soundfont, bank, preset)

    def fluid_key_down(self, note: int, velocity: int=127, channel: int=0) -> None:
        if self.fluidsynth and self.scene.realtime:
            self.fluidsynth.noteon(channel, note, velocity)

    def fluid_key_up(self, note: int, channel: int=0) -> None:
        if self.fluidsynth and self.scene.realtime:
            self.fluidsynth.noteoff(channel, note)

    def fluid_all_notes_off(self) -> None:
        if self.fluidsynth and self.scene.realtime:
            for channel, note in itertools.product(range(MAX_CHANNELS), range(MAX_NOTE)):
                self.fluidsynth.noteoff(channel, note)

    def fluid_render(self,
        midi: Path,
        soundfont: Path=None,
        output: Path=None
    ) -> Path:
        if not self.fluidsynth:
            return

        # Get temporary cached file
        if output is None:
            midi_hash = hashlib.md5(BrokenPath.get(midi).read_bytes()).hexdigest()
            output = Path(tempfile.gettempdir())/f"ShaderFlow-Midi2Audio-{midi_hash}.wav"

        import midi2audio
        with Halo(log.info(f"Rendering FluidSynth Midi ({midi}) → ({output})")):
            midi2audio.FluidSynth(soundfont).midi_to_audio(midi, output)

        # Normalize audio with FFmpeg
        normalized = output.with_suffix(".aac")
        with Halo(log.info(f"Normalizing Audio ({output}) → ({normalized})")):
            (BrokenFFmpeg()
                .quiet()
                .input(output)
                .filter("loudnorm")
                .aac()
                .output(normalized)
            ).run()

        return BrokenPath.get(normalized)