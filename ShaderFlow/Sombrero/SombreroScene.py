from . import *


@attrs.define
class SombreroScene(SombreroModule):

    # Base classes and utils for a Scene
    vsync:    BrokenVsync  = attrs.field(factory=BrokenVsync)
    ffmpeg:   BrokenFFmpeg = attrs.field(factory=BrokenFFmpeg)
    sombrero: Sombrero     = None

    # Internal state
    __quit__: bool = False

    def __attrs_post_init__(self):

        # Create base modules
        with self.registry:
            SombreroContext().auto_bind()
            SombreroWindow().auto_bind()
            SombreroMouse().auto_bind()
            SombreroCamera().auto_bind()

            self.window.create_window()

            # Create main Sombrero
            self.sombrero = Sombrero()
            self.sombrero.render_to_window()

        # Register self (Scene)' on Register, as the Scene's register is the main one
        self.registry.register(self)

        # Setup scene
        with self.registry:
            self.setup()
        self.sombrero.load_shaders()

    # # Loop wise

    def __update__(self, dt: float):
        self.registry.update(time=self.context.time, dt=dt)
        self.sombrero.render()
        self.context.window.swap_buffers()

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

    # # Debug, internal

    def __print_pipeline__(self):
        log.trace(f"Pipeline:")
        for var in self.sombrero.pipeline:
            log.trace(f"· {str(var.name).ljust(16)}: {var.value}")

# -------------------------------------------------------------------------------------------------|

@attrs.define
class SombreroSceneSecondOrderSystem(SombreroModule):
    name: str = None
    system: BrokenSecondOrderDynamics = None

    def __init__(self, value: float=None, frequency: float=1, zeta: float=1, response: float=0, *args, **kwargs):
        self.__attrs_init__(*args, **kwargs)
        self.system = BrokenSecondOrderDynamics(value=value, frequency=frequency, zeta=zeta, response=response)

    @property
    def pipeline(self) -> list[ShaderVariable]:
        return [
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.name}",          value=self.system.value   ),
            ShaderVariable(qualifier="uniform", type="float", name=f"{self.name}_integral", value=self.system.integral),
        ]

    def update(self, time: float, dt: float) -> Any:
        return self.system.update(dt=dt)

