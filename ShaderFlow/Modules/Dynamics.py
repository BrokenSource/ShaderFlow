from __future__ import annotations

import math
from ast import Tuple
from copy import deepcopy
from ctypes import Union
from math import pi, tau
from numbers import Number
from typing import Iterable, Optional, Self

import numpy
from attr import define, field

from ShaderFlow.Module import ShaderModule
from ShaderFlow.Variable import ShaderVariable, Uniform

# Fixme: Move to Broken when ought to be used somewhere else?

@define(slots=False)
class DynamicNumber(Number):
    """
    Simulate on time domain a progressive second order system

    # Sources:
    - https://www.youtube.com/watch?v=KPoeNZZ6H4s <- Math mostly took from here, thanks @t3ssel8r
    - https://en.wikipedia.org/wiki/Semi-implicit_Euler_method
    - Control System classes on my university which I got 6/10 final grade

    This is a Python-port of the video's math, with custom implementation and extras
    """

    def _convert(self, value):
        return numpy.array(value, dtype=getattr(value, "dtype", self.dtype))

    def _set_target(self, attribute, value):
        target = self._convert(value)
        if (target.shape != getattr(self.value, "shape", None)):
            self.initial = deepcopy(target)
            self.value = deepcopy(target)
        return target

    value: Union[numpy.dtype, numpy.ndarray] = field(default=0)
    """The current value of the system. Prefer explicitly using it over the object itself"""

    target: Union[numpy.dtype, numpy.ndarray] = field(default=None, on_setattr=_set_target)
    """The target value the system is trying to reach, modeled by the parameters"""

    dtype: numpy.dtype = field(default=numpy.float32)
    """Data type of the NumPy vectorized data"""

    initial: Union[numpy.dtype, numpy.ndarray] = field(default=None)
    """Initial value of the system, defaults to first value set"""

    def __attrs_post_init__(self):
        self.value   = self._convert(self.value)
        self.target  = self._convert(self.target if (self.target is not None) else self.value)
        self.initial = deepcopy(self.value)

    frequency: float = 1.0
    """Natural frequency of the system in Hertz, "the speed the system responds to a change in input".
    Also, the frequency it tends to vibrate at, doesn't affect shape of the resulting motion"""

    zeta: float = 1.0
    """Damping coefficient, z=0 vibration never dies, z=1 is the critical limit where the system
    does not overshoot, z>1 increases this effect and the system takes longer to settle"""

    response:  float = 0.0
    """Defines the initial response "time" of the system, when r=1 the system responds instantly
    to changes on the input, when r=0 the system takes a bit to respond (smoothstep like), when r<0
    the system "anticipates" motion"""

    precision: float = 1e-6
    """If |target - value| < precision, the system stops updating to save computation"""

    integral: float = 0.0
    """Integral of the system, the sum of all values over time"""

    derivative: float = 0.0
    """Derivative of the system, the rate of change of the value in ($unit/second)"""

    acceleration: float = 0.0
    """Acceleration of the system, the rate of change of the derivative in ($unit/second^2)"""

    instant: bool = False
    """Update the system immediately to the target value, """

    @property
    def k1(self) -> float:
        """Y velocity coefficient"""
        return self.zeta/(pi * self.frequency)

    @property
    def k2(self) -> float:
        """Y acceleration coefficient"""
        return 1/(self.radians*self.radians)

    @property
    def k3(self) -> float:
        """X velocity coefficient"""
        return (self.response * self.zeta) / (tau * self.frequency)

    @property
    def radians(self) -> float:
        """Natural resonance frequency in radians per second"""
        return tau * self.frequency

    @property
    def damping(self) -> float:
        """Damping ratio of some sort"""
        return self.radians * (abs(self.zeta*self.zeta - 1.0))**0.5

    previous: float = 0
    """Previous target value"""

    def next(self, target: Number=None, dt: float=1.0) -> Number:
        """
        Update the system to the next time step, optionally with a new target value
        # Fixme: There is a HUGE potential for speed gains if we don't create many temporary ndarray

        Args:
            target: Next target value to reach, None for previous
            dt:     Time delta since last update

        Returns:
            The system's self.value
        """
        if not dt:
            return self.value

        # Update target
        if (target is not None):
            self.target = target

        # Instant mode
        if self.instant:
            self.value = self.target*1
            self.integral += self.value * dt
            self.derivative = 0
            self.acceleration = 0
            return self.value

        # Optimization: Do not compute if value within precision to target
        if abs(numpy.sum(self.target - self.value)) < self.precision:
            self.integral += self.value * dt
            return self.value

        # "Estimate velocity"
        velocity = (self.target - self.previous)/dt
        self.previous = self.target

        # "Clamp k2 to stable values without jitter"
        if (self.radians*dt < self.zeta):
            k2 = max(self.k1*dt, self.k2, 0.5*(self.k1+dt)*dt)
            k1 = self.k1

        # "Use pole matching when the system is very fast"
        else:
            t1 = math.exp(-1 * self.zeta * self.radians * dt)
            a1 = 2 * t1 * (math.cos if self.zeta <= 1 else math.cosh)(self.damping*dt)
            t2 = 1/(1 + t1*t1 - a1) * dt
            k1 = t2 * (1 - t1*t1)
            k2 = t2 * dt

        # Integrate values
        self.value       += (self.derivative * dt)
        self.acceleration = (self.target + self.k3*velocity - self.value - k1*self.derivative)/k2
        self.derivative  += (self.acceleration * dt)
        self.integral    += (self.value * dt)
        return self.value

    def set(self, value: Number):
        """Force the system to a new value"""
        self.target = deepcopy(value)
        self.value = deepcopy(value)

    def reset(self, instant: bool=False):
        """Reset the system to its initial state"""
        self.target = deepcopy(self.initial)
        if instant:
            self.value = deepcopy(self.initial)
        self.integral = 0
        self.derivative = 0
        self.acceleration = 0
        self.previous = 0

    @staticmethod
    def extract(*objects: Union[Number, Self]) -> Tuple[Number]:
        """Extract the values from DynamicNumbers objects or return the same object"""
        return tuple(obj.value if isinstance(obj, DynamicNumber) else obj for obj in objects)

    # # Number implementation

    def __str__(self) -> str:
        return str(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __int__(self) -> int:
        return int(self.value)

    def __mul__(self, other) -> Number:
        return self.value * other

    def __rmul__(self, other) -> Self:
        return self * other

    def __add__(self, other) -> Self:
        return self.value + other

    def __radd__(self, other) -> Self:
        return self + other

    def __sub__(self, other) -> Self:
        return self.value - other

    def __rsub__(self, other) -> Self:
        return self - other

    def __truediv__(self, other) -> Self:
        return self.value / other

    def __rtruediv__(self, other) -> Self:
        return self / other

    def __floordiv__(self, other) -> Self:
        return self.value // other

    def __rfloordiv__(self, other) -> Self:
        return self // other

    def __mod__(self, other) -> Self:
        return self.value % other

    def __rmod__(self, other) -> Self:
        return self % other

    def __pow__(self, other) -> Self:
        return self.value ** other

    def __rpow__(self, other) -> Self:
        return self ** other

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderDynamics(ShaderModule, DynamicNumber):
    name: str  = "iShaderDynamics"
    real: bool = False

    def build(self):
        DynamicNumber.__attrs_post_init__(self)

    def setup(self):
        self.reset(instant=self.scene.freewheel)

    def update(self):
        # Note: |dt| as backwards in time the system is unstable
        dt = abs(self.scene.rdt if self.real else self.scene.dt)
        self.next(dt=dt)

    @property
    def type(self) -> Optional[str]:

        if isinstance(self.value, int):
            return "int"

        elif isinstance(self.value, float):
            return "float"

        shape = self.value.shape

        if len(shape) == 0:
            return "float"

        return {
            2: "vec2",
            3: "vec3",
            4: "vec4",
        }.get(shape[0], None)

    def pipeline(self) -> Iterable[ShaderVariable]:
        if not self.type:
            return
        yield Uniform(self.type, f"{self.name}", self.value)
        yield Uniform(self.type, f"{self.name}Integral", self.integral)
        yield Uniform(self.type, f"{self.name}Derivative", self.derivative)

