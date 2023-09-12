from __future__ import annotations

from . import *

# What to use for module indentifiers
SombreroHash = uuid.uuid4

@attrs.define
class SombreroRegistry:
    """
    A registry to keep track of all SombreroModule

    ```python
    # Initialize registry
    registry = SombreroRegistry()

    # Initialize modules
    module1 = Module1()
    module2 = Module2()
    module3 = Module3()

    # Register modules to registry
    registry.register(module1, module2, module3)

    # Relay a message to all modules from a source hash
    registry.relay(hash, message)
    ```

    Instead of manually registering modules, you can enter its context or activate it
    NOTE: There can only be one active registry at a time

    ```python
    # Context manager
    with registry:
        module1 = Module1()
        module2 = Module2()
        ...

    # Activation
    registry.activate()
    module1 = Module1()
    module2 = Module2()
    ```
    """

    # Dictionary that loosely-couples uuids to modules
    modules: dict[SombreroHash, SombreroModule] = attrs.Factory(dict)

    # # Registration of new modules

    # Auto bind module set to new modules
    auto_bind: set[SombreroHash] = attrs.Factory(set)

    def register(self, *modules: SombreroModule | List[SombreroModule]) -> None:
        """Register a module to this registry"""
        for module in BrokenUtils.flatten(modules):
            log.debug(f"Registering new module: ({module.short_hash}) ({module.__class__.__name__})")

            # Register and auto bind on incoming module
            self.modules[module.hash] = module
            map(lambda item: module.bind(item), self.auto_bind)

    def get(self, hash: SombreroHash) -> SombreroModule | None:
        """Get a module from the registry using its Hash"""
        return self.modules.get(hash, None)

    # # Context registry activation

    ACTIVE_CONTEXT = None

    def __enter__(self) -> SombreroRegistry:
        """Activate this registry"""
        SombreroRegistry.ACTIVE_CONTEXT = self
        return self

    def __exit__(self, *args) -> None:
        """Deactivates any registry"""
        SombreroRegistry.ACTIVE_CONTEXT = None

    # # Messaging

    def relay(self, hash: SombreroHash, message: SombreroMessage) -> None:
        """Relay some message to all modules"""
        log.trace(f"Relaying message ({hash}): {message}")
        for module in self.modules.values():
            module.on_message(
                hash=hash,
                bound=hash in module.bound,
                message=message
            )

    # # Pipelining

    def update(self, time: float, dt: float) -> None:
        """
        Once per frame, after the modules changes their internal target states, call
        update on all registered modules for interpolation or custom time based actions

        Args:
            time: Time since the start of the shader
            dt: Time in seconds since the last frame

        Returns:
            None: Nothing
        """
        for module in self.modules.values():
            module.update(time=time, dt=dt)

    # # Experimental Serde

    def serialize(self) -> dict:
        """Serialize this registry to a dictionary"""
        return {f"{module.__class__.__name__}-{module.short_hash}": module.serialize() for module in self.modules.values()}

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroModule:
    """
    The base class for "Modules" or "Components", "Actors" of Sombrero shader engine

    ```python
    registry = SombreroRegistry()

    # Manual binding
    with registry:
        mouse  = Mouse()
        camera = Camera()

        # Messages from mouse are bound=True to camera
        camera.bind(mouse)
    mouse.action()

    # Auto binding
    with registry:
        mouse  = Mouse().auto_bind()
        camera = Camera().auto_bind()

        # Any module created now will bind to both above
    mouse.action()

    # Context binding
    with registry:
        with (mouse := Mouse()):
            camera = Camera()
    mouse.action()
    ```
    """

    # Hash identification of this module
    hash: SombreroHash = attrs.field(factory=SombreroHash, converter=str)

    # Registry of all modules
    registry: SombreroRegistry = attrs.Factory(SombreroRegistry)

    # Modules that this module should listen to
    bound: set[SombreroHash] = attrs.Factory(set)

    # # Initialization

    def __attrs_post_init__(self):

        # Get the active registry from context if none was provided
        self.registry = SombreroRegistry.ACTIVE_CONTEXT or self.registry

        if not self.registry:
            err = f"No registry was provided and no active registry was found [{self.registry=}]"
            log.error(err)
            raise RuntimeError(err)

        # Register this module to the registry
        self.registry.register(self)

    @property
    def short_hash(self) -> str:
        """Get a short hash of this module"""
        return str(self.hash)[:8]

    # # The Binding of Modules

    def bind(self, *modules: SombreroModule | SombreroHash | Iterable) -> Self:
        """
        Bind this module to some other modules
        - Messages from bound modules are now tagged "bound" on .on_message (should listen)

        Args:
            modules: A module instance, hash or iterable of the previous

        Returns:
            Self: Fluent interface
        """
        for item in BrokenUtils.flatten(modules):
            self.bound.add(getattr(item, "hash", item))
        return self

    def __matmul__(self, *modules: SombreroModule | SombreroHash | Iterable) -> Self:
        """Wraps self.bind"""
        return self.bind(modules)

    # # Auto binding

    def auto_bind(self, status: bool=True) -> Self:
        """
        Automatically bind this module to new registered modules on the registry
        Call .auto_bind(False) to disable

        Args:
            status: Should this module be automatically bound to new modules?

        Returns:
            Self: Fluent interface
        """
        (self.registry.auto_bind.add if status else self.registry.auto_bind.remove)(self.hash)
        return self

    def __enter__(self) -> Self:
        """Wraps self.auto_bind(True)"""
        return self.auto_bind(status=True)

    def __exit__(self, *args) -> None:
        """Wraps self.auto_bind(False)"""
        self.auto_bind(status=False)

    # # Finding ~nemo~ modules

    def find(self, type: Type[SombreroModule], all: bool=False) -> SombreroModule | None:
        """
        Find some bound module of a given type, for example .find(SombreroSettings)

        Args:
            type: The type of the module to find
            all: List of all modules of the given type or first one if any

        Returns:
            SombreroModule | None: The module instance or None if not found
        """
        list = []
        for module in self.registry.modules.values():
            if isinstance(module, type):
                if not all: return module
                list.append(module)
        return list or None

    @staticmethod
    def broken_extend(name: str, type: Type) -> None:
        """
        Add a property to SombreroModule that finds a module of a given type
        It's better explained in code:

        ```python
        # Manual method
        context = camera.find(SombreroContext)

        # Automatic property method
        SombreroModule.broken_extend("context", SombreroContext)
        context = camera.context
        ```
        """
        BrokenUtils.extend(SombreroModule, name=name, as_property=True)(
            lambda self: self.find(type=type)
        )

    # # Messaging

    def relay(self, message: SombreroMessage) -> Self:
        """
        Relay a message to all modules on the registry

        Args:
            message: Some message payload from SombreroMessage

        Returns:
            Self: Fluent interface
        """
        self.registry.relay(self.hash, message)
        return self

    @abstractmethod
    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage) -> None:
        """
        Handle incoming messages from the Registry send by other modules

        Args:
            hash: Hash of the module that sent the message
            bound: Does this module should listen to the sender? (is bound?)
            message: Some message payload from SombreroMessage

        Returns:
            None: Shouldn't, as the Registry does nothing with the return
        """
        if bound:
            log.warning(f"({self.short_hash}) Unhandled message from component ({hash}): {message}")

    # # Experimental serde

    def serialize(self) -> dict[hash, Self]:
        """Serialize this module to a dictionary"""
        return {"class": self.__class__.__name__} | attrs.asdict(self,
            filter=lambda attribute, value: not isinstance(value, SombreroRegistry),
        )

    # # SombreroGL Specific methods

    def update(self, time: float, dt: float) -> None:
        """
        Called every frame for updating internal states, interpolation

        Args:
            time: Time since the start of the shader
            dt: Time in seconds since the last frame

        Returns:
            None: Shouldn't, as the Registry does nothing with the return
        """
        pass

    @property
    def pipeline(self) -> dict[str, Any]:
        """
        Get the state of this module to be piped to the shader
        """
        return {}
