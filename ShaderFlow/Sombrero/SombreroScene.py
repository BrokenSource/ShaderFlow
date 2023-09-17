from . import *


@attrs.define
class SombreroScene(SombreroModule):

    # Smart Constant Frame Rate class
    vsync: BrokenVsync = attrs.field(factory=BrokenVsync)
    sombrero: Sombrero = None

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

            # Create main Sombrero
            self.sombrero = Sombrero(registry)

        # Setup scene
        self.setup()
        self.sombrero.load_shaders()

    # # Loop wise

    def __update__(self, dt: float):
        self.registry.update(time=self.context.time, dt=dt)
        self.sombrero.render()

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
        log.info(f"Quitting Scene [{self.__class__.__name__}]")
        self.__quit__ = True

    def loop(self) -> None:
        """
        Start the scene main loop, which will call the update method every vsync
        """
        # Create Vsync client
        client = self.vsync.new(self.__update__, dt=True, frequency=self.context.fps)

        while not self.__quit__:
            self.vsync.next()

        del client

    # # User defined methods

    @abstractmethod
    def setup(self) -> None:
        """
        Let the user configure the scene
        """
        log.warning(f"Scene [{self.__class__.__name__}] has no setup method")

    @abstractmethod
    def update(self, time: float, dt: float) -> None:
        """
        Let the user change variables over time
        - time: Time in seconds since the start of the video
        - dt:   Time in seconds since the last frame
        """
        ...
