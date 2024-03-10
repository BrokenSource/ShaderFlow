from __future__ import annotations

from . import *


@define
class ShaderFlowModule(BrokenFluentBuilder):
    name:  str = "Unknown"
    scene: ShaderFlowScene = None
    uuid:  int = Factory(itertools.count(1).__next__)

    @property
    def who(self) -> str:
        """Basic module information of UUID and Class Name"""
        return f"({self.uuid:>2}) [{{color}}]{type(self).__name__[:18].ljust(18)}[/{{color}}] │ ▸"

    def add(self, module: ShaderFlowModule | Type[ShaderFlowModule], **kwargs) -> ShaderFlowModule:
        return self.scene.register(module, **kwargs)

    def find(self, type: Type[ShaderFlowModule]) -> Iterable[ShaderFlowModule]:
        for module in self.scene.modules:
            if isinstance(module, type):
                yield module

    @staticmethod
    def make_findable(type: Type) -> None:
        """
        # Manual method
        context = module.find(ShaderFlowContext)

        # Automatic property method
        ShaderFlowModule.make_findable(ShaderFlowContext)
        context = module.context
        """
        name = type.__name__.lower().removeprefix("shaderflow")
        BrokenUtils.extend(ShaderFlowModule, name=name, as_property=True)(
            lambda self: next(self.find(type=type))
        )

    # # Messaging

    def relay(self, message: Union[ShaderFlowMessage, Type[ShaderFlowMessage]]) -> Self:
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
    def handle(self, message: ShaderFlowMessage) -> None:
        pass

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        return []

    def _full_pipeline(self) -> Iterable[ShaderVariable]:
        for module in self.scene.modules:
            yield from module.pipeline()

    @abstractmethod
    def ffmpeg(self, ffmpeg: BrokenFFmpeg) -> None:
        pass

    # ------------------------------------------|

    # # User interface

    def __shaderflow_ui__(self) -> None:
        """Basic info of a ShaderFlowModule"""
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
