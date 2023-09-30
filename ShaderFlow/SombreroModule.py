from __future__ import annotations

from . import *


@attrs.define
class SombreroModule:
    """
    A Base class that defines a Sombrero module. It's quite hard to explain and keep it short,
    please do see the implementation documentation itself
    """

    # Scene this module belongs to
    scene: SombreroScene = None

    # Unique identification of this module
    hash: SombreroHash = attrs.field(factory=SombreroHash, converter=str)

    # A prefix to be added before variable names, defaults to "iTime", "iResolution", etc
    prefix: str = "i"

    def __attrs_post_init__(self):
        self.scene.__add__(self)
        self.setup()

    def setup(self) -> None:
        """
        Let the module configure itself, called ater the module is added to the scene
        For example, a Keyboard module might subscribe to window events here
        """
        pass

    # # Find modules wise

    def find(self, type: Type[SombreroModule], all: bool=False) -> SombreroModule | list[SombreroModule] | None:
        """
        Find some scene module of a given type

        Args:
            type: The type of the module to find
            all: List of all modules of the given type or first one if any

        Returns:
            SombreroModule | None: The module (list if all else instance) or None if not found
        """
        list = []
        for module in self.scene.modules.values():
            if isinstance(module, type):
                if not all: return module
                list.append(module)
        return list or None

    @staticmethod
    def make_findable(type: Type) -> None:
        """
        Add a property to all SombreroModule that finds a module of a given type easily
        It's better explained in code:

        ```python
        # Manual method
        context = scene.find(SombreroContext)

        # Automatic property method
        SombreroModule.make_findable(SombreroContext)
        context = camera.context
        ```
        """
        name = type.__name__.lower().removeprefix("sombrero")
        BrokenUtils.extend(SombreroModule, name=name, as_property=True)(
            lambda self: self.find(type=type)
        )

    # # Messaging

    def relay(self, message: SombreroMessage) -> Self:
        """
        Relay a message to all modules on the scene

        Args:
            message: Some SombreroMessage instance and its payload

        Returns:
            Self: Fluent interface
        """
        self.scene.relay(hash=self.hash, message=message)
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
        if not bound: return
        log.warning(f"({self.__class__.__name__} @ {self.short_hash}) Unhandled message from bound component ({hash}): {message}")

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
    def pipeline(self) -> list[ShaderVariable]:
        """
        Get the state of this module to be piped to the shader
        As a side effect, also the variable definitions and default values
        Note: Variable names should start with self.prefix

        Returns:
            list[ShaderVariable]: List of variables and their states
        """
        return []
