from __future__ import annotations

from Broken import *

# -------------------------------------------------------------------------------------------------|

class SombreroMessage:

    # # Special

    class Any:
        """Any data type"""
        data: Any

    # # Mouse

    class Mouse:

        @attrs.define
        class Position:
            x: int = None
            y: int = None
            dx: int = None
            dy: int = None

        @attrs.define
        class Press:
            x: int = None
            y: int = None
            button: int = None

        @attrs.define
        class Release:
            x: int = None
            y: int = None
            button: int = None

        @attrs.define
        class Drag:
            x: int = None
            y: int = None
            dx: int = None
            dy: int = None

        @attrs.define
        class Scroll:
            dx: int = None
            dy: int = None

    # # Window

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
    hash: SombreroHash = attrs.Factory(SombreroHash)

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
class SombreroContext(SombreroModule):
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
SombreroModule.broken_extend("context", SombreroContext)

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroMouse(SombreroModule):
    def action(self):
        self.relay(SombreroMessage.Mouse.Position(x=1, y=2))
        log.info(f"Mouse got context: {self.context}")

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
    """
    Metaprogramming class to define a shader variable

    "uniform vec2 resolution;"
    • qualifier: "uniform"
    • type:      "vec2"
    • name:      "resolution"
    • default:   Any
    • interpolation: "flat", "smooth", "noperspective"
    """
    parameter: str = "uniform"
    type:      str = None
    name:      str = None
    default:   str = None
    interpolation: str = ""

    def __hash__(self):
        return self

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
            SombreroContext().auto_bind()
            SombreroMouse().auto_bind()
            SombreroCamera().auto_bind()

        # Create Vsync client
        self.vsync.new(self.__update__, dt=True, frequency=self.context.fps)

        # Setup scene
        self.setup()

    # # Loop wise

    def __update__(self, dt: float):
        self.registry.update(time=self.context.time, dt=dt)

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
        self.context.fps = 10
        self.mouse.action()

    def update(self, time: float, dt: float):
        log.info(f"Time: {time:.5f}s {dt:.6f}")

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        # log.info(f"Message: {hash} {message}")
        ...

log.info(f"ShaderFlow Alive")

scene = UserScene()
scene.loop()



# registry = SombreroRegistry()

# with registry:
#     settings = SombreroSettings().auto_bind()
#     mouse    = SombreroMouse().auto_bind()
#     camera   = Camera().auto_bind()
#     mouse.action()