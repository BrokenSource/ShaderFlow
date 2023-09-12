from . import *


@attrs.define
class SombreroScene(SombreroModule):

    # Smart Constant Frame Rate class
    vsync: BrokenVsync = attrs.Factory(BrokenVsync)

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

        # Setup scene
        self.setup()

    # # Loop wise

    def __update__(self, dt: float):
        self.registry.update(time=self.context.time, dt=dt)

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
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
        ...

    @abstractmethod
    def update(self, time: float, dt: float) -> None:
        """
        Let the user change variables over time
        - time: Time in seconds since the start of the video
        - dt:   Time in seconds since the last frame
        """
        ...
