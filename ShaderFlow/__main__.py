from ShaderFlow import *


class UserScene(SombreroScene):
    def setup(self):
        log.info("Setting up UserScene")
        log.info(f"Context: {self.context}")

def main():
    scene = UserScene()

if __name__ == "__main__":
    main()
