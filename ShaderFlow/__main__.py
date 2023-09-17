from ShaderFlow import *

FRAGMENT = """
void main() {
    fragColor = vec4(gluv, 0.5 - 0.5*cos(iTime), 1.0);
    fragColor = texture(test_texture, gluv + iTime/3);
}
"""

VERTEX = (SHADERFLOW_DIRECTORIES.SHADERS/"Vertex"/"Default.glsl").read_text()


class UserScene(SombreroScene):
    def setup(self):
        self.context.fps = 60
        self.mouse.action()

        # Map new texture
        self.sombrero.new_texture("test_texture").from_path(
            SHADERFLOW_DIRECTORIES.RESOURCES/"test.jpg"
        )

        # Load shaders
        self.sombrero.load_shaders(vertex=VERTEX, fragment=FRAGMENT)
        self.sombrero.__print_shaders__()

    def update(self, time: float, dt: float):
        log.info(f"New frame Pipeline:                (dt: {dt:.6f})")

        for var in self.sombrero.pipeline:
            log.info(f"  {var.name}: {var.value}")

        if time > 10:
            self.quit()

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        # log.info(f"Message: {hash} {message}")
        ...

def main():
    scene = UserScene()
    scene.loop()

if __name__ == "__main__":
    main()


# registry = SombreroRegistry()

# with registry:
#     settings = SombreroSettings().auto_bind()
#     mouse    = SombreroMouse().auto_bind()
#     camera   = Camera().auto_bind()
#     mouse.action()