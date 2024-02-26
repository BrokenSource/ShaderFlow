from __future__ import annotations

from . import *

SombreroID: TypeAlias = int


@define
class SombreroModule(BrokenFluentBuilder):
    name:  str           = "Unknown"
    scene: SombreroScene = None
    uuid:  SombreroID    = Factory(itertools.count(1).__next__)

    @property
    def who(self) -> str:
        """Basic module information of UUID and Class Name"""
        return f"│{self.uuid:>2}├┤{type(self).__name__[:16].ljust(16)}│"

    def add(self, module: SombreroModule | Type[SombreroModule], **kwargs) -> SombreroModule:
        return self.scene.register(module, **kwargs)

    def find(self, type: Type[SombreroModule]) -> Generator[SombreroModule]:
        for module in self.scene.modules:
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

        # Instantiate class references, usually data-less messages
        if isinstance(message, type):
            message = message()

        for module in self.scene.modules:
            module._handle(message)

        return self

    # ------------------------------------------|

    # # Shader definitions

    def __process_include__(self, include: str) -> str:
        return include.format({f"${k}": v for k, v in vars(self).items()})

    @abstractmethod
    def includes(self) -> Iterable[str]:
        yield ""

    # ------------------------------------------|

    """
    The methods below implements a dunder, sunder and.. nunder? for different reasons. Example Usage:
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

    # # Initialization

    # # Build

    @abstractmethod
    def __build__(self) -> None:
        """Sombrero's Internal method for self.build"""
        pass

    @abstractmethod
    def _build_(self) -> None:
        """Module's Internal method for self.build"""
        pass

    @abstractmethod
    def build(self) -> None:
        """User's Method for building the module"""
        pass

    def _build(self) -> None:
        """Call all build methods"""
        self.__build__()
        self._build_()
        self.build()

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

        Returns:
            Iterable of ShaderVariables
        """
        return []

    def _pipeline(self) -> Iterable[ShaderVariable]:
        """Internal call all pipeline methods"""
        yield from self.__pipeline__() or []
        yield from self._pipeline_() or []
        yield from self.pipeline() or []

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

    # # FFmpeg

    @abstractmethod
    def __ffmpeg__(self, ffmpeg: BrokenFFmpeg) -> None:
        """Sombrero's Internal method for self.ffmpeg"""
        pass

    @abstractmethod
    def _ffmpeg_(self, ffmpeg: BrokenFFmpeg) -> None:
        """Module's Internal method for self.ffmpeg"""
        pass

    @abstractmethod
    def ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        """User's Method for configuring the ffmpeg"""
        pass

    def _ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        """Internal call all ffmpeg methods"""
        self.__ffmpeg__(ffmpeg)
        self._ffmpeg_(ffmpeg)
        self.ffmpeg(ffmpeg)

    # ------------------------------------------|

    # # User interface

    def __sombrero_ui__(self) -> None:
        """Basic info of a SombreroModule"""
        # Todo: Make automatic Imgui methods

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
