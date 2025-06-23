from shaderflow.scene import ShaderScene


class Mandelbrot(ShaderScene):
    """Mandelbrot fractal"""
    def build(self):
        self.shader.fragment = (self.directory/"shaders/mandelbrot.frag")

class Tetration(ShaderScene):
    """Complex tetration fractal"""
    def build(self):
        self.shader.fragment = (self.directory/"shaders/tetration.frag")
