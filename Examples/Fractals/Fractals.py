from ShaderFlow.Scene import ShaderScene


class Mandelbrot(ShaderScene):
    def build(self):
        self.shader.fragment = (self.directory/"GLSL"/"Mandelbrot.frag")
