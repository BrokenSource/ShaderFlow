from __future__ import annotations

import rich.pretty
from ShaderFlow import *

# -------------------------------------------------------------------------------------------------|

class EmptySceneDemo(SombreroScene):
    """The most basic Sombrero Scene, the default shader"""
    NAME = "Empty Scene Demo"
    ...

# -------------------------------------------------------------------------------------------------|

class NestedSceneDemo(SombreroScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    NAME = "Nested Shaders Demo"

    def setup(self):

        # - Left screen is black, right screen is red
        # - Adds content of child shader to final image
        self.engine.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += texture(child, stuv).rgb;
            }
        """)

        self.child = self.engine.child(SombreroEngine)
        self.child.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
            }
        """)

        self.engine.new_texture("child").from_engine(self.child)

# -------------------------------------------------------------------------------------------------|

class DynamicsSceneDemo(SombreroScene):
    """Second order system demo"""
    NAME = "Dynamics Scene Demo"

    def setup(self):

        # Create background texture
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")

        # Create dynamics module
        self.dynamics = self.engine.add(SombreroDynamics(frequency=4))

        # Camera shake noise
        self.engine.add(SombreroNoise(name="NoiseShake", dimensions=2))
        self.engine.add(SombreroNoise(name="NoiseZoom"))

        # Load custom shader
        self.engine.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iDynamics, vec2(0.5));
                fragColor = texture(background, uv);
            }
        """)

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.context.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class NoiseSceneDemo(SombreroScene):
    """Basics of Simplex noise"""
    NAME = "Noise Scene Demo"

    def setup(self):
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")

        # Create noise module
        self.shake_noise = self.engine.add(SombreroNoise(name="Shake", dimensions=2))
        self.zoom_noise  = self.engine.add(SombreroNoise(name="Zoom"))

        # Load custom shader
        self.engine.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.95 + 0.02*iZoom, vec2(0.5));
                uv += 0.02 * iShake;
                fragColor = texture(background, uv);
            }
        """)

        rich.print(self)

# -------------------------------------------------------------------------------------------------|

def main():
    scene = NoiseSceneDemo()
    scene.run()

if __name__ == "__main__":
    main()
