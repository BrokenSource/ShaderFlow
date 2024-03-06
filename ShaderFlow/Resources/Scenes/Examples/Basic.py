from ShaderFlow import *

# Warn: To be considered a Scene file, the substring `ShaderFlowScene` must be present on the file.

GLSL = SHADERFLOW.RESOURCES.EXAMPLE_SCENES/"GLSL"

# -------------------------------------------------------------------------------------------------|

class Default(ShaderFlowScene):
    """The most basic ShaderFlow Scene, the default shader"""
    ...

# -------------------------------------------------------------------------------------------------|

class Nested(ShaderFlowScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "Nested Shaders"

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
        self.child = self.engine.child(ShaderFlowEngine)
        self.child.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
                fragColor.a = 1;
            }
        """)

        self.engine.new_texture("child").from_module(self.child)

# -------------------------------------------------------------------------------------------------|

class Dynamics(ShaderFlowScene):
    """Second order system"""
    __name__ = "Dynamics"

    def build(self):
        self.add(ShaderFlowTexture(name="background")).from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")
        self.dynamics = self.add(ShaderFlowDynamics(name="iDynamics", frequency=4))
        self.engine.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iDynamics, vec2(0.5));
                fragColor = draw_image(background, uv);
            }
        """)

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class Noise(ShaderFlowScene):
    """Basics of Simplex noise"""
    __name__ = "Procedural Noise"

    def build(self):
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")

        # Create noise module
        self.shake_noise = self.add(ShaderFlowNoise(name="Shake", dimensions=2))
        self.zoom_noise  = self.add(ShaderFlowNoise(name="Zoom"))

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
class Audio(ShaderFlowScene):
    """Basic audio processing"""
    __name__ = "Audio"

    def build(self):
        self.audio = self.add(ShaderFlowAudio, name="Audio")
        self.engine.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
                fragColor.r = astuv.x;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Bars(ShaderFlowScene):
    """Basic music bars"""
    __name__ = "Music Bars"

    def build(self):
        self.audio = self.add(ShaderFlowAudio, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = self.add(ShaderFlowSpectrogram, audio=self.audio, length=1)
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(10),
            end=BrokenPianoNote.from_frequency(18000),
        )
        self.engine.fragment = GLSL/"Bars.frag"

# -------------------------------------------------------------------------------------------------|

class Visualizer(ShaderFlowScene):
    """Proof of concept of a Music Visualizer Scene"""
    __name__ = "Visualizer MVP"

    # Note: This cody is messy, used as a way to see where things go wrong and be improved

    def build(self):
        self.audio = self.add(ShaderFlowAudio(name="Audio", file="/path/to/audio.ogg"))
        self.spectrogram = self.add(ShaderFlowSpectrogram(length=1, audio=self.audio, smooth=False))
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
        )
        self.add(ShaderFlowTexture(name="background")).from_image("https://w.wallhaven.cc/full/rr/wallhaven-rrjvyq.png")
        self.add(ShaderFlowTexture(name="logo")).from_image(SHADERFLOW.RESOURCES.ICON)
        self.add(ShaderFlowNoise(name="Shake", dimensions=2))
        self.add(ShaderFlowNoise(name="Zoom"))
        self.engine.fragment = GLSL/"Visualizer.frag"

# -------------------------------------------------------------------------------------------------|
