from ShaderFlow import *

# Warn: To be considered a Scene file, the substrings `ShaderFlow` and `SombreroScene` must be
# Warn: present on the file contents. This is a optimization to avoid scanning non-scene files.

GLSL = SHADERFLOW.RESOURCES.EXAMPLE_SCENES/"GLSL"

# -------------------------------------------------------------------------------------------------|

class Default(SombreroScene):
    """The most basic Sombrero Scene, the default shader"""
    ...

# -------------------------------------------------------------------------------------------------|

class Nested(SombreroScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "Nested Shaders Demo"

    def build(self):

        # - Left screen is black, right screen is red
        # - Adds content of child shader to final image
        self.engine.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += draw_image(child, stuv).rgb;
                fragColor.a = 1;
            }
        """)

        # Left screen is green, right screen is black
        self.child = self.engine.child(SombreroEngine)
        self.child.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
                fragColor.a = 1;
            }
        """)

        self.engine.new_texture("child").from_module(self.child)

# -------------------------------------------------------------------------------------------------|

class Dynamics(SombreroScene):
    """Second order system demo"""
    __name__ = "Dynamics Demo"

    def build(self):
        self.add(SombreroTexture(name="background")).from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")
        self.dynamics = self.add(SombreroDynamics(name="iDynamics", frequency=4))
        self.engine.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iDynamics, vec2(0.5));
                fragColor = draw_image(background, uv);
            }
        """)

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class Noise(SombreroScene):
    """Basics of Simplex noise"""
    __name__ = "Procedural Noise Demo"

    def build(self):
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")

        # Create noise module
        self.shake_noise = self.add(SombreroNoise(name="Shake", dimensions=2))
        self.zoom_noise  = self.add(SombreroNoise(name="Zoom"))

        # Load custom shader
        self.engine.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.95 + 0.02*iZoom, vec2(0.5));
                uv += 0.02 * iShake;
                fragColor = draw_image(background, uv);
            }
        """)

# -------------------------------------------------------------------------------------------------|

# Todo: Waveform Module
class Audio(SombreroScene):
    """Basic audio processing"""
    __name__ = "Audio Demo"

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio")
        self.engine.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
                fragColor.r = astuv.x;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Bars(SombreroScene):
    """Basic music bars demo"""
    __name__ = "Music Bars Demo"

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = self.add(SombreroSpectrogram, audio=self.audio, length=1)
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(10),
            end=BrokenPianoNote.from_frequency(18000),
        )
        self.engine.fragment = GLSL/"Bars.frag"

# -------------------------------------------------------------------------------------------------|

class Spectrogram(SombreroScene):
    """Basic spectrogram demo"""
    __name__ = "Spectrogram Demo"

    def build(self):
        self.audio = self.add(SombreroAudio(name="Audio", file="/path/to/audio.ogg"))
        self.spectrogram = self.add(SombreroSpectrogram(audio=self.audio))
        self.spectrogram.dynamics.frequency = 20
        self.engine.fragment = GLSL/"Spectrogram.frag"

# -------------------------------------------------------------------------------------------------|

class PianoRoll(SombreroScene):
    """Basic piano roll demo"""
    __name__ = "Piano Roll Demo"

    def build(self):
        self.audio = self.add(SombreroAudio(name="Audio", file="/path/to/audio.ogg"))
        self.piano = self.add(SombreroPianoRoll)
        self.piano.add_midi(SHADERFLOW.RESOURCES/"Midis"/"Hopeless Sparkle.mid")
        self.piano.normalize_velocities()
        self.engine.fragment = GLSL/"PianoRoll.frag"

# -------------------------------------------------------------------------------------------------|

class Visualizer(SombreroScene):
    """Proof of concept of a Music Visualizer Scene"""
    __name__ = "Visualizer MVP"

    # Note: This cody is messy, used as a way to see where things go wrong and be improved

    def build(self):
        self.audio = self.add(SombreroAudio(name="Audio", file="/path/to/audio.ogg"))
        self.spectrogram = self.add(SombreroSpectrogram(length=1, audio=self.audio, smooth=False))
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
        )
        self.add(SombreroTexture(name="background")).from_image("https://w.wallhaven.cc/full/rr/wallhaven-rrjvyq.png")
        self.add(SombreroTexture(name="logo")).from_image(SHADERFLOW.RESOURCES.ICON)
        self.add(SombreroNoise(name="Shake", dimensions=2))
        self.add(SombreroNoise(name="Zoom"))
        self.engine.fragment = GLSL/"Visualizer.frag"

# -------------------------------------------------------------------------------------------------|
