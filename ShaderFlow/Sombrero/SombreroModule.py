from __future__ import annotations

from . import *

# Identifier for modules
SombreroID = uuid.uuid4

# Apply deterministic UUIDs?
if (SHADERFLOW_CONFIG.default("deterministic_uuids", True)):
    SombreroID = lambda: uuid.UUID(int=random.randint(0, 2**128))
    random.seed(0)


@attrs.define
class SombreroModule(BrokenFluentBuilder):
    scene: SombreroScene = None

    # Note: A prefix for variable names - "iTime", "rResolution", etc
    prefix: str = "i"

    # # Module hierarchy and identification
    uuid:             SombreroID  = attrs.field(factory=SombreroID)
    __group__:    Set[SombreroID] = attrs.field(factory=set)
    __children__: Set[SombreroID] = attrs.field(factory=set)
    __parent__:       SombreroID  = None

    @property
    def suuid(self) -> str:
        """Short UUID for printing"""
        return str(self.uuid)[:8]

    # # Hierarchy methods

    @property
    def group(self) -> List[SombreroModule]:
        """Returns a list of the modules in the 'super node' group of this module"""
        return [self.scene.modules[uuid] for uuid in self.__group__]

    @property
    def children(self) -> List[SombreroModule]:
        """Returns a list of the children of this module"""
        return [self.scene.modules[uuid] for uuid in self.__children__]

    @property
    def parent(self) -> SombreroModule | None:
        """Returns the parent module of this module"""
        return self.scene.modules.get(self.__parent__, None)

    @property
    def bound(self) -> List[SombreroModule]:
        """Returns a list of the modules related to this module"""
        return BrokenUtils.truthy(self.group + [self.parent] + self.children)

    # # Adding modules

    def child(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """Add a child to this module, starting a new group"""
        self.scene.register(module := module())
        self.__children__.add(module.uuid)
        module.__parent__ = self.uuid
        return module

    def add(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """Add a module to this module's group"""
        self.scene.register(module := module())
        self.__group__.add(module.uuid)

        # Modules on the same group share the same parent - assign it to the new
        module.__parent__ = getattr(self.parent, "uuid", None)

        # Reflect the updated group to all others
        for other in self.group:
            other.__group__.update(self.__group__)
            other.__group__.discard(other.uuid)

        return module

    # # Finding modules

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

    # # Pipeline of modules

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

    def full_pipeline(self) -> List[ShaderVariable]:
        """Full pipeline for this module following the hierarchy"""

        # Start with own pipeline if not the root module
        pipeline = self.pipeline()

        # 1. A module's full pipeline contains their children's one;
        for module in self.group + self.children:
            pipeline += module.pipeline()

        # 2. And shall recurse to all parents
        if self.parent:
            pipeline += self.parent.full_pipeline()

        return pipeline

    # # User defined methods

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
