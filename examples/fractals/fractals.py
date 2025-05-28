from shaderflow.scene import ShaderScene


class Mandelbrot(ShaderScene):
    """Mandelbrot fractal shader"""

    def build(self):
        self.shader.fragment = (self.directory/"shaders/mandelbrot.frag")
