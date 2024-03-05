from . import *


@define
class BucketInterval:
    start: float
    end:   float
    data:  Any

@define
class BucketTree:
    trees: Dict[int, Dict[int, Deque[Any]]] = Factory(dict)
    size: float = 5.0

    def index(self, index: int) -> int:
        return int(index/self.size)

    def subtree(self, index: int, B: int) -> IntervalTree:
        return self.trees.setdefault(index, {}).setdefault(B, deque())

    def subtree_range(self, start: float, end: float) -> range:
        return range(self.index(start) - 3, self.index(end) + 1)

    def add(self, index: int, start: float, end: float, data: Any):
        self.subtree(index, self.index(start)).append(BucketInterval(start, end, data))

    def overlap(self, index: int, start: float, end: float) -> Iterable[BucketInterval]:
        for tree in self.subtree_range(start, end):
            for interval in self.subtree(index, tree):
                if interval.end >= start and interval.start <= end:
                    yield interval

    def at(self, index: int, time: float) -> Iterable[BucketInterval]:
        for interval in self.subtree(index, self.index(time)):
            if interval.start <= time <= interval.end:
                yield interval

    def __iter__(self) -> Iterator[BucketInterval]:
        for tree in self.trees.values():
            for intervals in tree.values():
                yield from intervals

    def start(self) -> float:
        return min(interval.start for interval in self)

    def end(self) -> float:
        return max(interval.end for interval in self)

# -------------------------------------------------------------------------------------------------|

@define(slots=False)
class BrokenPiano:
    tree: BucketTree = Factory(BucketTree)
    tempo: Deque[Tuple[Seconds, BPM]] = Factory(deque)
    global_minimum_note: int = None
    global_maximum_note: int = None

    # # Base actions

    def add_note(self, note: BrokenPianoNote):
        self.global_minimum_note = min(self.global_minimum_note or 128, note.note)
        self.global_maximum_note = max(self.global_maximum_note or   0, note.note)
        self.tree.add(note.note, note.start, note.end, note)

    def clear(self):
        self.tree = BucketTree()

    def notes_between(self, index: int, start: Seconds, end: Seconds) -> Iterator[BrokenPianoNote]:
        for interval in self.tree.overlap(index, start, end):
            yield interval.data

    def notes_at(self, index: int, time: Seconds) -> Iterator[BrokenPianoNote]:
        for interval in self.tree.at(index, time):
            yield interval.data

    def tempo_at(self, time: Seconds) -> Optional[BPM]:
        for when, tempo in self.tempo:
            if when <= time:
                return tempo

    @property
    def notes(self) -> Iterator[BrokenPianoNote]:
        for interval in self.tree:
            yield interval.data

    @property
    def duration(self) -> Seconds:
        return self.tree.end()

    @property
    def end(self) -> Seconds:
        return self.tree.end()

    @end.setter
    def end(self, value: Seconds):
        self.force_interval(start=self.start, end=value)

    @property
    def start(self) -> Seconds:
        return self.tree.begin()

    @start.setter
    def start(self, value: Seconds):
        self.force_interval(start=value, end=self.end)

    def force_interval(self, start: Seconds, end: Seconds):
        tree  = BucketTree()
        ratio = ((end + start)/self.tree.end())
        off   = self.tree.begin()
        for interval in self.tree:
            s, e = ((interval.begin-off)*ratio-start, (interval.end - off)*ratio - start)
            tree.add(interval.data, s, e, note)
        self.tree = tree

    @property
    def note_range(self) -> range:
        return range(self.global_minimum_note, self.global_maximum_note)

    # # Initialization

    @classmethod
    def from_midi(cls, path: Path):
        return cls().load_midi(path)

    # # Utilities

    def load_midi(self, path: Path):
        import pretty_midi

        if not (path := BrokenPath(path)).exists():
            log.warning(f"Input Midi file not found ({path})")
            return

        self.clear()

        with Halo(log.info(f"Loading Midi file at ({path})")) as halo:
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

    @property
    def minimum_velocity(self) -> int:
        return min(note.velocity for note in self.notes)

    @property
    def maximum_velocity(self) -> int:
        return max(note.velocity for note in self.notes)

    def normalize_velocities(self, minimum: int=60, maximum: int=100):
        mi, ma = (self.minimum_velocity, self.maximum_velocity)

        # Safe against (minimum-maximum)=0
        def new(velocity: int) -> int:
            if ma == mi: return (maximum+minimum)//2
            return int((velocity-mi)/(ma-mi)*(maximum-minimum)+minimum)

        for note in self.notes:
            note.velocity = new(note.velocity)

    def __iter__(self) -> Iterator[BrokenPianoNote]:
        yield from self.tree

# -------------------------------------------------------------------------------------------------|

@define
class ShaderFlowPiano(ShaderFlowModule, BrokenPiano):
    name:               str     = "iPiano"
    keys_texture:       ShaderFlowTexture = None
    roll_texture:       ShaderFlowTexture = None
    channel_texture:    ShaderFlowTexture = None
    roll_time:          Seconds = 2
    height:             float   = 0.275
    black_ratio:        float   = 0.6
    minimum_visible:    int     = 12*3
    roll_note_limit:    int     = 256
    extra_side_keys:    int     = 6
    time_offset:        Seconds = 0
    time_scale:         float   = 1
    dynamic_note_ahead: float   = 4

    key_press_dynamics: ShaderFlowDynamics = Factory(lambda: ShaderFlowDynamics(
        value=numpy.zeros(128, dtype=f32), frequency=4, zeta=0.4, response=0, precision=0
    ))

    note_range_dynamics: ShaderFlowDynamics = Factory(lambda: ShaderFlowDynamics(
        value=numpy.zeros(2, dtype=f32), frequency=0.05, zeta=1/SQRT2, response=0,
    ))

    # # Fluidsynth

    fluidsynth: Any = None
    soundfont:  Any = None

    def fluid_load(self, sf2: Path, driver: str=("pulseaudio" if BrokenPlatform.OnLinux else None)) -> None:
        if not (sf2 := BrokenPath(sf2)).exists():
            log.warning(f"Couldn't load SoundFont from path ({sf2}), will not have Real Time MIDI Audio")
            return

        # Download FluidSynth for Windows
        if BrokenPlatform.OnWindows:
            FLUIDSYNTH = "https://github.com/FluidSynth/fluidsynth/releases/download/v2.3.4/fluidsynth-2.3.4-win10-x64.zip"
            BrokenPath.extract(BrokenPath.download(FLUIDSYNTH), BROKEN.DIRECTORIES.EXTERNALS, PATH=True)
        elif BrokenPlatform.OnMacOS:
            if not shutil.which("fluidsynth"):
                shell("brew", "install", "fluidsynth")
        elif BrokenPlatform.OnLinux:
            log.minor(f"Please install FluidSynth in your Package Manager if needed")

        import fluidsynth
        self.fluidsynth = fluidsynth.Synth()
        self.soundfont  = self.fluidsynth.sfload(str(sf2))
        self.fluidsynth.set_reverb(1, 1, 80, 1)
        self.fluidsynth.start(driver=driver)
        for channel in range(16):
            self.fluid_select(channel, 0, 0)

    def fluid_select(self, channel: int=0, bank: int=0, preset: int=0) -> None:
        if self.fluidsynth:
            self.fluidsynth.program_select(channel, self.soundfont, bank, preset)

    def fluid_key_down(self, note: int, velocity: int=127, channel: int=0) -> None:
        if self.fluidsynth:
            self.fluidsynth.noteon(channel, note, velocity)

    def fluid_key_up(self, note: int, channel: int=0) -> None:
        if self.fluidsynth:
            self.fluidsynth.noteoff(channel, note)

    def fluid_all_notes_off(self) -> None:
        if self.fluidsynth:
            for channel, note in itertools.product(range(16), range(128)):
                self.fluidsynth.noteoff(channel, note)

    def fluid_render(self,
        midi: PathLike,
        soundfont: PathLike=None,
        output: PathLike=None
    ) -> Path:
        if not self.fluidsynth:
            return

        # Get temporary cached file
        if output is None:
            midi_hash = hashlib.md5(BrokenPath(midi).read_bytes()).hexdigest()
            output = Path(tempfile.gettempdir())/f"ShaderFlow-Midi2Audio-{midi_hash}.wav"

        import midi2audio
        with Halo(log.info(f"Rendering FluidSynth Midi ({midi}) → ({output})")):
            midi2audio.FluidSynth(soundfont).midi_to_audio(midi, output)

        # Normalize audio with FFmpeg
        normalized = output.with_suffix(".aac")
        with Halo(log.info(f"Normalizing Audio ({output}) → ({normalized})")):
            (BrokenFFmpeg()
                .quiet()
                .overwrite()
                .input(output)
                .custom("-filter:a", "loudnorm")
                .custom("-c:a", FFmpegAudioCodec.AAC)
                .custom("-b:a", "300k")
                .output(normalized)
            ).run()

        return BrokenPath(normalized)

    # # Piano roll

    def _empty_keys(self) -> ndarray:
        return numpy.zeros((128, 1), f32)

    def _empty_roll(self) -> ndarray:
        return numpy.zeros((128, self.roll_note_limit, 4), f32)

    def __build__(self):
        self.keys_texture    = self.add(ShaderFlowTexture(f"{self.name}Keys")).from_numpy(self._empty_keys(), components=1)
        self.channel_texture = self.add(ShaderFlowTexture(f"{self.name}Chan")).from_numpy(self._empty_keys(), components=1)
        self.roll_texture    = self.add(ShaderFlowTexture(f"{self.name}Roll")).from_numpy(self._empty_roll(), "f4")
        self.tempo_texture   = self.add(ShaderFlowTexture(f"{self.name}Tempo")).from_numpy(numpy.zeros((100, 1, 2), "f4"), components=2)
        self.tree.size       = self.roll_time

    def load_midi(self, path: PathLike):
        super().load_midi(path=path)

        self.tempo_texture.clear()
        for offset, (when, tempo) in enumerate(self.tempo):
            self.tempo_texture.write(data=struct.pack("ff", when, tempo), viewport=(0, offset, 1, 1))

    # A (128 Notes x 16 Channels) matrix of the end-most note being played
    _playing_matrix: List[List[Optional[BrokenPianoNote]]] = Factory(lambda: [[None]*16 for _ in range(128)])

    def __update__(self):

        # Utilities and trackers
        time        = (self.scene.time - self.time_offset)
        in_range    = lambda note, end: (note.end+time>=time) and (note.start<=end+time)
        time_travel = lambda cond: cond if (self.time_scale > 0) else (not cond)
        lookup      = self.roll_time + self.dynamic_note_ahead
        upcoming    = set()

        # # Get and update pressed keys
        self.key_press_dynamics.target.fill(0)
        roll = self._empty_roll()

        # Channel '-1' means the note is not being played !
        self.channel_texture.write(self._empty_keys() - 1)

        # No need to check for the entire range 😉
        for midi in range(self.global_minimum_note, self.global_maximum_note):
            matrix_row = self._playing_matrix[midi]
            simultaneous = 0

            for note in self.notes_between(midi, time, time+lookup):
                upcoming.add(midi)

                # This note is being played
                if in_range(note, self.scene.frametime):
                    self.key_press_dynamics.target[midi] = note.velocity
                    self.channel_texture.write(
                        data=numpy.array(note.channel, dtype="f4"),
                        viewport=(midi, 0, 1, 1)
                    )

                # Build a 2D Grid of the piano keys being played
                # • Coordinate: (Note, #offset) @ (Start, End, Channel, Velocity)
                if (simultaneous<self.roll_note_limit) and in_range(note, self.roll_time):
                    roll[note.note, simultaneous] = (note.start, note.end, note.channel, note.velocity)
                    simultaneous += 1

                # Real time play notes condition
                if self.scene.rendering: continue
                if not self.fluidsynth:  continue
                if not in_range(note, self.scene.frametime): continue

                # Find empty slots or notes that will end soon, replace and play
                other = matrix_row[note.channel]
                if (other is None) or time_travel(other.end > note.end):
                    self.fluid_key_down(midi, note.velocity, note.channel)
                    matrix_row[note.channel] = note

            # Find notes that are not being played
            for channel in range(16 if self.scene.realtime else 0):
                if (other := matrix_row[channel]) and time_travel(other.end < time):
                    self.fluid_key_up(midi, other.channel)
                    matrix_row[channel] = None

        # The viewport should be present whenever the 'ahead' found keys
        self.note_range_dynamics.frequency = 1/lookup

        # Set dynamic note range to the globals on the start
        if sum(self.note_range_dynamics.value) == 0:
            self.note_range_dynamics.value[:] = (self.global_minimum_note, self.global_maximum_note)

        # Set new targets for dynamic keys
        self.note_range_dynamics.target = numpy.array([
            min(upcoming, default=self.global_minimum_note),
            max(upcoming, default=self.global_maximum_note)
        ], f32)

        # Write to keys textures
        self.note_range_dynamics.next(dt=abs(self.scene.dt))
        self.key_press_dynamics.next(dt=abs(self.scene.dt))
        self.keys_texture.write(data=self.key_press_dynamics.value)
        self.roll_texture.write(roll)

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",   f"{self.name}GlobalMin",  self.global_minimum_note)
        yield ShaderVariable("uniform", "int",   f"{self.name}GlobalMax",  self.global_maximum_note)
        yield ShaderVariable("uniform", "vec2",  f"{self.name}Dynamic",    self.note_range_dynamics.value)
        yield ShaderVariable("uniform", "float", f"{self.name}RollTime",   self.roll_time)
        yield ShaderVariable("uniform", "float", f"{self.name}Extra",      self.extra_side_keys)
        yield ShaderVariable("uniform", "float", f"{self.name}Height",     self.height)
        yield ShaderVariable("uniform", "int",   f"{self.name}Limit",      self.roll_note_limit)
        yield ShaderVariable("uniform", "float", f"{self.name}BlackRatio", self.black_ratio)
