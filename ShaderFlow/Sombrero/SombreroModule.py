from __future__ import annotations

from . import *


# Identifier for modules
class __SombreroID__:
    Counter = 0

    def next() -> int:
        __SombreroID__.Counter += 1
        return __SombreroID__.Counter

SombreroID = __SombreroID__.next


@define
class SombreroModule(BrokenFluentBuilder):
    scene: SombreroScene = None

    # Note: A prefix for variable names - "iTime", "rResolution", etc
    prefix: str = "i"

    # # Module hierarchy and identification
    uuid:              SombreroID  = Factory(SombreroID)
    __weak__:      Set[SombreroID] = Factory(set)
    __group__:     Set[SombreroID] = Factory(set)
    __children__:  Set[SombreroID] = Factory(set)
    __connected__: Set[SombreroID] = Factory(set)
    __parent__:        SombreroID  = None

    @property
    def who(self) -> str:
        """Basic module information of UUID and Class Name"""
        return f"│{self.uuid:>2}├┤{type(self).__name__[:16].ljust(16)}│"

    # # Hierarchy methods

    @property
    def weak(self) -> Generator[SombreroModule]:
        """List of the modules in the 'weak' group of this module"""
        yield from map(self.scene.modules.get, self.__weak__)

    @property
    def group(self) -> Generator[SombreroModule]:
        """List of the modules in the 'super node' group of this module"""
        yield from map(self.scene.modules.get, self.__group__)

    @property
    def children(self) -> Generator[SombreroModule]:
        """List of the children of this module"""
        yield from map(self.scene.modules.get, self.__children__)

    @property
    def connected(self) -> Generator[SombreroModule]:
        """List of the modules related to this module"""
        yield from map(self.scene.modules.get, self.__connected__)

    @property
    def parent(self) -> SombreroModule | None:
        """Parent module of this module"""
        return self.scene.modules.get(self.__parent__, None)

    # # Module manipulation

    def __attrs_post_init__(self) -> None:
        # Warn: Whenever inheriting with another post init, call this super's one
        self.__connected__.add(self.uuid)
        self.__group__.add(self.uuid)

    def child(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """
        Add a child to this module, becoming a parent, and starting a new super node

        > Copies the parent pipeline to the child

        - Useful for isolated modules on the Scene or rendering layers

        Args:
            module: The module to add

        Returns:
            SombreroModule: The added module
        """
        self.scene.register(module := module())
        self.__children__.add(module.uuid)
        module.__connected__.update(self.__connected__)
        module.__parent__ = self.uuid
        module._setup()
        return module

    def add(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """
        Note: Strongly connect a new module to the current super node - pipes recursively downstream

        > The implementation for updating the .__connected__ attribute is tricky, as it must avoid
        recursion and "propagate" to the current super node and all nodes down the hierarchy

        - Useful everywhere, as it avoids a child-only hierarchy

        Args:
            module: The module to add

        Returns:
            SombreroModule: The added module
        """
        self.scene.register(module := module())
        self.__group__.add(module.uuid)
        module.__connected__.update(self.__connected__)
        module.__parent__ = self.__parent__
        module.__group__  = self.__group__
        for other in self.group:
            other.__propagate__(module)
        module._setup()
        return module

    def __propagate__(self, module: SombreroModule) -> None:
        self.__connected__.add(module.uuid)
        for child in self.children:
            for other in child.group:
                other.__propagate__(module)

    def connect(self, module: SombreroModule | Type[SombreroModule]) -> SombreroModule:
        """
        Note: Weakly connect a new module to the current module - no recursive downstream piping

        - Useful when a module's pipeline is only intended to be used by selected modules

        Args:
            module: The module to add

        Returns:
            SombreroModule: The added module
        """
        self.scene.register(module := module())
        self.__connected__.add(module.uuid)
        module._setup()
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

    def find(self, type: Type[SombreroModule]) -> Generator[SombreroModule]:
        """
        Find modules of a given type in the scene

        Args:
            type: The type of the module to find

        Returns:
            Generator of modules of the given type
        """
        for module in self.scene.modules.values():
            if isinstance(module, type):
                yield module

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
            lambda self: next(self.find(type=type))
        )

    # # Messaging

    def relay(self, message: SombreroMessage, __received__: Set[SombreroID]=None) -> Self:
        """
        Relay a message to all related modules down the hierarchy

        Args:
            message: The message to relay

        Returns:
            Self: Fluent interface
        """

        # Instantiate class references, usually data-less messages
        if isinstance(message, type):
            message = message()

        # Python death trap - mutable default arguments
        __received__ = __received__ or set()

        # Skip if already received else register self
        if self.uuid in __received__:
            return
        __received__.add(self.uuid)

        # Handle the message
        self._handle(message)

        # Recurse down the hierarchy
        for module in itertools.chain(self.group, self.children):
            module.relay(message=message, __received__=__received__)

        return self

    # ------------------------------------------|

    # # Shader definitions

    def __process_include__(self, include: str) -> str:
        return include.format({f"${k}": v for k, v in vars(self).items()})

    @abstractmethod
    def includes(self) -> Dict[str, str]:
        """
        Get the includes for this module

        Returns:
            dict[str, str]: The includes for this module
        """
        return {}

    # ------------------------------------------|

    """
    The methods below implements a dunder, sunder and nunder for different reasons. Example Usage:
    • Dunder: Internal primitive methods, like the SombreroEngine recreating textures, "ring zero"
    • Sunder: A Scene creates its default modules here, they're custom, not part of Sombrero spec
    • Nunder: The user changes the module's behavior, or add their own

    This way, one can inherit from a Module and add extra custom behavior to it. The best example
    is from the DepthFlow project:

    ```python
    class DepthFlowScene(SombreroScene):
        def _setup_(self):
            self.image = self.engine.new_texture("image").repeat(False)
            self.depth = self.engine.new_texture("depth").repeat(False)

        def _handle_(self, message: SombreroMessage):
            if isinstance(message, SombreroMessage.Window.FileDrop):
                self.parallax(image=message.files[0], depth=message.files.get(1))
        ...


    class MyScene(DepthFlowScene):
        def setup(self):
            self.self.engine.add(...)

        def handle(self, message: SombreroMessage):
            if isinstance(message, SombreroMessage.Mouse.Position):
                ...
    ```

    Notice how the "DepthFlow" objects are decoupled-ly defined in the base project, and inheritance
    of the base class (or module) allows for custom behavior to be added. The internal __handle__
    is still there for SombreroScene. It is safe to say that these three levels is all one needs
    """

    # # Setup

    @abstractmethod
    def __setup__(self) -> None:
        """Sombrero's Internal method for self.setup"""
        pass

    @abstractmethod
    def _setup_(self) -> None:
        """Module's Base Internal method for self.setup"""
        pass

    @abstractmethod
    def setup(self) -> None:
        """User's Method for configuring the module"""
        pass

    def _setup(self) -> None:
        """Call all setup methods"""
        self.__setup__()
        self._setup_()
        self.setup()

    # # Updating

    @abstractmethod
    def __update__(self) -> None:
        """Sombrero's Internal method for self.update"""
        pass

    @abstractmethod
    def _update_(self) -> None:
        """Module's Internal method for self.update"""
        pass

    @abstractmethod
    def update(self) -> None:
        """User's Method for updating the module"""
        pass

    def _update(self) -> None:
        """Internal call all update methods"""
        self.__update__()
        self._update_()
        self.update()

    # # Pipeline

    @abstractmethod
    def __pipeline__(self) -> Iterable[ShaderVariable]:
        """Sombrero's Internal method for self.pipeline"""
        return []

    @abstractmethod
    def _pipeline_(self) -> Iterable[ShaderVariable]:
        """Module's Internal method for self.pipeline"""
        return []

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        """
        Get the state of this module to be piped to the shader
        As a side effect, also the variable definitions and default values
        Note: Variable names should start with self.prefix

        Returns:
            Iterable of ShaderVariables
        """
        return []

    def _pipeline(self) -> Iterable[ShaderVariable]:
        """Internal call all pipeline methods"""
        yield from self.__pipeline__() or []
        yield from self._pipeline_() or []
        yield from self.pipeline() or []

    def full_pipeline(self) -> Iterable[ShaderVariable]:
        """Full module's pipeline"""
        yield from self._pipeline()
        for module in self.connected:
            yield from module._pipeline()

    # # Messaging

    @abstractmethod
    def __handle__(self, message: SombreroMessage) -> None:
        """Sombrero's Internal method for self.handle"""
        pass

    @abstractmethod
    def _handle_(self, message: SombreroMessage) -> None:
        """Module's Internal method for self.handle"""
        pass

    @abstractmethod
    def handle(self, message: SombreroMessage) -> None:
        """
        Receive a message from any related module

        Args:
            message: The message received
        """
        pass

    def _handle(self, message: SombreroMessage) -> None:
        """Internal call all handle methods"""
        self.__handle__(message)
        self._handle_(message)
        self.handle(message)

    # ------------------------------------------|

    # # User interface

    def __sombrero_ui__(self) -> None:
        """Basic info of a SombreroModule"""
        # Todo: Make automatic Imgui methods

        # Hierarchy
        if imgui.tree_node("Hierarchy"):
            imgui.text(f"UUID:      {self.uuid}")
            imgui.text(f"Group:     {self.__group__}")
            imgui.text(f"Children:  {self.__children__}")
            imgui.text(f"Connected: {self.__connected__}")
            imgui.text(f"Parent:    {self.__parent__}")
            imgui.tree_pop()

        # Pipeline
        if pipeline := list(self.pipeline()):
            if imgui.tree_node("Pipeline"):
                for variable in pipeline:
                    imgui.text(f"{variable.name.ljust(16)}: {variable.value}")
                imgui.tree_pop()

        # Module - self.__ui__ must be implemented
        if not getattr(self.__ui__, "__isabstractmethod__", False):
            self.__ui__()

        # Module - self.ui must be implemented
        if not getattr(self.ui, "__isabstractmethod__", False):
            self.ui()

    @abstractmethod
    def __ui__(self) -> None:
        """Internal method for self.ui"""
        pass

    @abstractmethod
    def ui(self) -> None:
        """
        Draw the UI for this module
        """
        pass
