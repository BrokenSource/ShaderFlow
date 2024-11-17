from __future__ import annotations

import math
from ast import Tuple
from copy import deepcopy
from math import pi, tau
from numbers import Number
from typing import Iterable, Optional, Self, TypeAlias, Union

import numpy
from attr import define, field

from ShaderFlow.Module import ShaderModule
from ShaderFlow.Variable import ShaderVariable, Uniform

# Fixme: Move to Broken when ought to be used somewhere else?

DynType: TypeAlias = numpy.ndarray
INSTANT_FREQUENCY = 1e6

# ------------------------------------------------------------------------------------------------ #

class NumberDunder(Number):
    """Boring dunder methods for number-like objects"""

    def __float__(self) -> float:
        return float(self.value)
    def __int__(self) -> int:
        return int(self.value)
    def __str__(self) -> str:
        return str(self.value)

    # Multiplication
    def __mul__(self, other) -> DynType:
        return self.value * other
    def __rmul__(self, other) -> DynType:
        return self * other

    # Addition
    def __add__(self, other) -> DynType:
        return self.value + other
    def __radd__(self, other) -> DynType:
        return self + other

    # Subtraction
    def __sub__(self, other) -> DynType:
        return self.value - other
    def __rsub__(self, other) -> DynType:
        return self - other

    # Division
    def __truediv__(self, other) -> DynType:
        return self.value / other
    def __rtruediv__(self, other) -> DynType:
        return self / other

    # Floor division
    def __floordiv__(self, other) -> DynType:
        return self.value // other
    def __rfloordiv__(self, other) -> DynType:
        return self // other

    # Modulus
    def __mod__(self, other) -> DynType:
        return self.value % other
    def __rmod__(self, other) -> DynType:
        return self % other

    # Power
    def __pow__(self, other) -> DynType:
        return self.value ** other
    def __rpow__(self, other) -> DynType:
        return self ** other

# ------------------------------------------------------------------------------------------------ #

@define(slots=False)
class DynamicNumber(NumberDunder, Number):
    """
    Simulate on time domain a progressive second order system

    # Sources:
    - Control System classes on my university which I got 6/10 final grade but survived
    - https://www.youtube.com/watch?v=KPoeNZZ6H4s <- Math mostly took from here, thanks @t3ssel8r
    - https://en.wikipedia.org/wiki/Semi-implicit_Euler_method

    This is a Python-port of the video's math, with custom implementation and extras
    """

    # # Base system values

    def _ensure_numpy(self, value) -> numpy.ndarray:
        if isinstance(value, numpy.ndarray):
            return value
        return numpy.array(value, dtype=getattr(value, "dtype", self.dtype))

    def _ensure_numpy_setattr(self, attribute, value) -> numpy.ndarray:
        return self._ensure_numpy(value)

    value: DynType = field(default=0, on_setattr=_ensure_numpy_setattr)
    """The current value of the system. Prefer explicitly using it over the object itself"""

    target: DynType = field(default=0, on_setattr=_ensure_numpy_setattr)
    """The target value the system is trying to reach, modeled by the parameters"""

    dtype: numpy.dtype = field(default=numpy.float64)
    """Data type of the NumPy vectorized data"""

    initial: DynType = field(default=None)
    """Initial value of the system, defaults to first value set"""

    def __attrs_post_init__(self):
        self.set(self.target or self.value)

    def set(self, value: DynType, *, instant: bool=True) -> None:
        value = self._ensure_numpy(value)
        self.value = deepcopy(value) if (instant) else self.value
        self.target = deepcopy(value)
        self.initial = deepcopy(value)
        self.previous = deepcopy(value) if (instant) else self.previous

        zeros = numpy.zeros_like(value)
        self.integral = deepcopy(zeros)
        self.derivative = deepcopy(zeros)
        self.acceleration = deepcopy(zeros)

    def reset(self, instant: bool=False):
        self.set(self.initial, instant=instant)

    # # Dynamics system parameters

    frequency: float = 1.0
    """Natural frequency of the system in Hertz, "the speed the system responds to a change in input".
    Also, the frequency it tends to vibrate at, doesn't affect shape of the resulting motion"""

    zeta: float = 1.0
    """Damping coefficient, z=0 vibration never dies, z=1 is the critical limit where the system
    does not overshoot, z>1 increases this effect and the system takes longer to settle"""

    response: float = 0.0
    """Defines the initial response "time" of the system, when r=1 the system responds instantly
    to changes on the input, when r=0 the system takes a bit to respond (smoothstep like), when r<0
    the system "anticipates" motion"""

    precision: float = 1e-6
    """If `max(target - value) < precision`, the system stops updating to save computation"""

    # # Auxiliary intrinsic variables

    integral: DynType = 0.0
    """Integral of the system, the sum of all values over time"""

    derivative: DynType = 0.0
    """Derivative of the system, the rate of change of the value in ($unit/second)"""

    acceleration: DynType = 0.0
    """Acceleration of the system, the rate of change of the derivative in ($unit/second^2)"""

    previous: DynType = 0.0
    """Previous target value"""

    @property
    def instant(self) -> bool:
        """Update the system immediately to the target value"""
        return (self.frequency >= INSTANT_FREQUENCY)

    @property
    def k1(self) -> float:
        """Y velocity coefficient"""
        return self.zeta / (pi * self.frequency)

    @property
    def k2(self) -> float:
        """Y acceleration coefficient"""
        return 1.0 / (self.radians*self.radians)

    @property
    def k3(self) -> float:
        """X velocity coefficient"""
        return (self.response * self.zeta) / (tau * self.frequency)

    @property
    def radians(self) -> float:
        """Natural resonance frequency in radians per second"""
        return (tau * self.frequency)

    @property
    def damping(self) -> float:
        """Damping ratio of some sort"""
        return self.radians * (abs(self.zeta*self.zeta - 1.0))**0.5

    def next(self, target: Optional[DynType]=None, dt: float=1.0) -> DynType:
        """
        Update the system to the next time step, optionally with a new target value
        # Fixme: There is a HUGE potential for speed gains if we don't create many temporary ndarray

        Args:
            target: Next target value to reach, None for previous
            dt:     Time delta since last update

        Returns:
            The system's self.value
        """
        if (not dt):
            return self.value

        # Update target and recreate if necessary
        if (target is not None):
            self.target = self._ensure_numpy(target)

            if (self.target.shape != self.value.shape):
                self.set(target)

        # Todo: instant mode

        # Optimization: Do not compute if within precision to target
        if (numpy.abs(self.target - self.value).max() < self.precision):
            self.integral += (self.value * dt)
            return self.value

        # "Estimate velocity"
        velocity = (self.target - self.previous)/dt
        self.previous = self.target

        # "Clamp k2 to stable values without jitter"
        if (self.radians*dt < self.zeta):
            k1 = self.k1
            k2 = max(k1*dt, self.k2, 0.5*(k1+dt)*dt)

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

    @staticmethod
    def extract(*objects: Union[Number, Self]) -> Tuple[Number]:
        """Extract the values from DynamicNumbers objects or return the same object"""
        return tuple(obj.value if isinstance(obj, DynamicNumber) else obj for obj in objects)

# ------------------------------------------------------------------------------------------------ #

@define
class ShaderDynamics(ShaderModule, DynamicNumber):
    name: str  = "iShaderDynamics"
    real: bool = False

    def build(self) -> None:
        DynamicNumber.__attrs_post_init__(self)

    def setup(self) -> None:
        self.reset(instant=self.scene.freewheel)

    def update(self) -> None:
        # Note: abs(dt) the system is unstable backwards in time (duh)
        self.next(dt=abs(self.scene.rdt if self.real else self.scene.dt))

    @property
    def type(self) -> Optional[str]:
        if not (shape := self.value.shape):
            return "float"
        elif (shape[0] == 1):
            return "float"
        elif (shape[0] == 2):
            return "vec2"
        elif (shape[0] == 3):
            return "vec3"
        elif (shape[0] == 4):
            return "vec4"
        return None

    def pipeline(self) -> Iterable[ShaderVariable]:
        if (not self.type):
            return
        yield Uniform(self.type, f"{self.name}", self.value)
        yield Uniform(self.type, f"{self.name}Integral", self.integral)
        yield Uniform(self.type, f"{self.name}Derivative", self.derivative)

