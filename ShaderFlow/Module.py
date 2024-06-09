from __future__ import annotations

import itertools
from abc import abstractmethod
from typing import TYPE_CHECKING, Iterable, Self, Type, Union

from attr import Factory, define, field

from Broken import BrokenAttrs, BrokenFluentBuilder, log
from Broken.Externals.FFmpeg import BrokenFFmpeg
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Variable import ShaderVariable


@define
class ShaderModule(BrokenFluentBuilder, BrokenAttrs):
    scene: ShaderScene = field(default=None, repr=False)
    name:  str = "Unknown"
    uuid:  int = Factory(itertools.count(1).__next__)

    @property
    def who(self) -> str:
        return f"({self.uuid:>2}) {type(self).__name__[:18].ljust(18)} │ ▸"

    def __post__(self):
        from ShaderFlow.Scene import ShaderScene

        # The module can be a ShaderScene itself
        self.scene = self.scene or self

        # Module must be part of a 'scene=instance(ShaderScene)'
        if not isinstance(self.scene, ShaderScene):
            log.error('\n'.join((
                f"Module of type '{type(self).__name__}' must be added to a 'ShaderScene' instance",
                f"• Initialize it with {type(self).__name__}(scene='instance(ShaderScene)', ...)",
            )))
            exit(0)

        log.trace(f"{self.who} Module added to the Scene")
        self.scene.modules.append(self)
        self.commands()

    @abstractmethod
    def commands(self) -> None:
        """Add commands to the scene with self.scene.broken_typer.command(...)"""
        ...

    # # Messaging

    def relay(self, message: Union[ShaderMessage, Type[ShaderMessage]]) -> Self:
        """Send a ShaderMessage to all modules in the scene. Handle it with self.handle(message)"""
        if isinstance(message, type):
            message = message()
        for module in self.scene.modules:
            module.handle(message)
        return self

    @abstractmethod
    def handle(self, message: ShaderMessage) -> None:
        ...

    def find(self, type: Type[ShaderModule]) -> Iterable[ShaderModule]:
        for module in self.scene.modules:
            if isinstance(module, type):
                yield module

    @property
    @abstractmethod
    def duration(self) -> float:
        """Self-report 'time to render' until completion"""
        return 0.0

    @abstractmethod
    def build(self) -> None:
        pass

    @abstractmethod
    def setup(self) -> None:
        pass

    @abstractmethod
    def update(self) -> None:
        pass

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        return []

    # ------------------------------------------|
    # Stuff pending a remaster

    def __process_include__(self, include: str) -> str:
        return include.format({f"${k}": v for k, v in vars(self).items()})

    @abstractmethod
    def includes(self) -> Iterable[str]:
        yield ""

    @abstractmethod
    def defines(self) -> Iterable[str]:
        yield None

    @abstractmethod
    def ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        pass

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

# Avoid circular reference on Module importing partial Scene
if TYPE_CHECKING:
    from ShaderFlow.Scene import ShaderScene
