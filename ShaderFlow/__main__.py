from ShaderFlow import *

# -------------------------------------------------------------------------------------------------|

class EmptyScene(SombreroScene):
    """Default vertex and fragment shaders"""
    ...

# -------------------------------------------------------------------------------------------------|

BASIC_FRAGMENT = """
void main() {
    fragColor = vec4(gluv, 0.5 - 0.5*cos(iTime), 1.0);
}
"""

class BasicScene(SombreroScene):
    """Basic Fragment shader loading example"""
    def setup(self):
        self.sombrero.load_shaders(fragment=BASIC_FRAGMENT)

# -------------------------------------------------------------------------------------------------|

TEXTURE_FRAGMENT = """
void main() {
    fragColor = texture(test_texture, gluv + iTime/5);
}
"""

class TextureScene(SombreroScene):
    """Texture mapping from file or image example"""
    def setup(self):
        self.sombrero.new_texture("test_texture").from_path(SHADERFLOW_DIRECTORIES.RESOURCES/"test.jpg")
        self.sombrero.load_shaders(fragment=TEXTURE_FRAGMENT)

# -------------------------------------------------------------------------------------------------|

DYNAMICS_FRAGMENT = """
void main() {
    fragColor = vec4(gluv, 0.5 - 0.5*cos(iTime), 1.0);
    fragColor = texture(test_texture, gluv*(0.8 + 0.2*system) + iTime/10);

    if (instance == 1) {
        // fragColor = vec4(1.0, 0.0, 0.0, gluv.x);
    }
}
"""

class DynamicsScene(SombreroScene):
    """Second order control system example"""
    def setup(self):

        # Create a second order system
        with self.registry:
            self.sos = SombreroSceneSecondOrderSystem(name="system", value=0, frequency=3, zeta=0.3, response=0)
            self.sombrero.bind(self.sos)

        # Map new texture
        self.sombrero.new_texture("test_texture").from_path(SHADERFLOW_DIRECTORIES.RESOURCES/"test.jpg")

        # Load shaders
        self.sombrero.load_shaders(fragment=DYNAMICS_FRAGMENT)

    def update(self, time: float, dt: float):
        self.sos.system.target = 0.2 * (1 + numpy.sign(numpy.sin(2*math.pi*time * 0.5)))
        self.__print_pipeline__()

# -------------------------------------------------------------------------------------------------|

CHILD_FRAGMENT = """
void main() {
    fragColor = vec4(gluv, 0.5 - 0.5*cos(iTime), 1.0);
}
"""

MAIN_FRAGMENT = """
void main() {
    fragColor = texture(child, gluv);
    // fragColor += vec4(0.2);
}
"""

class ChildScene(SombreroScene):
    """Mapping child shaders example"""
    def setup(self):

        # Create child class
        self.child = self.sombrero.child()
        self.child.load_shaders(fragment=CHILD_FRAGMENT)

        # Load main shaders
        self.sombrero.new_texture("child").from_sombrero(self.child)
        self.sombrero.load_shaders(fragment=MAIN_FRAGMENT)

    def update(self, time: float, dt: float):
        # self.__print_pipeline__()
        ...

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        # log.info(f"Message: {hash} {message}")
        ...

# -------------------------------------------------------------------------------------------------|

def main():
    scene = DynamicsScene()
    scene.loop()

if __name__ == "__main__":
    main()


# registry = SombreroRegistry()

# with registry:
#     settings = SombreroSettings().auto_bind()
#     mouse    = SombreroMouse().auto_bind()
#     camera   = Camera().auto_bind()
#     mouse.action()