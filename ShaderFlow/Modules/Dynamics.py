from __future__ import annotations

from . import *


@define(slots=False)
class DynamicNumber(Number):
    """
    Simulate on time domain a progressive second order system
    # Fixme: Move to Broken when ought to be used somewhere else

    # Sources:
    - https://www.youtube.com/watch?v=KPoeNZZ6H4s <- Math mostly took from here, thanks @t3ssel8r
    - https://en.wikipedia.org/wiki/Semi-implicit_Euler_method
    - Control System classes on my university which I got 6/10 final grade

    # Explanation

    A second order system is defined by the following equation:
    $$ y + k1*y' + k2*y'' = x + k3*x' $$

    This can be rewritten based on "intuitive" parameters:
    $$ f = 1/(2*pi*sqrt(k2)) $$
    $$ z = k1/(2*sqrt(k2)) $$
    $$ r = 2*k3/k1 $$

    Where the meaning of each term is:

    - f: Natural frequency of the system in Hertz, "the speed the system responds to a change in input"
    Also is the frequency the system tends to vibrate at, doesn't affect shape of the resulting motion

    - z: Damping coefficient, z=0 vibration never dies, z=1 is the critical limit where the system
    does not overshoot, z>1 increases this effect and the system takes longer to settle

    - r: Defines the initial response "time" of the system, when r=1 the system responds instantly
    to changes on the input, when r=0 the system takes a bit to respond (smoothstep like), when r<0
    the system "anticipates" motion

    These terms are rearranged into some smart math I don't understand using semi-implicit Euler method

    Hence why, most of this code is a Python-port of the code saw in the video, with many
    modifications and different implementation - a class that acts like a number normally
    """

    def __convert__(self, value):
        if isinstance(value, int):
            value = float(value)
        return numpy.array(value, dtype=getattr(value, "dtype", self.dtype))

    def __set_target__(self, attribute, value):
        target = self.__convert__(value)
        if (target.shape != self.value.shape):
            self.value = target
        return target

    value:  Union[numpy.dtype, numpy.ndarray] = Field(default=0)
    target: Union[numpy.dtype, numpy.ndarray] = Field(default=None, on_setattr=__set_target__)
    dtype:  numpy.dtype                       = Field(default=numpy.float32)

    def __attrs_post_init__(self):
        self.value  = self.__convert__(self.value)
        self.target = self.__convert__(self.target if (self.target is not None) else self.value)

    # # Dynamics

    # System parameters
    frequency: float = 1.0
    zeta:      float = 1.0
    response:  float = 0.0
    precision: float = 1e-6

    # Free lunches
    integral:     float = 0.0
    derivative:   float = 0.0
    acceleration: float = 0.0

    @property
    def k1(self) -> float:
        """Y velocity coefficient"""
        return self.zeta/(PI * self.frequency)

    @property
    def k2(self) -> float:
        """Y acceleration coefficient"""
        return 1/(self.radians*self.radians)

    @property
    def k3(self) -> float:
        """X velocity coefficient"""
        return (self.response * self.zeta) / (TAU * self.frequency)

    @property
    def radians(self) -> float:
        """Natural resonance frequency in radians per second"""
        return TAU * self.frequency

    @property
    def damping(self) -> float:
        """Damping ratio of some sort"""
        return self.radians * (abs(self.zeta*self.zeta - 1.0))**0.5

    previous: float = 0

    def next(self, target: Number=None, dt: float=1.0) -> Number:
        """
        Update the system to the next time step, optionally with a new target value
        # Fixme: There is a HUGE potential for speed gains if we don't create many temporary ndarray

        Args:
            `target`: Next target value to reach, None for previous
            `dt`:     Time delta since last update

        Returns:
            The system's self.value
        """
        if not dt:
            return self.value

        # Update target
        if (target is not None):
            self.target = target

        # Optimization: Do not compute if value within precision to target
        if abs(numpy.sum(self.target - self.value)) < self.precision:
            return self.value

        # "Estimate velocity"
        velocity      = (self.target - self.previous)/dt
        self.previous = self.target

        # "Clamp k2 to stable values without jitter"
        if (self.radians*dt < self.zeta):
            k1 = self.k1
            k2 = max(self.k2, 0.5*(self.k1+dt)*dt, self.k1*dt)

        # "Use pole matching when the system is very fast"
        else:
            t1 = numpy.exp(-1 * self.zeta * self.radians * dt)
            a1 = 2 * t1 * (numpy.cos if self.zeta <= 1 else numpy.cosh)(self.damping*dt)
            t2 = 1/(1 + t1*t1 - a1) * dt
            k1 = t2 * (1 - t1*t1)
            k2 = t2 * dt

        # Integrate values
        self.value       += (self.derivative * dt)
        self.acceleration = (self.target + self.k3*velocity - self.value - k1*self.derivative)/k2
        self.derivative  += (self.acceleration * dt)
        self.integral    += (self.value * dt)
        return self.value

    def __call__(self, target: Number=None, dt: float=1.0) -> Number:
        """Wraps around self.next"""
        return self.next(target, dt=dt)

    @staticmethod
    def extract(*objects: Union[Number, DynamicNumber]) -> Tuple[Number]:
        """Extract the values from DynamicNumbers objects or return the same object"""
        return tuple(obj.value if isinstance(obj, DynamicNumber) else obj for obj in objects)

    # # Number implementation

    def __str__(self) -> str:
        return str(self.value)

    def __float__(self) -> float:
        return self.value

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

# -------------------------------------------------------------------------------------------------|

@define
class ShaderFlowDynamics(ShaderFlowModule, DynamicNumber):
    name: str  = Field(default="Dynamics")
    real: bool = False

    def update(self):
        # Note: |dt| as rewinding time the system is unstable
        dt = abs(self.scene.rdt if self.real else self.scene.dt)
        self.next(dt=dt)

    @property
    def type(self) -> Optional[str]:

        # Guess type based on shape
        match self.value.shape:
            case ():
                return "float"
            case (2,):
                return "vec2"
            case (3,):
                return "vec3"
            case (4,):
                return "vec4"

    def pipeline(self) -> Iterable[ShaderVariable]:
        if not self.type:
            return
        yield ShaderVariable("uniform", self.type, f"{self.name}", self.value)
        yield ShaderVariable("uniform", self.type, f"{self.name}Integral", self.integral)
        yield ShaderVariable("uniform", self.type, f"{self.name}Derivative", self.derivative)

