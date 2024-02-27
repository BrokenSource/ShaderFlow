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
    height: float           = 0.18
    limit:  int             = 128
    extra:  int             = 4
    ahead:  Seconds         = 0
    dynamics: SombreroDynamics = Factory(lambda: SombreroDynamics(
        value=numpy.zeros(128, dtype=numpy.float32),
        frequency=3, zeta=1, response=0, precision=0
    ))

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

    def __update__(self):
        time = self.scene.time - self.ahead

        self.dynamics.target = self._empty()
        for note in self.notes_at(time):
            self.dynamics.target[note.note] = note.velocity
            self.chan.write(data=numpy.array(note.channel, dtype="f4"), viewport=(note.note, 0, 1, 1))
        self.dynamics.next(dt=abs(self.scene.dt))
        self.keys.write(data=self.dynamics.value)

        # Build a 2D Grid of the piano keys being played
        # • Coordinate: (Note, #Index)
        # • Pixel: (Start, End, Channel, Velocity)
        playing = self.notes_between(time, time+self.length)
        offsets = numpy.zeros((128), dtype=int) - 1
        self.roll.write(data=numpy.zeros((128, self.limit, 4), dtype=numpy.float32))

        for note in playing:
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
