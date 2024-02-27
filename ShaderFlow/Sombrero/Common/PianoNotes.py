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
    @functools.lru_cache
    def from_index(cls, note: int, **kwargs) -> Self:
        return cls(note=note, **kwargs)

    @classmethod
    @functools.lru_cache
    def from_name(cls, name: str, **kwargs) -> Self:
        return cls(note=BrokenPianoNote.name_to_index(name), **kwargs)

    @classmethod
    @functools.lru_cache
    def from_frequency(cls, frequency: float, **kwargs) -> Self:
        return cls(note=BrokenPianoNote.frequency_to_index(frequency), **kwargs)

    # # Conversion

    @staticmethod
    @functools.lru_cache
    def index_to_name(index: int) -> str:
        return f"{PIANO_NOTES[index % 12]}{index//12 - 1}"

    @staticmethod
    @functools.lru_cache
    def index_to_frequency(index: int, *, tuning: float=440) -> float:
        return tuning * 2**((index - 69)/12)

    @staticmethod
    @functools.lru_cache
    def name_to_index(name: str) -> int:
        note, octave = name[:-1], int(name[-1])
        return PIANO_NOTES.index(note) + 12*(octave + 1)

    @staticmethod
    @functools.lru_cache
    def name_to_frequency(name: str, *, tuning: float=440) -> float:
        return BrokenPianoNote.index_to_frequency(BrokenPianoNote.name_to_index(name), tuning=tuning)

    @staticmethod
    @functools.lru_cache
    def frequency_to_index(frequency: float, *, tuning: float=440) -> int:
        return round(12*math.log2(frequency/tuning) + 69)

    @staticmethod
    @functools.lru_cache
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