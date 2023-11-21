from __future__ import annotations

import rich.pretty
from ShaderFlow import *

fragment_main = """
void main() {
    fragColor = texture(background, gluv.xy + iTime/5);
}
"""

fragment_child = """
void main() {
    fragColor = vec4(gluv + cos(iTime), -gluv.y, 1.0);
}
"""


class UserScene(SombreroScene):
    def setup(self):

        # Configuration
        self.context.fps = 60

        # Create child
        child = self.engine.add(SombreroEngine)
        child.shader.fragment = fragment_child
        child.create_texture_fbo()
        child.load_shaders()

        # Main shader
        self.engine.shader.fragment = fragment_main
        self.engine.add(SombreroTexture(name="background")).from_engine(child)

        # rich.print(self)

        # Map background texture to the main shader
        # self.texture = self.engine.add(SombreroTexture(name="background")).from_path(
        #     path=SHADERFLOW_DIRECTORIES.RESOURCES/"image"
        # )

    def update(self):
        if self.context.time > 5:
            self.quit()

def main():
    scene = UserScene()

if __name__ == "__main__":
    main()
