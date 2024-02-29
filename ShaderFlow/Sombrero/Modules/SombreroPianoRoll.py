from . import *


@define(slots=False)
class BrokenPianoRoll:
    tree: intervaltree.IntervalTree = Factory(intervaltree.IntervalTree)
    global_minimum_note: int = None
    global_maximum_note: int = None

    # # Base actions

    def add_notes(self, notes: BrokenPianoNote | Iterable[BrokenPianoNote]):
        for note in BrokenUtils.flatten(notes):
            self.tree.addi(note.start, note.end, note)
            self.global_minimum_note = min(self.global_minimum_note or 128, note.note)
            self.global_maximum_note = max(self.global_maximum_note or   0, note.note)

    def notes_between(self, start: Seconds, end: Seconds) -> Iterator[BrokenPianoNote]:
        for interval in self.tree.overlap(start, end):
            yield interval.data

    def notes_at(self, time: Seconds) -> Iterator[BrokenPianoNote]:
        for interval in self.tree.at(time):
            yield interval.data

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
        tree  = intervaltree.IntervalTree()
        ratio = ((end + start)/self.tree.end())
        off   = self.tree.begin()
        for interval in self.tree:
            s, e = ((interval.begin - off)*ratio - start, (interval.end - off)*ratio - start)
            tree.add(intervaltree.Interval(s, e, interval.data.copy(start=s, end=e)))
        self.tree = tree

    @property
    def note_range(self) -> range:
        return range(self.global_minimum_note, self.global_maximum_note)

    # # Initialization

    @classmethod
    def from_notes(cls, notes: Iterable[BrokenPianoNote]):
        return cls().add_notes(notes)

    @classmethod
    def from_midi(cls, path: Path):
        return cls().add_midi(path)

    # # Utilities

    def add_midi(self, path: Path):
        import pretty_midi

        if not (path := BrokenPath(path)).exists():
            log.warning(f"Input Midi file not found ({path})")
            return

        log.info(f"Loading Midi file at ({path})")
        midi = pretty_midi.PrettyMIDI(str(path))

        for channel, instrument in enumerate(midi.instruments):
            for note in instrument.notes:
                if instrument.is_drum:
                    pass
                self.add_notes(BrokenPianoNote(
                    note=note.pitch,
                    start=note.start,
                    end=note.end,
                    channel=channel,
                    velocity=note.velocity,
                ))

        log.minor(f"Midi file duration: {midi.get_end_time()}s")

    @property
    def minimum_velocity(self) -> int:
        return min(note.velocity for note in self.notes)

    @property
    def maximum_velocity(self) -> int:
        return max(note.velocity for note in self.notes)

    def normalize_velocities(self, minimum: int=60, maximum: int=100):
        mi, ma = (self.minimum_velocity, self.maximum_velocity)
        for note in self.notes:
            lerp = (note.velocity - mi)/(ma - mi)*(maximum - minimum) + minimum
            note.velocity = int(lerp)

    def __iter__(self) -> Iterator[BrokenPianoNote]:
        yield from self.tree


@define
class SombreroPianoRoll(SombreroModule, BrokenPianoRoll):
    name:               str             = "iPiano"
    keys_texture:       SombreroTexture = None
    roll_texture:       SombreroTexture = None
    channel_texture:    SombreroTexture = None
    roll_duration:      Seconds         = 5
    key_height:         float           = 0.25
    black_ratio:        float           = 0.6
    roll_note_limit:    int             = 128
    extra_side_keys:    int             = 4
    time_offset:        Seconds         = 0
    time_scale:         float           = 1
    dynamic_note_ahead: float           = 10

    key_press_dynamics: SombreroDynamics = Factory(lambda: SombreroDynamics(
        value=numpy.zeros(128, dtype=numpy.float32),
        frequency=8, zeta=1, response=0, precision=0
    ))

    minimum_note_dynamics: SombreroDynamics = Factory(lambda: SombreroDynamics(
        frequency=0.05, zeta=1/SQRT2, response=0,
    ))

    maximum_note_dynamics: SombreroDynamics = Factory(lambda: SombreroDynamics(
        frequency=0.05, zeta=1/SQRT2, response=0,
    ))

    @property
    def extra_global_minimum(self) -> int:
        return self.global_minimum_note - self.extra_side_keys
    @property
    def extra_global_maximum(self) -> int:
        return self.global_maximum_note + self.extra_side_keys
    @property
    def extra_dynamic_minimum(self) -> int:
        return max(self.minimum_note_dynamics.value - self.extra_side_keys, self.extra_global_minimum)
    @property
    def extra_dynamic_maximum(self) -> int:
        return min(self.maximum_note_dynamics.value + self.extra_side_keys, self.extra_global_maximum)

    # # Fluidsynth

    fluidsynth: Any = None
    soundfont:  Any = None

    def fluid_load(self, sf2: Path, driver: str=("pulseaudio" if BrokenPlatform.OnLinux else "coreaudio")) -> None:
        if not (sf2 := BrokenPath(sf2)).exists():
            log.warning(f"Couldn't load SoundFont from path ({sf2}), will not have Real Time MIDI Audio")
            return
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

    def fluid_panic(self):
        if self.fluidsynth:
            for channel, note in itertools.product(range(16), range(128)):
                self.fluid_key_up(note, channel)

    # # Piano roll

    def _empty_keys(self) -> numpy.ndarray:
        return numpy.zeros((128, 1), dtype=numpy.float32)

    def _empty_roll(self) -> numpy.ndarray:
        return numpy.zeros((128, self.roll_note_limit, 4), dtype=numpy.float32)

    def __build__(self):
        self.keys_texture    = self.add(SombreroTexture(name=f"{self.name}Keys")).from_numpy(self._empty_keys(), components=1)
        self.channel_texture = self.add(SombreroTexture(name=f"{self.name}Chan")).from_numpy(self._empty_keys(), components=1)
        self.roll_texture    = self.add(SombreroTexture(name=f"{self.name}Roll")).from_numpy(self._empty_roll(), dtype="f4")

    _playing: Set[BrokenPianoNote] = Factory(set)

    def __update__(self):
        time = (self.scene.time - self.time_offset)*self.time_scale

        # # Get and update pressed keys
        self.key_press_dynamics.target.fill(0)
        playing = set(self.notes_between(time, time + self.scene.frametime/self.time_scale))

        for note in playing:
            self.key_press_dynamics.target[note.note] = note.velocity
            self.channel_texture.write(data=numpy.array(note.channel, dtype="f4"), viewport=(note.note, 0, 1, 1))

        self.key_press_dynamics.next(dt=abs(self.scene.dt))
        self.keys_texture.write(data=self.key_press_dynamics.value)

        # # Get the set difference of playing and _playing
        if not self.scene.rendering:
            for note in (playing - self._playing):
                self.fluid_key_down(note.note, note.velocity, note.channel)
                self._playing.add(note)
            # Fixme: Do not key up on some level of overlap or remove overlaps
            for note in (self._playing - playing):
                self.fluid_key_up(note.note, note.channel)
                self._playing.remove(note)

        # Build a 2D Grid of the piano keys being played
        # • Coordinate: (Note, #Index) @ (Start, End, Channel, Velocity)
        visible = self.notes_between(time, time+self.roll_duration)
        offsets = numpy.zeros((128), dtype=int) - 1
        self.roll_texture.write(self._empty_roll())

        for note in visible:
            start = (note.start - time)/self.roll_duration
            end   = (note.end   - time)/self.roll_duration
            offsets[note.note] += 1
            self.roll_texture.write(
                data=numpy.array([start, end, note.channel, note.velocity], dtype=numpy.float32),
                viewport=(note.note, offsets[note.note], 1, 1),
            )

        # Update dynamic minimum and maximum
        # Todo: Ugly code, might vectorize
        visible = list(self.notes_between(time, time+self.dynamic_note_ahead))
        self.minimum_note_dynamics.frequency = 1/self.dynamic_note_ahead
        self.maximum_note_dynamics.frequency = 1/self.dynamic_note_ahead
        self.minimum_note_dynamics.value = numpy.float32(self.minimum_note_dynamics.value or self.extra_global_minimum)
        self.maximum_note_dynamics.value = numpy.float32(self.maximum_note_dynamics.value or self.extra_global_maximum)
        self.minimum_note_dynamics.target = min((note.note for note in visible), default=self.extra_global_minimum)
        self.maximum_note_dynamics.target = max((note.note for note in visible), default=self.extra_global_maximum)
        self.minimum_note_dynamics.next(dt=abs(self.scene.dt))
        self.maximum_note_dynamics.next(dt=abs(self.scene.dt))

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",   f"{self.name}GlobalMin",  self.extra_global_minimum)
        yield ShaderVariable("uniform", "int",   f"{self.name}GlobalMax",  self.extra_global_maximum)
        yield ShaderVariable("uniform", "float", f"{self.name}DynamicMin", self.extra_dynamic_minimum)
        yield ShaderVariable("uniform", "float", f"{self.name}DynamicMax", self.extra_dynamic_maximum)
        yield ShaderVariable("uniform", "float", f"{self.name}Height",     self.key_height)
        yield ShaderVariable("uniform", "int",   f"{self.name}Limit",      self.roll_note_limit)
        yield ShaderVariable("uniform", "float", f"{self.name}BlackRatio", self.black_ratio)
