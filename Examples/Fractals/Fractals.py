from ShaderFlow.Scene import ShaderScene


class Mandelbrot(ShaderScene):
    """Mandelbrot fractal shader"""

    def build(self):
        self.shader.fragment = (self.directory/"GLSL"/"Mandelbrot.frag")
