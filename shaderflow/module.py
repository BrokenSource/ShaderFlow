from __future__ import annotations

import itertools
import weakref
from abc import abstractmethod
from typing import TYPE_CHECKING, Iterable, Self, Union
from weakref import CallableProxyType, ProxyType

from attrs import Factory, define, field

from shaderflow import logger
from shaderflow.message import ShaderMessage
from shaderflow.variable import ShaderVariable

if TYPE_CHECKING:
    from shaderflow.ffmpeg import FFmpeg
    from shaderflow.scene import ShaderScene

@define(slots=False)
class ShaderModule:

    scene: ShaderScene = field(default=None, repr=False)
    """The ShaderScene this module belongs to. Must be set on initialization of any module with
    `ShaderModule(scene=...)` (even though it's `default=None` for MRO reasons)"""

    uuid: int = Factory(itertools.count(1).__next__)
    """A module identifier, mostly used for differentiating log statements of same type modules"""

    name: str = None
    """The base name for exported GLSL variables, textures, etc. It is technically optional, but
    it's not a bad idea for all modules to have a default value for this attribute than None"""

    def __attrs_post_init__(self):

        # Post-import to avoid circular reference for type checking
        from shaderflow.scene import ShaderScene

        # The first module initialized is the Scene itself
        if not isinstance(self.scene or self, (CallableProxyType, ProxyType)):
            self.scene = weakref.proxy(self.scene or self)

        # Module must be part of a scene
        if not isinstance(self.scene, ShaderScene):
            raise RuntimeError(logger.error('\n'.join((
                f"Module of type '{type(self).__name__}' must be added to a 'ShaderScene' instance",
                f"• Initialize it with {type(self).__name__}(scene='instance(ShaderScene)', ...)",
            ))))

        self.scene.modules.append(self)
        self.commands()

        if not isinstance(self, ShaderScene):
            self.build()

    @abstractmethod
    def build(self) -> None:
        """Only ever called once on a scene initialization"""
        pass

    @abstractmethod
    def setup(self) -> None:
        """Called every time before the main event loop"""
        pass

    @abstractmethod
    def update(self) -> None:
        """Called every frame in the event loop"""
        pass

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        return []

    def full_pipeline(self) -> Iterable[ShaderVariable]:
        """Yield all pipelines from all modules in the scene"""
        for module in self.scene.modules:
            yield from module.pipeline()

    def relay(self, message: Union[ShaderMessage, type[ShaderMessage]]) -> Self:
        """Send a message to all modules in the scene"""
        if isinstance(message, type):
            message = message()
        for module in self.scene.modules:
            module.handle(message)
        return self

    @abstractmethod
    def handle(self, message: ShaderMessage) -> None:
        """Handle a message sent by some module in the scene"""
        ...

    def find(self, type: type[ShaderModule]) -> Iterable[ShaderModule]:
        """Find all modules of a certain type in the scene"""
        for module in self.scene.modules:
            if isinstance(module, type):
                yield module

    @property
    @abstractmethod
    def duration(self) -> float:
        """Self-reported time for full completion"""
        return 0.0

    @abstractmethod
    def ffhook(self, ffmpeg: FFmpeg) -> None:
        pass

    @abstractmethod
    def commands(self) -> None:
        """Add commands to the scene with `self.scene.cli.command(...)`"""
        ...

    @abstractmethod
    def destroy(self) -> None:
        """Similar to __del__, potentially intentional, but automatic when the Scene is gc'd"""
        pass

    def __del__(self) -> None:
        self.destroy()

    # -------------------------------------------|
    # Logging

    @property
    def who(self) -> str:
        return f"[bold dim](Module {self.uuid:>2} • {type(self).__name__[:12].ljust(12)})[/]"

    def log_info(self, *args, **kwargs) -> str:
        return logger.info(self.who, *args, **kwargs)

    def log_warn(self, *args, **kwargs) -> str:
        return logger.warn(self.who, *args, **kwargs)

    def log_error(self, *args, **kwargs) -> str:
        return logger.error(self.who, *args, **kwargs)

    def log_debug(self, *args, **kwargs) -> str:
        return logger.debug(self.who, *args, **kwargs)

    def log_minor(self, *args, **kwargs) -> str:
        return logger.minor(self.who, *args, **kwargs)

    # -------------------------------------------|
    # Stuff pending a remaster

    @abstractmethod
    def includes(self) -> Iterable[dict[str, str]]:
        yield ""

    @abstractmethod
    def defines(self) -> Iterable[str]:
        yield None

    # # User interface

    def __shaderflow_ui__(self) -> None:
        """Basic info of a Module"""
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
