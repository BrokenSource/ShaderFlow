import opensimplex

from . import *


@define
class SombreroNoise(SombreroModule):
    name: str = "Noise"
    seed: int = Factory(functools.partial(random.randint, 0, 10000))

    # TODO: Convert these to BrokenSecondOrderDynamics?

    # Maximum amplitude (roughly)
    amplitude: float = 1

    # Frequency of the first octave
    frequency: float = 1

    # How many octaves of noise to sum
    octaves:   int   = 1

    # How much to divide the amplitude of each octave
    roughness: float = 1

    # # Number of dimensions for this noise

    __dimensions__: int = 1

    @property
    def dimensions(self):
        return self.__dimensions__

    @dimensions.setter
    def dimensions(self, value):
        self.__dimensions__ = value
        self.__simplex__ = [
            opensimplex.OpenSimplex(seed=self.seed + dimension*1000)
            for dimension in range(self.dimensions)
        ]

    @property
    def dimension_variable_type(self) -> str:
        return {
            1: "float",
            2: "vec2",
            3: "vec3",
        }[self.dimensions]

    # Noise generator
    __simplex__: opensimplex.OpenSimplex = None

    def __init__(self, dimensions: int=1, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)
        self.dimensions = dimensions

    def at(self, x: float=0, y: float=0, z: float=0) -> float:
        """Internal function to return a noise value for three dimensions"""
        noise = numpy.zeros(self.dimensions, dtype=numpy.float32)

        for dimension in range(self.dimensions):
            for octave in range(self.octaves):

                # The "position velocity" due frequency of this octave
                # · One octave up, double the frequency
                # · Scale linearly with self.frequency
                k = (2**octave) * self.frequency

                # Amplitude of this octave so noise remains bounded
                # · Double the octave, half the amplitude
                amplitude = self.amplitude * (self.roughness)**octave

                # Sum this octave's noise to the total
                # Fixme: x=0, y=0, z=0 yields the same noise for all octaves
                noise[dimension] += self.__simplex__[dimension].noise3(x*k, y*k, z*k) * amplitude

        return noise

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield ShaderVariable(
            qualifier="uniform",
            type=self.dimension_variable_type,
            name=f"{self.prefix}{self.name}",
            value=self.at(self.scene.time)
        )
