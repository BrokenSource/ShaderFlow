from . import *


@define(slots=False)
class BrokenPianoRoll:
    tree:         intervaltree.IntervalTree = Factory(intervaltree.IntervalTree)
    minimum_note: int = None
    maximum_note: int = None

    # # Base actions

    def add_notes(self, notes: BrokenPianoNote | Iterable[BrokenPianoNote]):
        for note in BrokenUtils.flatten(notes):
            self.tree.addi(note.start, note.end, note)
            self.minimum_note = min(self.minimum_note or 128, note.note)
            self.maximum_note = max(self.maximum_note or   0, note.note)

    def notes_between(self, start: Seconds, end: Seconds) -> Iterator[BrokenPianoNote]:
        for interval in self.tree[start:end]:
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
    def note_range(self) -> range:
        return range(self.minimum_note, self.maximum_note)

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

    def __iter__(self) -> Iterator[BrokenPianoNote]:
        yield from self.tree


@define
class SombreroPianoRoll(SombreroModule, BrokenPianoRoll):
    name:   str             = "iPiano"
    keys:   SombreroTexture = None
    roll:   SombreroTexture = None
    chan:   SombreroTexture = None
    length: Seconds         = 5
    height: float           = 0.2
    limit:  int             = 128
    extra:  int             = 2
    ahead:  Seconds         = 0
    speed:  float           = 1
    dynamics: SombreroDynamics = Factory(lambda: SombreroDynamics(
        value=numpy.zeros(128, dtype=numpy.float32),
        frequency=5, zeta=1, response=1, precision=0
    ))

    # # Fluidsynth

    fluidsynth: Any = None
    soundfont:  Any = None

    def fluid_load(self,
        sf2: Path,
        driver: str=("pulseaudio" if BrokenPlatform.OnLinux else "coreaudio"),
    ) -> None:
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

    @staticmethod
    @functools.lru_cache
    def _empty() -> numpy.ndarray:
        return numpy.zeros(128, dtype=numpy.float32)

    def __build__(self):
        self.keys = self.add(SombreroTexture(name=f"{self.name}Keys", mipmaps=False, filter="linear"))
        self.keys.from_raw(size=(128, 1), components=1, data=self._empty())
        self.chan = self.add(SombreroTexture(name=f"{self.name}Chan", mipmaps=False, filter="linear"))
        self.chan.from_raw(size=(128, 1), components=1, data=self._empty())
        self.roll = self.add(SombreroTexture(name=f"{self.name}Roll", mipmaps=False, filter="linear"))
        self.roll.from_raw(size=(128, self.limit), components=4)

    _playing: Set[BrokenPianoNote] = Factory(set)

    def __update__(self):
        time = (self.scene.time - self.ahead)*self.speed

        # # Get and update pressed keys
        self.dynamics.target.fill(0)
        playing = set(self.notes_between(time, time + self.scene.frametime/self.speed))

        for note in playing:
            self.dynamics.target[note.note] = note.velocity
            self.chan.write(data=numpy.array(note.channel, dtype="f4"), viewport=(note.note, 0, 1, 1))

        self.dynamics.next(dt=abs(self.scene.dt))
        self.keys.write(data=self.dynamics.value)

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
        # • Coordinate: (Note, #Index)
        # • Pixel: (Start, End, Channel, Velocity)
        visible = self.notes_between(time, time+self.length)
        offsets = numpy.zeros((128), dtype=int) - 1
        self.roll.write(data=numpy.zeros((128, self.limit, 4), dtype=numpy.float32))

        for note in visible:
            start = (note.start - time)/self.length
            end   = (note.end   - time)/self.length
            offsets[note.note] += 1
            self.roll.write(
                data=numpy.array([start, end, note.channel, note.velocity], dtype=numpy.float32),
                viewport=(note.note, offsets[note.note], 1, 1),
            )

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable("uniform", "int",   f"{self.name}Min",    self.minimum_note - self.extra)
        yield ShaderVariable("uniform", "int",   f"{self.name}Max",    self.maximum_note + self.extra)
        yield ShaderVariable("uniform", "float", f"{self.name}Height", self.height)
        yield ShaderVariable("uniform", "int",   f"{self.name}Limit",  self.limit)
