import math
from collections.abc import Iterable

import numpy as np
import shaderflow
from shaderflow.dynamics import ShaderDynamics
from shaderflow.scene import ShaderScene
from shaderflow.shader import ShaderProgram
from shaderflow.texture import ShaderTexture, TextureFilter
from shaderflow.variable import ShaderVariable, Uniform

# Note: We are lazy importing heavy modules for better import times

BACKGROUND = "https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg"

# ---------------------------------------------------------------------------- #

class Basic(ShaderScene):
    """The most basic ShaderScene, the default shader"""
    ...

# ---------------------------------------------------------------------------- #

class ShaderToy(ShaderScene):
    """ShaderToy Default Shader"""

    def build(self):
        self.shader.fragment = (self.directory/"shaders"/"shadertoy.frag")

# ---------------------------------------------------------------------------- #

class MultiShader(ShaderScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""

    def build(self):
        self.child = ShaderProgram(scene=self, name="child")

        # Left screen is green, right screen is black
        self.child.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
                fragColor.a = 1;
            }
        """)

        # - Left screen is black, right screen is red
        # - Adds content of child shader to final image
        self.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += texture(child, astuv).rgb;
                fragColor.a = 1;
            }
        """)

# ---------------------------------------------------------------------------- #

class Multipass(ShaderScene):
    """Many Layers ('Buffers') done on a single shader"""

    def build(self):
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.layers = 2
        self.shader.fragment = (self.directory/"shaders"/"multipass.frag")

# ---------------------------------------------------------------------------- #

class MotionBlur(ShaderScene):
    """Poor's man Motion Blur. If you dislike the effect, definitely don't run this"""

    def build(self):
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.temporal = 10
        self.shader.texture.layers = 2
        self.shader.fragment = (self.directory/"shaders"/"motionblur.frag")

# ---------------------------------------------------------------------------- #

class Dynamics(ShaderScene):
    """Second order system"""

    def build(self):
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.dynamics = ShaderDynamics(scene=self, name="iShaderDynamics", frequency=4)
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iShaderDynamics, vec2(0.5));
                fragColor = stexture(background, uv);
            }
        """)

    def update(self):
        # This is how square waves are born in the digital world
        self.dynamics.target = 0.5 * (1 + np.sign(np.sin(2*math.pi*self.time * 0.5)))

# ---------------------------------------------------------------------------- #

class Noise(ShaderScene):
    """Basics of Simplex noise"""

    def build(self):
        from shaderflow.noise import ShaderNoise
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shake_noise = ShaderNoise(scene=self, name="Shake", dimensions=2)
        self.zoom_noise  = ShaderNoise(scene=self, name="Zoom")
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.95 + 0.02*iZoom, vec2(0.5));
                uv += 0.02 * iShake;
                fragColor = stexture(background, uv);
            }
        """)

# ---------------------------------------------------------------------------- #

class Video(ShaderScene):
    """Video as a Texture demo"""

    def build(self):
        from broken.path import BrokenPath # noqa
        from shaderflow.video import ShaderVideo
        BUNNY = "https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_60fps_normal.mp4.zip"
        download = next(BrokenPath.get_external(BUNNY).rglob("*.mp4"))
        self.video = ShaderVideo(scene=self, path=download)
        self.shader.fragment = (self.directory/"shaders"/"video.frag")

# ---------------------------------------------------------------------------- #

class Audio(ShaderScene):
    """Basic audio processing"""

    def build(self):
        from shaderflow.audio import ShaderAudio
        self.audio = ShaderAudio(scene=self, name="iAudio")
        self.audio.open_recorder()
        self.shader.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
            }
        """)

# ---------------------------------------------------------------------------- #

class Waveform(ShaderScene):
    """Audio Waveform Oscilloscope demo"""

    def build(self):
        from shaderflow.audio import ShaderAudio
        from shaderflow.audio.waveform import ShaderWaveform
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.ogg")
        self.waveform = ShaderWaveform(scene=self, audio=self.audio, smooth=False)
        self.shader.fragment = (self.directory/"shaders"/"waveform.frag")

# ---------------------------------------------------------------------------- #

class MusicBars(ShaderScene):
    """Basic music bars"""

    def build(self):
        from shaderflow.audio import ShaderAudio
        from shaderflow.audio.spectrogram import ShaderSpectrogram
        from shaderflow.piano import PianoNote
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderSpectrogram(scene=self, audio=self.audio, length=0)
        self.spectrogram.from_notes(
            start=PianoNote.from_frequency(20),
            end=PianoNote.from_frequency(18000),
            piano=True
        )
        self.shader.fragment = (self.directory/"shaders"/"bars.frag")

# ---------------------------------------------------------------------------- #

class Visualizer(ShaderScene):
    """Radial Bars Music Visualizer Scene"""

    def build(self):
        from shaderflow.audio import ShaderAudio
        from shaderflow.audio.spectrogram import ShaderSpectrogram
        from shaderflow.audio.waveform import ShaderWaveform
        from shaderflow.piano import PianoNote
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.opus")
        self.waveform = ShaderWaveform(scene=self, audio=self.audio)
        self.spectrogram = ShaderSpectrogram(scene=self, length=0, audio=self.audio, smooth=False)
        self.spectrogram.from_notes(
            start=PianoNote.from_frequency(20),
            end=PianoNote.from_frequency(14000),
            piano=True
        )
        ShaderTexture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/ex/wallhaven-ex6kmr.jpg")
        ShaderTexture(scene=self, name="logo").from_image(shaderflow.resources/"images"/"logo.png")
        self.shader.fragment = (self.directory/"shaders"/"visualizer.frag")

# ---------------------------------------------------------------------------- #

class RayMarch(ShaderScene):
    """Ray Marching demo"""

    def build(self):
        self.shader.fragment = (self.directory/"shaders"/"raymarch.frag")

# ---------------------------------------------------------------------------- #

class Life(ShaderScene):
    """Conway's Game of Life in GLSL"""

    life_period: int = 6
    """Number of frames between each life update"""

    def setup(self):
        width, height = 192, 108
        random = np.random.randint(0, 2, (width, height), dtype=bool)
        self.simulation.texture.size = (width, height)
        self.simulation.texture.write(random.astype(np.float32), temporal=1)

    def build(self):
        self.simulation = ShaderProgram(scene=self, name="iLife")
        self.simulation.texture.temporal = 10
        self.simulation.texture.filter = TextureFilter.Nearest
        self.simulation.texture.dtype = "f4"
        self.simulation.texture.components = 1
        self.simulation.texture.track = False
        self.simulation.fragment = (self.directory/"shaders/life/simulation.glsl")
        self.shader.fragment = (self.directory/"shaders/life/visuals.glsl")

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield from ShaderScene.pipeline(self)
        yield Uniform("int", "iLifePeriod", self.life_period)

# ---------------------------------------------------------------------------- #
