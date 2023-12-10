from __future__ import annotations

from . import *

# Identifier for modules
SombreroID = uuid.uuid4

# Apply deterministic UUIDs?
if (SHADERFLOW.CONFIG.default("deterministic_uuids", True)):
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
    def who(self) -> str:
        """Basic module information of UUID and Class Name"""
        return f"({self.suuid} | {self.__class__.__name__[:16].ljust(16)})"

    @property
    def suuid(self) -> str:
        """Short UUID for printing"""
        return str(self.uuid)[:8].upper()

    # # Hierarchy methods

    @property
    def group(self) -> List[SombreroModule]:
        """List of the modules in the 'super node' group of this module"""
        return [self.scene.modules[uuid] for uuid in self.__group__]

    @property
    def children(self) -> List[SombreroModule]:
        """List of the children of this module"""
        return [self.scene.modules[uuid] for uuid in self.__children__]

    @property
    def parent(self) -> SombreroModule | None:
        """Parent module of this module"""
        return self.scene.modules.get(self.__parent__, None)

    @property
    def bound(self) -> List[SombreroModule]:
        """List of the modules related to this module"""
        return BrokenUtils.truthy(self.group + [self.parent] + self.children)

    # # Module manipulation

    def child(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """Add a child to this module, starting a new group"""
        self.scene.register(module := module())
        self.__children__.add(module.uuid)
        module.__parent__ = self.uuid
        module.setup()
        return module

    def add(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """Add a module to this module's group"""
        self.scene.register(module := module())
        self.__group__.add(module.uuid)

        # Modules on the same group share the same parent - assign it to the new
        module.__parent__ = self.__parent__

        # Reflect the updated group to all others
        for other in self.group:
            other.__group__.update(self.__group__ | {self.uuid})
            other.__group__.discard(other.uuid)

        module.setup()
        return module

    def swap(self, module: SombreroModule | Type[SombreroModule]) -> None:
        """
        Swap this module with another one

        Args:
            module: The module to swap with
        """
        log.info(f"{self.who} Swapping with {module.who}")
        self.scene.register(module := module(uuid=self.uuid))

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

        if (not recursive) or (not self.__parent__):
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

    # # Messaging

    def relay(self,
        message: SombreroMessage,
        children: bool=True,
        group: bool=True,
        __received__: Set[SombreroID]=None,
        uuid: SombreroID=None
    ) -> None:
        """
        Relay a message to all related modules down the hierarchy

        Args:
            message:  The message to relay
            children: Whether to relay the message to children
            group:    Whether to relay the message to the group
        """
        uuid = uuid or self.uuid

        # If the message is a class reference, instantiate it
        if isinstance(message, type):
            message = message()

        # Python death trap - mutable default arguments
        __received__ = __received__ or set()

        # Trace message when received is empty
        if len(__received__) == 0:
            log.trace(f"{self.who} Relaying {message}", echo=SHADERFLOW.CONFIG.default("trace_relay", False))

        # Skip if already received else register self
        if self.uuid in __received__:
            return
        __received__.add(self.uuid)

        # Process the message
        self.__handle__(message)
        self.handle(message)

        # Recurse to children and group optionally
        for module in (self.children*children) + (self.group*group):
            module.relay(message, children=children, group=group, __received__=__received__, uuid=uuid)

    @abstractmethod
    def __handle__(self, message: SombreroMessage) -> None:
        """Internal method for self.handle"""
        pass

    @abstractmethod
    def handle(self, message: SombreroMessage) -> None:
        """
        Receive a message from any related module

        Args:
            message: The message received
        """
        pass

    # # Pipeline of modules

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
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
        # Fixme: This is a bottleneck function

        # Start with own pipeline if not the root module
        pipeline = self.pipeline()

        # 1. A module's full pipeline contains their children's one;
        for module in self.group + self.children:
            pipeline += module.pipeline() or []

        # 2. And shall recurse to all parents
        if self.parent:
            pipeline += self.parent.full_pipeline()

        return BrokenUtils.flatten(pipeline)

    # # User defined methods

    @abstractmethod
    def setup(self) -> Self:
        """
        Let the module configure itself, called after the module is added to the scene
        - For example, a Keyboard module might subscribe to window events here
        """
        return self

    @abstractmethod
    def update(self) -> None:
        """
        Called every frame for updating internal states, interpolation
        """
        pass
