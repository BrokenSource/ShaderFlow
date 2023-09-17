from ShaderFlow import *

FRAGMENT = """
void main() {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""

VERTEX = (SHADERFLOW_DIRECTORIES.SHADERS/"Vertex"/"Default.glsl").read_text()


class UserScene(SombreroScene):
    def setup(self):
        self.context.fps = 10
        self.mouse.action()

        self.sombrero.load_shaders(vertex=VERTEX, fragment=FRAGMENT)

    def update(self, time: float, dt: float):
        log.info(f"Time: {time:.5f}s {dt:.6f}")

        for name, value in self.sombrero.pipeline:
            log.info(f"  {name}: {value}")

        if time > 3:
            self.quit()

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        # log.info(f"Message: {hash} {message}")
        ...

def main():
    log.info(f"ShaderFlow Alive")
    scene = UserScene()

    if (test_serde := False):
        data = scene.registry.serialize()
        Path("data.toml").write_text(toml.dumps(data))

    scene.loop()

if __name__ == "__main__":
    main()


# registry = SombreroRegistry()

# with registry:
#     settings = SombreroSettings().auto_bind()
#     mouse    = SombreroMouse().auto_bind()
#     camera   = Camera().auto_bind()
#     mouse.action()