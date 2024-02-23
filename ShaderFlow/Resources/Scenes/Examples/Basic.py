from ShaderFlow import *

# Warn: To be considered a Scene file, the substrings `ShaderFlow` and `SombreroScene` must be
# Warn: present on the file contents. This is a optimization to avoid scanning non-scene files.

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
        self.engine.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(stuv.x, 0, 0);
                fragColor.rgb += draw_image(child, stuv).rgb;
                fragColor.a = 1;
            }
        """)

        # Left screen is green, right screen is black
        self.child = self.engine.child(SombreroEngine)
        self.child.shader.fragment = ("""
            void main() {
                fragColor.rgb = vec3(0, 1 - stuv.x, 0);
                fragColor.a = 1;
            }
        """)

        self.engine.new_texture("child").from_module(self.child)

    def settings(self):
        ...

# -------------------------------------------------------------------------------------------------|

class Dynamics(SombreroScene):
    """Second order system demo"""
    __name__ = "Dynamics Demo"

    def build(self):

        # Create background texture
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/e7/wallhaven-e778vr.jpg")

        # Create dynamics module
        self.dynamics = self.engine.add(SombreroDynamics(frequency=4))

        # Load custom shader
        self.engine.shader.fragment = ("""
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

# Todo: Waveform Module
class Audio(SombreroScene):
    """Basic audio processing"""
    __name__ = "Audio Demo"

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio")
        self.engine.shader.fragment = ("""
            void main() {
                float k = iAudioVolume;
                fragColor = vec4(k, k, k, 1.0);
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Bars(SombreroScene):
    """Basic music bars demo"""
    __name__ = "Music Bars Demo"

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio", file="/path/to/audio_file.ogg")
        self.spectrogram = self.engine.add(SombreroSpectrogram(audio=self.audio, length=1))
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(10),
            end=BrokenPianoNote.from_frequency(18000),
        )
        self.engine.shader.fragment = ("""
            void main() {
                fragColor.rgba = vec4(0, 0, 0, 1);

                vec2 intensity = sqrt(texture(iSpectrogram, astuv.yx).xy / 100);

                if (astuv.y < intensity.x) {
                    fragColor.rgb += vec3(1.0, 0.0, 0.0);
                }
                if (astuv.y < intensity.y) {
                    fragColor.rgb += vec3(0.0, 1.0, 0.0);
                }
                if (astuv.y < (intensity.y + intensity.x)/2.0) {
                    fragColor.rgb += vec3(0.0, 0.0, 1.0);
                }

                fragColor.rgb += vec3(0.0, 0.0, 0.4*(intensity.x + intensity.y)*(1.0 - astuv.y));
                fragColor.a = 1;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Spectrogram(SombreroScene):
    """Basic spectrogram demo"""
    __name__ = "Spectrogram Demo"

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio", file="/path/to/audio_file.ogg")
        self.spectrogram = self.engine.add(SombreroSpectrogram(audio=self.audio))
        self.spectrogram._setup()
        self.spectrogram.dynamics.frequency = 20
        self.engine.shader.fragment = ("""
            void main() {
                vec2 uv = gluv2stuv(agluv * 0.99);
                uv.x += iSpectrogramOffset;
                vec2 spec = sqrt(texture(iSpectrogram, uv).xy / 100);
                fragColor.rgb = vec3(0.2) + vec3(spec.x, pow(spec.x + spec.y, 2), spec.y);
                fragColor.a = 1;
            }
        """)

# -------------------------------------------------------------------------------------------------|

class Visualizer(SombreroScene):
    """Proof of concept of a Music Visualizer Scene"""
    __name__ = "Visualizer MVP"

    # Note: This cody is messy, used as a way to see where things go wrong and be improved

    def build(self):
        self.audio = self.add(SombreroAudio, name="Audio", file="/path/to/audio_file.ogg")
        self.spectrogram = self.add(SombreroSpectrogram, length=1, audio=self.audio, smooth=False)
        self.spectrogram.make_spectrogram_matrix_piano(
            start=BrokenPianoNote.from_frequency(20),
            end=BrokenPianoNote.from_frequency(14000),
        )
        self.engine.new_texture("background").from_image("https://w.wallhaven.cc/full/rr/wallhaven-rrjvyq.png")
        self.engine.new_texture("logo").from_image(SHADERFLOW.RESOURCES.ICON)
        self.engine.add(SombreroNoise(name="Shake", dimensions=2))
        self.engine.add(SombreroNoise(name="Zoom"))
        self.engine.shader.fragment = ("""
            // Not proud of this shader :v
            void main() {
                vec2 uv = iCamera.uv;
                vec3 space = vec3(1, 11, 26) / 255;

                if (iCamera.out_of_bounds) {
                    fragColor.rgb = space;
                    return;
                }

                // Draw background
                vec2 background_uv = zoom(gluv2stuv(uv), 0.95 + 0.02*iZoom - 0.02*iAudioVolume, vec2(0.5));
                background_uv += 0.01 * iShake;
                fragColor = draw_image(background, background_uv);

                // Music bars coordinates
                vec2 music_uv = rotate2d(-PI/2) * uv;
                music_uv *= 1 - 0.4 * pow(abs(iAudioVolume), 0.5);
                float radius = 0.17;

                // Get spectrogram bar volumes
                float circle = abs(atan1_normalized(music_uv));
                vec2 freq = (texture(iSpectrogram, vec2(0, circle)).xy / 120);
                freq *= 0.3 + 1.3*smoothstep(0, 1, circle);

                // Music bars
                if (length(music_uv) < radius) {
                    vec2 logo_uv = (rotate2d(0.3*sin(3*iAudioVolumeIntegral + iTime/2)) * music_uv / (1.3*radius));
                    logo_uv *= 1 - 0.02*pow(abs(iAudioVolume), 0.1);
                    fragColor = draw_image(logo, gluv2stuv(logo_uv * rotate2d(-PI/2)));
                } else {
                    float bar = (music_uv.y < 0) ? freq.x : freq.y;
                    float r = radius + 0.5*bar;

                    if (length(music_uv) < r) {
                        fragColor.rgb = mix(fragColor.rgb, vec3(1), smoothstep(0, 1, 0.5 + bar));
                    } else {
                        fragColor.rgb *= pow((length(music_uv) - r) * 0.5, 0.05);
                    }
                }

                fragColor.rgb = mix(fragColor.rgb, space, smoothstep(0, 1, length(uv)/20));

                // Vignette
                vec2 vig = astuv * (1 - astuv.yx);
                fragColor.rgb *= pow(vig.x*vig.y * 20, 0.1 + 0.15*iAudioVolume);
                fragColor.a = 1;
            }
        """)

# -------------------------------------------------------------------------------------------------|
