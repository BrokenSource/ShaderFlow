from __future__ import annotations

import rich.pretty
from ShaderFlow import *

COUNT = 0
def count():
    global COUNT
    return (COUNT := COUNT+1)
SombreroID = count
# SombreroID = uuid.uuid4


@attrs.define
class SombreroModule:
    scene: SombreroScene = None

    # Module hierarchy
    uuid:             SombreroID  = attrs.field(factory=SombreroID)
    __group__:    Set[SombreroID] = attrs.field(factory=set)
    __children__: Set[SombreroID] = attrs.field(factory=set)
    __parent__:       SombreroID  = None

    @property
    def group(self) -> List[SombreroID]:
        """Returns a list of the modules in the 'super node' group of this module"""
        return [self.scene.modules[uuid] for uuid in self.__group__]

    @property
    def children(self) -> List[SombreroID]:
        """Returns a list of the children of this module"""
        return [self.scene.modules[uuid] for uuid in self.__children__]

    @property
    def parent(self) -> SombreroModule | None:
        """Returns the parent module of this module"""
        return self.scene.modules.get(self.__parent__, None)

    # # # #

    def add(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """
        Add a module to the scene

        Args:
            module: The module to add

        Returns:
            The module added
        """

        # Instantiate if needed
        if not isinstance(module, SombreroModule):
            module = module()

        log.trace(f"Registering module ({module.uuid}) - {module.__class__.__name__}")

        # Register the module on the scene
        self.scene.modules[module.uuid] = module
        module.scene = self.scene

        # Add new module as a child of this one
        self.__children__.add(module.uuid)

        # The module's collection includes the parent module
        module.__parent__ = self.uuid

        # Childs of this module forms a collection
        for child in self.children:
            child.__group__.update(self.__children__)
            child.__group__.discard(self.uuid)

        return module

    # # # #

    def find(self, type: Type[SombreroModule], recursive: bool=True) -> List[SombreroModule]:
        """
        Find modules of a given type in the scene

        Args:
            type: The type of the module to find
            recursive: Whether to search recursively through the hierarchy

        Returns:
            list[SombreroModule]: The list of modules found (empty if none)
        """
        list = []

        for module in self.children + self.group:
            if isinstance(module, type):
                list.append(module)

        if (not recursive) or (not self.parent):
            return list

        return list + self.parent.find(type=type, recursive=recursive)

    # # # #

    @property
    def context(self) -> SombreroContext | None:
        return self.find(SombreroContext)[0]

    @property
    def window(self) -> SombreroWindow | None:
        return self.find(SombreroWindow)[0]

    @property
    def mouse(self) -> SombreroMouse | None:
        return self.find(SombreroMouse)[0]


@attrs.define
class SombreroContext(SombreroModule):
    time: float = 0

    def test(self):
        log.warning("Hello from Context")
        log.warning("Window is:")
        rich.print(self.window)

@attrs.define
class SombreroWindow(SombreroModule):
    width:  int = 1280
    height: int = 720

    def test(self):
        log.warning("Hello from Window")
        log.warning("Context is:")
        rich.print(self.context)

@attrs.define
class SombreroMouse(SombreroModule):
    x: int = 0
    y: int = 0

    def test(self):
        log.warning("Hello from Mouse")
        self.context.time = 1

class SombreroEngine(SombreroModule):
    def test(self):
        log.warning("Hello from Shader")

@attrs.define
class SombreroScene(SombreroModule):
    modules: Dict[SombreroID, SombreroModule] = attrs.field(factory=dict)

    def __attrs_post_init__(self):
        self.modules[self.uuid] = self
        self.scene = self
        self.setup()

    def setup(self):

        # # Sanity check 1: Simple context
        self.add(SombreroContext)

        if False:
            log.info("Sombrero Scene is:")
            rich.print(self)

            # log.info("Sombrero Context is:")
            # rich.print(self.context)

        # # Sanity check 2: Add window
        self.add(SombreroWindow)

        if False:
            log.info("Sombrero Scene is:")
            rich.print(self)

            # log.info("Sombrero window is:")
            # rich.print(self.window)

            self.window.test()
            self.context.test()

        # # Sanity check 3: Add mouse
        self.add(SombreroMouse)
        self.mouse.test()

        if True:
            log.info("Sombrero Scene is:")
            rich.print(self)

        # # Sanity check 4: Add dummy
        shader1 = self.add(SombreroEngine)
        shader2 = shader1.add(SombreroEngine)
        shader3 = shader1.add(SombreroEngine)
        shader4 = shader2.add(SombreroEngine)

        if True:
            log.info("Sombrero Scene is:")
            rich.print(self)





def main():
    scene = SombreroScene()

if __name__ == "__main__":
    main()
