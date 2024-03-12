from ShaderFlow import *

GLSL = SHADERFLOW.RESOURCES.EXAMPLE_SCENES/"GLSL"

# -------------------------------------------------------------------------------------------------|

class Default(Scene):
    """The most basic ShaderFlow Scene, the default shader"""
    ...

# -------------------------------------------------------------------------------------------------|

class Nested(Scene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "Nested Shaders"

    def build(self):
        Scene.build(self)
        self.child = Shader(scene=self, name="child")

        # - Left screen is black, right screen is red
        # - Adds content of child shader to final image
        self.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += texture(child, astuv).rgb;
                fragColor.a = 1;
            }
        """)

        # Left screen is green, right screen is black
        self.child.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
                fragColor.a = 1;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Multipass(Scene):
    """Second order system"""
    __name__ = "Multipass"

    def build(self):
        Scene.build(self)
        Texture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")
        self.shader.texture.layers = 2
        self.shader.fragment = ("""
            void main() {
                if (iLayer == 0) {
                    fragColor = draw_image(background, stuv);
                } else if (iLayer == 1) {
                    fragColor = texture(iScreen1, astuv);
                }
                fragColor.a = 1;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Dynamics(Scene):
    """Second order system"""
    __name__ = "Dynamics"

    def build(self):
        Scene.build(self)
        Texture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")
        self.dynamics = Dynamics(scene=self, name="iDynamics", frequency=4)
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iDynamics, vec2(0.5));
                fragColor = draw_image(background, uv);
                fragColor.a = 1;
            }
        """)

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class Noise(Scene):
    """Basics of Simplex noise"""
    __name__ = "Procedural Noise"

    def build(self):
        Scene.build(self)
        Texture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")
        self.shake_noise = ShaderFlowNoise(scene=self, name="Shake", dimensions=2)
        self.zoom_noise  = ShaderFlowNoise(scene=self, name="Zoom")
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.95 + 0.02*iZoom, vec2(0.5));
                uv += 0.02 * iShake;
                fragColor = draw_image(background, uv);
            }
        """)

# -------------------------------------------------------------------------------------------------|

# Todo: Waveform Module
class Audio(Scene):
    """Basic audio processing"""
    __name__ = "Audio"

    def build(self):
        Scene.build(self)
        self.audio = ShaderFlowAudio(scene=self, name="Audio")
        self.shader.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Bars(Scene):
    """Basic music bars"""
    __name__ = "Music Bars"

    def build(self):
        Scene.build(self)
        self.audio = ShaderFlowAudio(scene=self, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderFlowSpectrogram(scene=self, audio=self.audio, length=1)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(18000),
            piano=True
        )
        self.shader.fragment = GLSL/"Bars.frag"

# -------------------------------------------------------------------------------------------------|

class Visualizer(Scene):
    """Proof of concept of a Music Visualizer Scene"""
    __name__ = "Visualizer MVP"

    def build(self):
        Scene.build(self)
        self.audio = ShaderFlowAudio(scene=self, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderFlowSpectrogram(scene=self, length=1, audio=self.audio, smooth=False)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
            piano=True
        )
        Texture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/rr/wallhaven-rrjvyq.png")
        Texture(scene=self, name="logo").from_image(SHADERFLOW.RESOURCES.ICON)
        ShaderFlowNoise(scene=self, name="Shake", dimensions=2)
        ShaderFlowNoise(scene=self, name="Zoom")
        self.shader.fragment = GLSL/"Visualizer.frag"

# -------------------------------------------------------------------------------------------------|
