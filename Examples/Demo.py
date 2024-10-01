import math
from pathlib import Path
from typing import Iterable

import numpy
from ShaderFlow import SHADERFLOW
from ShaderFlow.Common.Notes import BrokenPianoNote
from ShaderFlow.Modules.Dynamics import ShaderDynamics
from ShaderFlow.Modules.Noise import ShaderNoise
from ShaderFlow.Scene import ShaderScene
from ShaderFlow.Shader import ShaderObject
from ShaderFlow.Texture import ShaderTexture, TextureFilter
from ShaderFlow.Variable import ShaderVariable, Uniform

from Broken import BrokenPath

BACKGROUND = "https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg"

# Note: We are lazy importing heavy modules for better import times

# ------------------------------------------------------------------------------------------------ #

class Basic(ShaderScene):
    """The most basic ShaderScene, the default shader"""
    ...

# ------------------------------------------------------------------------------------------------ #

class ShaderToy(ShaderScene):
    """ShaderToy Default Shader"""

    def build(self):
        self.shader.fragment = (self.directory/"GLSL"/"ShaderToy.frag")

# ------------------------------------------------------------------------------------------------ #

class Nested(ShaderScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "Nested Shaders"

    def build(self):
        self.child = ShaderObject(scene=self, name="child")

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

# ------------------------------------------------------------------------------------------------ #

class Multipass(ShaderScene):
    """Many Layers ('Buffers') done on a single shader"""
    __name__ = "Multipass"

    def build(self):
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.layers = 2
        self.shader.fragment = (self.directory/"GLSL"/"Multipass.frag")

# ------------------------------------------------------------------------------------------------ #

class MotionBlur(ShaderScene):
    """Poor's man Motion Blur. If you dislike the effect, definitely don't run this"""
    __name__ = "MotionBlur"

    def build(self):
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.temporal = 10
        self.shader.texture.layers = 2
        self.shader.fragment = (self.directory/"GLSL"/"MotionBlur.frag")

# ------------------------------------------------------------------------------------------------ #

class Dynamics(ShaderScene):
    """Second order system"""
    __name__ = "Dynamics"

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
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.time * 0.5)))

# ------------------------------------------------------------------------------------------------ #

class Noise(ShaderScene):
    """Basics of Simplex noise"""
    __name__ = "Procedural Noise"

    def build(self):
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

# ------------------------------------------------------------------------------------------------ #

class Bouncing(ShaderScene):
    """Bouncing Logo animation"""
    __name__ = "Bouncing Logo"

    def build(self):
        from ShaderFlow.Modules.Others.Bouncing import ShaderBouncing
        LOGO = SHADERFLOW.RESOURCES.ICON_PNG
        self.dvd = ShaderTexture(scene=self, name="logo").from_image(LOGO)
        self.shader.fragment = (self.directory/"GLSL"/"Bouncing.frag")
        self.bounce = ShaderBouncing(scene=self)
        self.bounce.advanced_ratios(LOGO)

    def update(self):
        self.bounce.aspect_ratio = self.aspect_ratio

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield from ShaderScene.pipeline(self)
        yield Uniform("float", "iLogoSize", 0.3)

# ------------------------------------------------------------------------------------------------ #

class Video(ShaderScene):
    """Video as a Texture demo"""
    __name__ = "Video"

    def build(self):
        from ShaderFlow.Modules.Video import ShaderVideo
        BUNNY = "https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_60fps_normal.mp4.zip"
        download = next(BrokenPath.get_external(BUNNY).rglob("*.mp4"))
        self.video = ShaderVideo(scene=self, path=download)
        self.shader.fragment = (self.directory/"GLSL"/"Video.frag")

# ------------------------------------------------------------------------------------------------ #

class Audio(ShaderScene):
    """Basic audio processing"""
    __name__ = "Audio"

    def build(self):
        from ShaderFlow.Modules.Audio import ShaderAudio
        self.audio = ShaderAudio(scene=self, name="iAudio")
        self.audio.open_recorder()
        self.shader.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
            }
        """)

# ------------------------------------------------------------------------------------------------ #

class Waveform(ShaderScene):
    """Audio Waveform Oscilloscope demo"""
    __name__ = "Waveform"

    def build(self):
        from ShaderFlow.Modules.Audio import ShaderAudio
        from ShaderFlow.Modules.Waveform import ShaderWaveform
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.ogg")
        self.waveform = ShaderWaveform(scene=self, audio=self.audio)
        self.shader.fragment = (self.directory/"GLSL"/"Waveform.frag")

# ------------------------------------------------------------------------------------------------ #

class Bars(ShaderScene):
    """Basic music bars"""
    __name__ = "Music Bars"

    def build(self):
        from ShaderFlow.Modules.Audio import ShaderAudio
        from ShaderFlow.Modules.Spectrogram import ShaderSpectrogram
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderSpectrogram(scene=self, audio=self.audio, length=0)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(18000),
            piano=True
        )
        self.shader.fragment = (self.directory/"GLSL"/"Bars.frag")

# ------------------------------------------------------------------------------------------------ #

class Visualizer(ShaderScene):
    """Radial Bars Music Visualizer Scene"""
    __name__ = "Visualizer"

    def build(self):
        from ShaderFlow.Modules.Audio import ShaderAudio
        from ShaderFlow.Modules.Spectrogram import ShaderSpectrogram
        from ShaderFlow.Modules.Waveform import ShaderWaveform
        self.audio = ShaderAudio(scene=self, name="iAudio", file="/path/to/audio.ogg")
        self.waveform = ShaderWaveform(scene=self, audio=self.audio)
        self.spectrogram = ShaderSpectrogram(scene=self, length=0, audio=self.audio, smooth=False)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
            piano=True
        )
        ShaderTexture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/ex/wallhaven-ex6kmr.jpg")
        ShaderTexture(scene=self, name="logo").from_image(SHADERFLOW.RESOURCES.ICON_PNG)
        self.shader.fragment = (self.directory/"GLSL"/"Visualizer.frag")

# ------------------------------------------------------------------------------------------------ #

class RayMarch(ShaderScene):
    """Ray Marching demo"""
    __name__ = "Ray Marching"

    def build(self):
        self.shader.fragment = (self.directory/"GLSL"/"RayMarch.frag")

# ------------------------------------------------------------------------------------------------ #

class Batch(ShaderScene):
    """Batch exporting demo. Run with `shaderflow batch -b 1-3 --base /path/to/folder"""
    __name__ = "Batch"

    def export_name(self, path: Path) -> Path:
        return path.with_stem({
            1: "SubScene A",
            2: "SubScene B",
            3: "SubScene C",
        }[self.index])

# ------------------------------------------------------------------------------------------------ #

class Life(ShaderScene):
    """Conway's Game of Life in GLSL"""
    __name__ = "Game of Life"

    life_period: int = 6
    """Number of frames between each life update"""

    def setup(self):
        width, height = 192, 108
        random = numpy.random.randint(0, 2, (width, height), dtype=bool)
        self.simulation.texture.size = (width, height)
        self.simulation.texture.write(random.astype(numpy.float32), temporal=1)

    def build(self):
        self.simulation = ShaderObject(scene=self, name="iLife")
        self.simulation.texture.temporal = 10
        self.simulation.texture.filter = TextureFilter.Nearest
        self.simulation.texture.dtype = "f4"
        self.simulation.texture.components = 1
        self.simulation.texture.track = False
        self.simulation.fragment = (self.directory/"GLSL/Life/Simulation.glsl")
        self.shader.fragment = (self.directory/"GLSL/Life/Visuals.glsl")

    def pipeline(self) -> Iterable[ShaderVariable]:
        yield from ShaderScene.pipeline(self)
        yield Uniform("int", "iLifePeriod", self.life_period)

# ------------------------------------------------------------------------------------------------ #
