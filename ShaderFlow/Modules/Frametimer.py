from collections import deque
from typing import Deque

import imgui
import numpy
from attr import Factory, define

from ShaderFlow.Module import ShaderModule


@define
class ShaderFrametimer(ShaderModule):
    frametimes: Deque[float] = Factory(deque)
    history: float = 2

    @property
    def length(self) -> int:
        return max(int(self.history * self.scene.fps), 10)

    # Framerate manipulation

    def update(self):
        self.frametimes.append(self.scene.rdt)
        while len(self.frametimes) > self.length:
            self.frametimes.popleft()

    def percent(self, percent: float=1) -> float:
        cut = int(len(self.frametimes) * (percent/100))
        return numpy.sort(self.frametimes)[-cut:]

    def __safe__(self, value):
        return value if value < 1e8 else 0

    # # Frametimes

    def frametime_average(self, percent: float=100) -> float:
        frametimes = self.percent(percent)
        return sum(frametimes) / (len(frametimes) + 1e-9)

    @property
    def frametime_maximum(self) -> float:
        return max(self.frametimes)

    @property
    def frametime_minimum(self) -> float:
        return min(self.frametimes)

    # # Framerates

    def framerate_average(self, percent: float=100) -> float:
        return self.__safe__(1.0 / (self.frametime_average(percent) + 1e-9))

    @property
    def framerate_maximum(self) -> float:
        return self.__safe__(1.0 / (self.frametime_minimum + 1e-9))

    @property
    def framerate_minimum(self) -> float:
        return self.__safe__(1.0 / (self.frametime_maximum + 1e-9))

    # ShaderFlow

    def ui(self):
        imgui.plot_lines(
            (
                f"Target  {self.scene.fps:7.3f} fps\n"
                f"Average {self.framerate_average(100):7.3f} fps\n"
                # f"Low 10% {self.framerate_average(10):7.3f} fps\n"
                # f"Low  1% {self.framerate_average(1):7.3f} fps\n"
                f"Maximum {self.framerate_maximum:7.3f} fps\n"
                f"Minimum {self.framerate_minimum:7.3f} fps\n"
            ),
            numpy.array(self.frametimes, dtype=numpy.float32),
            scale_min = 0,
            graph_size = (0, 70)
        )

        if (state := imgui.input_float("History (Seconds)", self.history, 0.5, 0.5, "%.2f"))[0]:
            self.history = max(0, state[1])
