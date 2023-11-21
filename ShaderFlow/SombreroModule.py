from __future__ import annotations

from . import *


@attrs.define
class SombreroModule:
    scene: SombreroScene = None

    # # Module hierarchy
    uuid:             SombreroID  = attrs.field(factory=SombreroID)
    __group__:    Set[SombreroID] = attrs.field(factory=set)
    __children__: Set[SombreroID] = attrs.field(factory=set)
    __parent__:       SombreroID  = None

    # Note: A prefix for variable names - "iTime", "rResolution", etc
    prefix: str = "i"

    @property
    def suuid(self) -> str:
        """Short UUID for printing"""
        return str(self.uuid)[:8]

    def __call__(self, **kwargs) -> Self:
        """Calling a module updates its attributes"""
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    # # Hierarchy wise

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

    @property
    def bound(self) -> List[SombreroModule]:
        """Returns a list of the modules related to this module"""
        return self.group + self.children + [self.parent]

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
            child.__group__.discard(child.uuid)

        return module

    # # Find wise

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

        for module in self.bound:
            if isinstance(module, type):
                list.append(module)

        if (not recursive) or (not self.parent):
            return list

        return list + self.parent.find(type=type, recursive=recursive)

    @staticmethod
    def make_findable(type: Type) -> None:
        """
        # Manual method
        context = module.find(SombreroContext)

        # Automatic property method
        SombreroModule.make_findable(SombreroContext)
        context = module.context
        """
        name = type.__name__.lower().removeprefix("sombrero")
        BrokenUtils.extend(SombreroModule, name=name, as_property=True)(
            lambda self: self.find(type=type)[0]
        )

    # # Scene wise

    @abstractmethod
    def pipeline(self) -> List[ShaderVariable]:
        """
        Get the state of this module to be piped to the shader
        As a side effect, also the variable definitions and default values
        Note: Variable names should start with self.prefix

        Returns:
            List[ShaderVariable]: List of variables and their states
        """
        return []

    def full_pipeline(self, _visited: Set[SombreroID]=set()) -> List[ShaderVariable]:
        """Full pipeline for this module following the hierarchy"""

        # Start with own pipeline
        pipeline = self.pipeline()

        # 1. A module's full pipeline contains their children;
        for child in self.children:
            pipeline += child.pipeline()

        # 2. And shall recurse to all parents
        if self.parent:
            pipeline += self.parent.full_pipeline()

        return pipeline

    # # User wise

    @abstractmethod
    def setup(self) -> None:
        """
        Let the module configure itself, called after the module is added to the scene
        - For example, a Keyboard module might subscribe to window events here
        """
        pass

    @abstractmethod
    def update(self) -> None:
        """
        Called every frame for updating internal states, interpolation
        """
        pass
