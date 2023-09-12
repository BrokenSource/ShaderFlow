from ShaderFlow import *


class UserScene(SombreroScene):
    def setup(self):
        self.context.fps = 10
        self.mouse.action()

    def update(self, time: float, dt: float):
        log.info(f"Time: {time:.5f}s {dt:.6f}")

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