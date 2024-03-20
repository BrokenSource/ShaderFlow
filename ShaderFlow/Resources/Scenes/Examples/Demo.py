from ShaderFlow import *

BACKGROUND = "https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg"

# -------------------------------------------------------------------------------------------------|

class Default(ShaderScene):
    """The most basic ShaderFlow Scene, the default shader"""
    ...

# -------------------------------------------------------------------------------------------------|

class Nested(ShaderScene):
    """Basic scene with two shaders acting together, main shader referencing the child"""
    __name__ = "Nested Shaders"

    def build(self):
        ShaderScene.build(self)
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

class Multipass(ShaderScene):
    """Many Layers ('Buffers') done on a single shader"""
    __name__ = "Multipass"

    def build(self):
        ShaderScene.build(self)
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.layers = 2
        self.shader.fragment = self.read_file("GLSL/Multipass.frag")

# -------------------------------------------------------------------------------------------------|

class Temporal(ShaderScene):
    """Poor's man Motion Blur. If you dislike the effect, definitely don't run this"""
    __name__ = "Temporal"

    def build(self):
        ShaderScene.build(self)
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shader.texture.temporal = 10
        self.shader.texture.layers = 2
        self.shader.fragment = self.read_file("GLSL/Temporal.frag")

# -------------------------------------------------------------------------------------------------|

class Dynamics(ShaderScene):
    """Second order system"""
    __name__ = "Dynamics"

    def build(self):
        ShaderScene.build(self)
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.dynamics = ShaderDynamics(scene=self, name="iShaderDynamics", frequency=4)
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.85 + 0.1*iShaderDynamics, vec2(0.5));
                fragColor = draw_image(background, uv);
                fragColor.a = 1;
            }
        """)

    def update(self):
        self.dynamics.target = 0.5 * (1 + numpy.sign(numpy.sin(2*math.pi*self.time * 0.5)))

# -------------------------------------------------------------------------------------------------|

class Noise(ShaderScene):
    """Basics of Simplex noise"""
    __name__ = "Procedural Noise"

    def build(self):
        ShaderScene.build(self)
        ShaderTexture(scene=self, name="background").from_image(BACKGROUND)
        self.shake_noise = ShaderNoise(scene=self, name="Shake", dimensions=2)
        self.zoom_noise  = ShaderNoise(scene=self, name="Zoom")
        self.shader.fragment = ("""
            void main() {
                vec2 uv = zoom(stuv, 0.95 + 0.02*iZoom, vec2(0.5));
                uv += 0.02 * iShake;
                fragColor = draw_image(background, uv);
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Video(ShaderScene):
    """Video as a Texture demo"""
    __name__ = "Video"

    def build(self):
        ShaderScene.build(self)
        BUNNY = "https://download.blender.org/demo/movies/BBB/bbb_sunflower_1080p_60fps_normal.mp4.zip"
        self.video = next(BrokenPath.get_external(BUNNY).rglob("*.mp4"))
        ShaderVideo(scene=self, path=self.video)
        self.shader.fragment = self.read_file("GLSL/Video.frag")

# -------------------------------------------------------------------------------------------------|

class Audio(ShaderScene):
    """Basic audio processing"""
    __name__ = "Audio"

    def build(self):
        ShaderScene.build(self)
        self.audio = ShaderAudio(scene=self, name="Audio")
        self.shader.fragment = ("""
            void main() {
                fragColor = vec4(vec3(iAudioVolume), 1.0);
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Waveform(ShaderScene):
    """Audio Waveform Oscilloscope demo"""
    __name__ = "Waveform"

    def build(self):
        ShaderScene.build(self)
        self.audio = ShaderAudio(scene=self, name="Audio", file="/path/to/audio.ogg")
        self.waveform = ShaderWaveform(scene=self, audio=self.audio)
        self.shader.fragment = self.read_file("GLSL/Waveform.frag")

# -------------------------------------------------------------------------------------------------|

class Bars(ShaderScene):
    """Basic music bars"""
    __name__ = "Music Bars"

    def build(self):
        ShaderScene.build(self)
        self.audio = ShaderAudio(scene=self, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderSpectrogram(scene=self, audio=self.audio, length=0)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(18000),
            piano=True
        )
        self.shader.fragment = self.read_file("GLSL/Bars.frag")

# -------------------------------------------------------------------------------------------------|

class Visualizer(ShaderScene):
    """Radial Bars Music Visualizer Scene"""
    __name__ = "Visualizer"

    def build(self):
        ShaderScene.build(self)
        self.audio = ShaderAudio(scene=self, name="Audio", file="/path/to/audio.ogg")
        self.spectrogram = ShaderSpectrogram(scene=self, length=0, audio=self.audio, smooth=False)
        self.spectrogram.from_notes(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
            piano=True
        )
        ShaderTexture(scene=self, name="background").from_image("https://w.wallhaven.cc/full/rr/wallhaven-rrjvyq.png")
        ShaderTexture(scene=self, name="logo").from_image(SHADERFLOW.RESOURCES.ICON)
        ShaderNoise(scene=self, name="Shake", dimensions=2)
        ShaderNoise(scene=self, name="Zoom")
        self.shader.fragment = self.read_file("GLSL/Visualizer.frag")

# -------------------------------------------------------------------------------------------------|

class Life(ShaderScene):
    """Conway's Game of Life in GLSL"""
    __name__ = "Game of Life"

    life_each: int = 6
    """Number of frames between each life update"""

    def load_life(self):
        width, height = 192, 108
        random = numpy.random.randint(0, 2, (width, height), dtype=bool)
        self.simulation.texture.size = (width, height)
        self.simulation.texture.write(random.astype(numpy.float32), temporal=1)

    def build(self):
        ShaderScene.build(self)
        self.shader.fragment = self.read_file("GLSL/Life/Visuals.glsl")
        self.simulation = Shader(scene=self, name="iLife")
        self.simulation.fragment = self.read_file("GLSL/Life/Simulation.glsl")
        self.simulation.texture.filter = TextureFilter.Nearest
        self.simulation.texture.components = 1
        self.simulation.texture.temporal = 10
        self.simulation.texture.track = False
        self.load_life()

    def pipeline(self):
        yield from ShaderScene.pipeline(self)
        yield ShaderVariable("uniform", "int", "iLifeEach", self.life_each)

# -------------------------------------------------------------------------------------------------|
