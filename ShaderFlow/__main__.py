from __future__ import annotations

import rich.pretty
from ShaderFlow import *


class UserScene(SombreroScene):
    def setup(self):
        log.info("Setting up UserScene")
        rich.print(self)

    def update(self):
        if self.context.time > 0.5:
            self.quit()

def main():
    scene = UserScene()

if __name__ == "__main__":
    main()
