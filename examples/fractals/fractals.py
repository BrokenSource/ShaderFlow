from pathlib import Path

from shaderflow.scene import ShaderScene

shaders: Path = (Path(__file__).parent/"shaders")

class Mandelbrot(ShaderScene):
    """Mandelbrot fractal"""
    def build(self):
        self.shader.fragment = (shaders/"mandelbrot.frag")

class Tetration(ShaderScene):
    """Complex tetration fractal"""
    def build(self):
        self.shader.fragment = (shaders/"tetration.frag")
