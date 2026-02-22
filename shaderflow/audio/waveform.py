import math
from collections.abc import Iterable
from enum import Enum

import numpy as np
from attrs import define

from shaderflow.audio import BrokenAudio
from shaderflow.module import ShaderModule
from shaderflow.texture import ShaderTexture
from shaderflow.variable import ShaderVariable, Uniform


class WaveformReducer(Enum):
    def Average(x: np.ndarray) -> np.ndarray:
        return np.sqrt(np.mean(np.abs(x), axis=2))

    def RMS(x: np.ndarray) -> np.ndarray:
        return np.sqrt(np.sqrt(np.mean(x**2, axis=2))*(2**0.5))

    def STD(x: np.ndarray) -> np.ndarray:
        return np.sqrt(np.std(x, axis=2))

@define
class ShaderWaveform(ShaderModule):

    name: str = "iWaveform"
    """Prefix name and Texture name of the Shader Variables"""

    audio: BrokenAudio = None
    """Audio class to read the data from"""

    length: float = 3
    """Horizontal length of the Waveform content"""

    samplerate: float = 60
    """Number of bars per second"""

    reducer: WaveformReducer = WaveformReducer.Average
    """How to convert a (channels, length, samples) chunks into (channels, length)"""

    smooth: bool = True
    """Enables Linear interpolation on the Texture, not much useful for Bars mode"""

    texture: ShaderTexture = None
    """Internal managed Texture"""

    @property
    def length_samples(self) -> int:
        return int(max(1, self.length*self.scene.fps))

    def build(self):
        self.texture = ShaderTexture(
            scene=self.scene,
            filter=("linear" if self.smooth else "nearest"),
            components=self.audio.channels,
            name=self.name,
            width=self._points,
            height=1,
            mipmaps=False,
            dtype=np.float32,
        ).repeat(False)

    @property
    def chunk_size(self) -> int:
        return max(1, int(self.length*self.audio.samplerate/self._points))

    @property
    def _points(self) -> int:
        return self.length*self.samplerate

    @property
    def _offset(self) -> int:
        return self.audio.tell % self.chunk_size

    @property
    def _cutoff(self) -> int:
        return int(self.chunk_size * math.floor(self.audio.buffer_size/self.chunk_size))

    def update(self):
        start  = -int(self.chunk_size*self._points + self._offset + 1)
        end    = -int(self._offset + 1)
        chunks = self.audio.data[:, start:end]
        chunks = chunks.reshape(self.audio.channels, -1, self.chunk_size)
        chunks = self.reducer(chunks)
        chunks = np.ascontiguousarray(chunks.T)
        self.texture.write(chunks)

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield Uniform("int", f"{self.name}Length", self.length_samples)
