from __future__ import annotations

from . import *


@define
class Module(BrokenFluentBuilder, BrokenAttrs):
    scene: Scene = Field(default=None, repr=False)
    name:  str   = "Unknown"
    uuid:  int   = Factory(itertools.count(1).__next__)

    def __post__(self):
        self.scene = self.scene or self
        self.scene.modules.append(self)
        log.info(f"{self.who} Module added to the Scene")

    @property
    def who(self) -> str:
        return f"({self.uuid:>2}) [{{color}}]{type(self).__name__[:18].ljust(18)}[/{{color}}] │ ▸"

    def find(self, type: Type[Module]) -> Iterable[Module]:
        for module in self.scene.modules:
            if isinstance(module, type):
                yield module

    @staticmethod
    def make_findable(type: Module) -> None:
        name = type.__name__.lower()
        BrokenUtils.extend(Module, name=name, as_property=True)(
            lambda self: next(self.find(type=type))
        )

    # # Messaging

    def relay(self, message: Union[Message, Type[Message]]) -> Self:
        if isinstance(message, type):
            message = message()
        for module in self.scene.modules:
            module.handle(message)
        return self

    # ------------------------------------------|

    # # Shader definitions

    def __process_include__(self, include: str) -> str:
        return include.format({f"${k}": v for k, v in vars(self).items()})

    @abstractmethod
    def includes(self) -> Iterable[str]:
        yield ""

    @abstractmethod
    def defines(self) -> Iterable[str]:
        yield None

    # ------------------------------------------|

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
    def handle(self, message: Message) -> None:
        pass

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        return []

    @abstractmethod
    def ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        pass

    # ------------------------------------------|

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
