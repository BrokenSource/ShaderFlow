from . import *


@attrs.define
class SombreroScene(SombreroModule):
    modules: dict[SombreroHash, SombreroModule] = attrs.field(factory=dict)

    # Base classes and utils for a Scene
    vsync:    BrokenVsync       = attrs.field(factory=BrokenVsync)
    client:   BrokenVsyncClient = None
    ffmpeg:   BrokenFFmpeg      = attrs.field(factory=BrokenFFmpeg)

    # Internal state
    __quit__: bool = False

    def __attrs_post_init__(self):
        SombreroContext(scene=self)
        self.scene = self
        self.setup()

    def __add__(self, *modules: SombreroModule | Iterable[SombreroModule]) -> None:
        """Add modules to the scene. Automatically called on module creation"""
        for module in BrokenUtils.flatten(modules):
            log.debug(f"Registering module ({module.hash}) ({module.__class__.__name__})")
            self.modules[module.hash] = module

    # # Messages

    def relay(self, hash: SombreroHash, message: SombreroMessage) -> Self:
        """
        Relay a message to all modules on the scene

        Args:
            hash: Hash of the module that sent the message
            message: Some SombreroMessage instance and its payload

        Returns:
            Self: Fluent interface
        """
        for module in self.modules.values():
            module.on_message(hash=hash, bound=True, message=message)
        return self

    # # Loop wise

    def __update__(self, dt: float):

        # Update modules
        for module in self.modules.values():
            module.update(time=self.context.time, dt=dt)

        # Render scene
        # self.sombrero.render()
        # self.context.window.swap_buffers()

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
        log.info(f"Quitting Scene [{self.__class__.__name__}]")
        self.__quit__ = True

    def loop(self) -> None:
        """
        Start the scene main loop, which will call the update method every vsync

        Returns:
            None: Code stays on loop until quit is called
        """

        # Create Vsync client
        self.client = self.vsync.new(self.__update__, dt=True, frequency=self.context.fps)

        while not self.__quit__:
            self.vsync.next()

    # # User defined methods

    @abstractmethod
    def setup(self) -> None:
        """Let the user configure the scene"""
        log.warning(f"Scene ({self.__class__.__name__}) has no setup method")

    @abstractmethod
    def update(self, time: float, dt: float) -> None:
        """
        Let the user change variables over time

        Args:
            time: Time in seconds since the start of the video
            dt:   Time in seconds since the last frame

        Returns:
            None: Shouldn't, as the Scene does nothing with the return
        """
        ...
