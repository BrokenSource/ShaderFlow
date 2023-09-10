from __future__ import annotations
from Broken import *

# -------------------------------------------------------------------------------------------------|

class SombreroMessage:
    class Any:
        data: Any

    class Mouse:

        @attrs.define
        class Position:
            x: int
            y: int

    class Window:
        @attrs.define
        class Resize:
            width:  int = None
            height: int = None

        @attrs.define
        class Render:
            ...

        @attrs.define
        class Iconify:
            state: bool = None

        @attrs.define
        class FileDrop:
            files: list[str] = None


# -------------------------------------------------------------------------------------------------|

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

    Instead of manually registering modules, you can activate a registry:

    ```python
    with registry:
        module1 = Module1()
        module2 = Module2()
        ...
    ```
    """

    # Dictionary that loosely-couples uuids to modules
    modules: dict[SombreroHash, SombreroModule] = attrs.Factory(dict)

    # # Registration of new modules

    # Auto bind module set to new modules
    auto_bind: set[SombreroHash] = attrs.Factory(set)

    def register(self, *modules: SombreroModule | List[SombreroModule]) -> None:
        """Register a module to the registry"""
        for module in BrokenUtils.flatten(modules):
            log.debug(f"Registering new module: ({module.short_hash}) ({module.__class__.__name__})")
            self.modules[module.hash] = module

            # Auto bind modules
            for item in self.auto_bind:
                module.bind(item)

    def get(self, hash: SombreroHash) -> SombreroModule | None:
        """Get a module from the registry using its Hash"""
        return self.modules.get(hash, None)

    # # Context registry activation

    context_stack = []

    def __enter__(self) -> SombreroRegistry:
        """Activate this registry as the active one"""
        SombreroRegistry.context_stack.append(self)
        return self

    def __exit__(self, *args) -> None:
        """Deactivate this registry"""
        SombreroRegistry.context_stack.pop()

    @staticmethod
    def active() -> SombreroRegistry | None:
        """Get the last active registry context"""
        try:
            return SombreroRegistry.context_stack[-1]
        except IndexError:
            return None

    # # Messaging

    def relay(self, hash: SombreroHash, message: SombreroMessage) -> None:
        """Relay some message to all modules"""
        for module in self.modules.values():
            module.on_message(
                hash=hash,
                bound=hash in module.bound,
                message=message
            )

    # # Pipelining

    def update(self, time: float, dt: float) -> None:
        """Update all modules"""
        for module in self.modules.values():
            module.update(time=time, dt=dt)

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroModule:
    """
    The base class for "Modules" or "Components", "Actors" of Sombrero

    ```python
    registry = SombreroRegistry()

    # Alternative 1: Manual
    with registry:
        mouse  = Mouse()
        camera = Camera()
        camera.bind(mouse)
        mouse.action()

    # Alternative 2: Automatic
    with registry:
        mouse  = Mouse().auto_bind()
        camera = Camera().auto_bind()
        mouse.action()
    ```
    """
    # Hash identification of this module
    hash: SombreroHash = attrs.Factory(SombreroHash)

    # Registry of all modules
    registry: SombreroRegistry = attrs.Factory(SombreroRegistry)

    # Modules that this module should listen to
    bound: set[SombreroHash] = attrs.Factory(set)

    # # Initialization

    def __attrs_post_init__(self):

        # Get the active registry from context if none was provided
        self.registry = SombreroRegistry.active() or self.registry

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
        - Messages from bound modules are now tagged "bound" (should listen)

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
        Automatically bind this module to new modules

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

        ```python
        # Manual method
        camera.find(SombreroSettings)

        # Automatic property method
        SombreroModule.broken_extend("settings", SombreroSettings)
        camera.settings
        """
        BrokenUtils.extend(SombreroModule, name=name, as_property=True)(
            lambda self: self.find(type=type)
        )

    # # Messaging

    def relay(self, message: SombreroMessage) -> Self:
        """Relay a message to all modules on the registry

        Args:
            message (SombreroMessage): Some message payload from SombreroMessage

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
            hash (Hash): Hash of the module that sent the message
            bound (bool): Does this module should listen to the sender? (is bound?)
            message (SombreroMessage): Some message payload from SombreroMessage
        """
        if bound:
            log.warning(f"({self.short_hash}) Unhandled message from component ({hash}): {message}")

    # # SombreroGL Specific methods

    def update(self, time: float, dt: float) -> None:
        """
        Called every frame for updating internal states, interpolation

        Args:
            time (float): Time since the start of the shader
            dt (float): Time in seconds since the last frame

        Returns:
            None: Nothing
        """
        pass

    @property
    def pipeline(self) -> dict[str, Any]:
        """
        Get the state of this module to be piped to the shader
        """
        return {}

# -------------------------------------------------------------------------------------------------|

class SombreroBackend(BrokenEnum):
    Headless = "headless"
    GLFW     = "glfw"

class SombreroQuality(BrokenEnum):
    """
    Quality levels for Sombrero, generally speaking
    • Not all shaders or objects might react to this setting
    • "Final" quality level is meant for final renders
    """
    Low    = 0
    Medium = 1
    High   = 2
    Ultra  = 3
    Final  = 4

@attrs.define
class SombreroSettings(SombreroModule):

    time:   float = 0
    width:  int   = 1920
    height: int   = 1080
    fps:    float = 60
    msaa:   int   = 1
    ssaa:   int   = 1

    # # Quality

    __quality__: SombreroQuality = SombreroQuality.High

    @property
    def quality(self) -> int:
        return self.__quality__.value

    @quality.setter
    def quality(self, option: int | SombreroQuality) -> None:
        self.__quality__ = SombreroQuality.smart(option)

    # # Resolution

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height

    @resolution.setter
    def resolution(self, value: tuple[int, int]) -> None:
        self.width, self.height = value

    # # Window backend

    backend: SombreroBackend = SombreroBackend.GLFW
    title:   str             = "Sombrero"

    # # Messages, pipeline

    def update(self, time: float, dt: float) -> None:
        self.time += dt

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Window.Resize):
            self.resolution = (message.width, message.height)

    def pipeline(self) -> dict[str, Any]:
        return dict(
            resolution=self.resolution,
        )

# Access a bound SombreroSettings with a .settings property
SombreroModule.broken_extend("settings", SombreroSettings)

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroMouse(SombreroModule):
    def action(self):
        self.relay(SombreroMessage.Mouse.Position(x=1, y=2))
        log.info(f"Mouse got settings: {self.settings}")

# Access a bound SombreroMouse with a .mouse property
SombreroModule.broken_extend("mouse", SombreroMouse)

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroCamera(SombreroModule):
    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage) -> None:
        if not bound: return

        if isinstance(message, SombreroMessage.Mouse.Position):
            print(f"Camera got mouse position: {message}")

# Access a bound SombreroCamera with a .camera property
SombreroModule.broken_extend("camera", SombreroCamera)

# -------------------------------------------------------------------------------------------------|

@attrs.define
class ShaderVariable:
    ...

@attrs.define
class SombreroShader(SombreroModule):

    # # Variables

    # # Core content

    __vertex__:   str = None
    __fragment__: str = None

    @property
    def vertex(self) -> str:
        return self.__vertex__

    @vertex.setter
    def vertex(self, value: str) -> None:
        self.__vertex__ = value

    @property
    def fragment(self) -> str:
        return self.__fragment__

    @fragment.setter
    def fragment(self, value: str) -> None:
        self.__fragment__ = value

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroScene(SombreroModule):

    # Smart Constant Frame Rate class
    vsync: BrokenVsync = attrs.Factory(BrokenVsync)

    # Internal state
    __quit__: bool = False

    def __attrs_post_init__(self):

        # Register self (Scene)' on Register, as the Scene's register is the main one
        self.registry.register(self)

        # Create base modules
        with self.registry:
            SombreroSettings().auto_bind()
            SombreroMouse().auto_bind()
            SombreroCamera().auto_bind()

        # Setup scene
        self.setup()

        # Create Vsync client
        self.vsync.new(self.__update__, dt=True, frequency=self.settings.fps)

        # Start loop
        self.loop()

    # # Loop wise

    def __update__(self, dt: float):
        self.registry.update(time=self.settings.time, dt=dt)

    def quit(self) -> None:
        self.__quit__ = True

    def loop(self) -> None:
        while not self.__quit__:
            self.vsync.next()

    # # User defined methods

    @abstractmethod
    def setup(self) -> None:
        """Let the user configure the scene"""
        ...

    @abstractmethod
    def update(self, time: float, dt: float) -> None:
        """
        Let the user change variables over time
        - time: Time in seconds since the start of the video
        - dt:   Time in seconds since the last frame
        """
        ...

# -------------------------------------------------------------------------------------------------|

class UserScene(SombreroScene):
    def setup(self):
        self.settings.fps = 10
        ...

    def update(self, time: float, dt: float):
        log.info(f"Time: {time:.3f}s {dt:.6f}")
        self.mouse.action()

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        # log.info(f"Message: {hash} {message}")
        ...

scene = UserScene()


log.info(f"ShaderFlow Alive")

# registry = SombreroRegistry()

# with registry:
#     settings = SombreroSettings().auto_bind()
#     mouse    = SombreroMouse().auto_bind()
#     camera   = Camera().auto_bind()
#     mouse.action()