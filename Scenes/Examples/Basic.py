from ShaderFlow import *

# -------------------------------------------------------------------------------------------------|

class Empty(SombreroScene):
    """The most basic Sombrero Scene, the default shader"""
    ...

# -------------------------------------------------------------------------------------------------|

class Nested(SombreroScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "(Demo) Nested Shaders"

    def setup(self):

        # - Left screen is black, right screen is red
        # - Adds content of child shader to final image
        self.engine.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += draw_image(child, stuv).rgb;
            }
        """)

        self.child = self.engine.child(SombreroEngine)
        self.child.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
            }
        """)

        self.engine.new_texture("child").from_module(self.child)

    def pipeline(self) -> list[ShaderVariable]:
        return [
            ShaderVariable(qualifier="uniform", type="float", name=f"hahaha", value=2),
        ]

    def settings(self):
        ...

# -------------------------------------------------------------------------------------------------|

class Dynamics(SombreroScene):
    """Second order system demo"""
    __name__ = "(Demo) Dynamics"

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
                fragColor = draw_image(background, uv);
            }
        """)

        self.context.backend = SombreroBackend.GLFW

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.context.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class Noise(SombreroScene):
    """Basics of Simplex noise"""
    __name__ = "(Demo) Procedural Noise"

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
                fragColor = draw_image(background, uv);
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Bars(SombreroScene):
    """Basic music bars demo"""
    __name__ = "(Demo) Music Bars"

    def setup(self):

        # TODO: Port to SombreroAudio, better math
        self.audio = BrokenAudio()
        self.audio.open_device()
        self.audio.start_capture_thread()

        self.spectrogram = self.engine.add(SombreroSpectrogram(length=1, audio=self.audio))
        self.spectrogram.spectrogram.fft_n = 13
        self.spectrogram.spectrogram.make_spectrogram_matrix()
        # self.spectrogram.spectrogram.make_spectrogram_matrix_piano(
            # start=BrokenNote.from_frequency(20),
            # end=BrokenNote.from_frequency(18000),
        # )
        self.spectrogram.setup()

        self.engine.shader.fragment = ("""
            void main() {
                vec2 uv = astuv;

                // Round down to the iSpectrogramLength multiples
                // uv.x = floor(uv.x * iSpectrogramBins) / iSpectrogramBins;

                vec2 intensity = texture(iSpectrogram, vec2(0.0, uv.x)).xy;
                intensity /= iSpectrogramMaximum * 1.3;
                intensity = sqrt(intensity);
                // intensity *= pow(1.0 + uv.x, 1.6) * 0.6;

                if (uv.y < intensity.x) {
                    fragColor.rgb += vec3(1.0, 0.0, 0.0);
                }
                if (uv.y < intensity.y) {
                    fragColor.rgb += vec3(0.0, 1.0, 0.0);
                }

                if (uv.y < (intensity.y + intensity.x)/2.0) {
                    fragColor.rgb += vec3(0.0, 0.0, 1.0);
                }

                fragColor.rgb += vec3(0.0, 0.0, 0.4*(intensity.x + intensity.y)*(1.0 - uv.y));
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Spec(SombreroScene):
    """Basic spectrogram demo"""
    __name__ = "(Demo) Spectrogram"

    def setup(self):

        self.audio = BrokenAudio()
        self.audio.open_device()
        self.audio.start_capture_thread()

        self.spectrogram = self.engine.add(SombreroSpectrogram(audio=self.audio))
        self.spectrogram.setup()

        self.engine.shader.fragment = ("""
            void main() {
                vec2 uv = vec2(astuv.x + iSpectrogramOffset, astuv.y);
                uv = gluv2stuv(stuv2gluv(uv)*0.99);
                vec2 spec = sqrt(texture(iSpectrogram, uv).xy / iSpectrogramMaximum);
                fragColor.rgb = vec3(0.2) + vec3(spec.x, pow(spec.x + spec.y, 2), spec.y);
            }
        """)

# -------------------------------------------------------------------------------------------------|
