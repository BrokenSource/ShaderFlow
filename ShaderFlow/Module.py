from __future__ import annotations

import itertools
from abc import abstractmethod
from typing import TYPE_CHECKING, Iterable, Self, Union

from attr import Factory, define, field

from Broken import BrokenAttrs, BrokenFluent, log, smartproxy
from ShaderFlow.Message import ShaderMessage
from ShaderFlow.Variable import ShaderVariable

if TYPE_CHECKING:
    from Broken.Externals.FFmpeg import BrokenFFmpeg
    from ShaderFlow.Scene import ShaderScene


@define
class ShaderModule(BrokenFluent, BrokenAttrs):

    scene: ShaderScene = field(default=None, repr=False)
    """The ShaderScene this module belongs to. Must be set on initialization of any module with
    `ShaderModule(scene=...)` (even though it's `default=None` for MRO reasons)"""

    uuid: int = Factory(itertools.count(1).__next__)
    """A module identifier, mostly used for differentiating log statements of same type modules"""

    name: str = None
    """The base name for exported GLSL variables, textures, etc. It is technically optional, but
    it's not a bad idea for all modules to have a default value for this attribute than None"""

    def __post__(self):

        # Post-import to avoid circular reference for type checking
        from ShaderFlow.Scene import ShaderScene

        # The first module initialized is the Scene itself
        self.scene = smartproxy(self.scene or self)

        # Module must be part of a 'scene=instance(ShaderScene)'
        if not isinstance(self.scene, ShaderScene):
            raise RuntimeError(log.error('\n'.join((
                f"Module of type '{type(self).__name__}' must be added to a 'ShaderScene' instance",
                f"• Initialize it with {type(self).__name__}(scene='instance(ShaderScene)', ...)",
            ))))

        self.log_debug("Module added to the Scene")
        self.scene.modules.append(self)
        self.commands()

        if not isinstance(self, ShaderScene):
            self.build()

    def __del__(self) -> None:
        self.destroy()

    @abstractmethod
    def destroy(self) -> None:
        """Similar to __del__, potentially intentional, but automatic when the Scene is gc'd"""
        pass

    @abstractmethod
    def build(self) -> None:
        """Create Textures, child ShaderModules, load base shaders, etc. Happens only once, and it's
        a good place to set default values for attributes, such as a background image that can be
        later changed on `self.setup()` or, better yet, on the CLI of the module/custom Scene"""
        pass

    @abstractmethod
    def setup(self) -> None:
        """Called every time before the initialization (rendering) of the Scene. Useful for managing
        the behavior of batch exporting per export index; also a good place to reset values to their
        defaults or create procedural objects (seeds) after `self.build()`"""
        pass

    @abstractmethod
    def update(self) -> None:
        """Called every frame. This defines the main behavior of the module inside the event loop.
        All non-ShaderObjects are called first, then regular Modules. Access state data directly
        on the Scene with `self.scene.{dt,time,width,height,...}`"""
        pass

    @abstractmethod
    def pipeline(self) -> Iterable[ShaderVariable]:
        """Returns the list of variables that will be exported to all Shaders of the scene. The
        first compilation happens after `self.build()`, where all variables are metaprogrammed into
        the GLSL code. Subsequent calls happens after all `self.update()` on every frame and the
        variables are updated to the yielded values here"""
        return []

    def full_pipeline(self) -> Iterable[ShaderVariable]:
        """Yield all pipelines from all modules in the scene"""
        for module in self.scene.modules:
            yield from module.pipeline()

    def relay(self, message: Union[ShaderMessage, type[ShaderMessage]]) -> Self:
        """Send a message to all modules in the scene. Handle it defining a `self.handle(message)`"""
        if isinstance(message, type):
            message = message()
        for module in self.scene.modules:
            module.handle(message)
        return self

    @abstractmethod
    def handle(self, message: ShaderMessage) -> None:
        """Whenever a module relays a message on the scene, all modules are signaled via this method
        for potentially acting on it. A Camera might move on WASD keys, for example"""
        ...

    def find(self, type: type[ShaderModule]) -> Iterable[ShaderModule]:
        """Find all modules of a certain type in the scene. Note that this function is a generator,
        so it must be consumed on a loop or a `list(self.find(...))`"""
        for module in self.scene.modules:
            if isinstance(module, type):
                yield module

    @property
    @abstractmethod
    def duration(self) -> float:
        """Self-reported 'time for completion'. A ShaderAudio shall return the input audio duration,
        for example. The scene will determine or override the final duration"""
        return 0.0

    @abstractmethod
    def ffhook(self, ffmpeg: BrokenFFmpeg) -> None:
        """When exporting the Scene, after the initial CLI configuration of FFmpeg by the Scene's
        `self.main` method, all modules have an option to change the FFmpeg settings on the fly.
        Note that this can also be implemented on a custom Scene itself, and behavior _can_ be
        changed per batch exporting"""
        pass

    @abstractmethod
    def commands(self) -> None:
        """Add commands to the scene with `self.scene.cli.command(...)`"""
        ...

    # -------------------------------------------|
    # Logging

    @property
    def panel_module_type(self) -> str:
        """Suggested typer panel for identifying this module type"""
        return f"→ (Module) {type(self).__name__}"

    @property
    def panel_module_self(self) -> str:
        """Suggested typer panel for identifying this unique module"""
        return f"{self.panel_module_type}: {self.name or 'Unnamed'}"

    @property
    def who(self) -> str:
        return f"[bold dim](Module {self.uuid:>2} • {type(self).__name__[:12].ljust(12)})[/]"

    def log_info(self, *args, **kwargs) -> str:
        return log.info(self.who, *args, **kwargs)

    def log_success(self, *args, **kwargs) -> str:
        return log.success(self.who, *args, **kwargs)

    def log_warning(self, *args, **kwargs) -> str:
        return log.warning(self.who, *args, **kwargs)

    def log_error(self, *args, **kwargs) -> str:
        return log.error(self.who, *args, **kwargs)

    def log_debug(self, *args, **kwargs) -> str:
        return log.debug(self.who, *args, **kwargs)

    def log_minor(self, *args, **kwargs) -> str:
        return log.minor(self.who, *args, **kwargs)

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
