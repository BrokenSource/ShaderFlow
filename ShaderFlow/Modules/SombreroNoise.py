from . import *


@attrs.define
class SombreroNoise:
    seed: int = attrs.field(factory=functools.partial(random.randint, 0, 10000))

    # TODO: Convert these to BrokenSecondOrderDynamics
    frequency: float = 1
    roughness: float = 1
    octaves: int = 1

    # Noise generator
    simplex: opensimplex.OpenSimplex = None

    def __attrs_post_init__(self):
        self.simplex = opensimplex.OpenSimplex(seed=self.seed)

    def __noise__(self, x: float, y: float, z: float) -> float:
        """Internal function to return a noise value for three dimensions"""
        noise = 0

        for octave in range(self.octaves):
            # The "position velocity" due frequency of this octave
            # · One octave up, double the frequency
            # · Scale linearly with self.frequency
            k = (2**octave) * self.frequency

            # Amplitude of this octave so noise remains bounded
            # · Double the octave, half the amplitude
            # · Apply roughness by changing *that* half-much
            amplitude = (2/self.roughness)**octave

            # Sum this octave's noise to the total
            # Fixme: x=0, y=0, z=0 yields the same noise for all octaves
            noise += self.simplex.noise3(x*k, y*k, z*k) / amplitude

        return noise

    def one(self, x: float) -> float:
        """Get a noise value for one input"""
        return self.__noise__(x, 0, 0)

    def two(self, x: float, y: float) -> float:
        """Get a noise value for two inputs"""
        return self.__noise__(x, y, 0)

    def three(self, x: float, y: float, z: float) -> float:
        """Get a noise value for three inputs"""
        return self.__noise__(x, y, z)
