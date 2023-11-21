from . import *


@attrs.define
class SombreroScene(SombreroModule):
    modules: Dict[SombreroID, SombreroModule] = attrs.field(factory=dict)

    # Base classes and utils for a Scene
    ffmpeg: BrokenFFmpeg      = attrs.field(factory=BrokenFFmpeg, repr=False)
    vsync:  BrokenVsync       = attrs.field(factory=BrokenVsync)
    client: BrokenVsyncClient = None

    # Internal state
    __quit__: bool = False

    def __attrs_post_init__(self):

        # Special registry for the Scene
        self.modules[self.uuid] = self
        self.scene = self

        # Add default modules
        self.add(SombreroContext)
        self.add(SombreroEngine)

        # Setup the scene
        self.setup()
        self.context.init()
        self.engine.render_to_window()
        self.loop()

    # # Loop wise

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
        self.client = self.vsync.new(self.__update__, dt=True)

        while not self.__quit__:
            self.client.frequency = self.context.fps
            self.vsync.next()

    def __update__(self, dt: float):

        # Temporal
        self.context.time += dt
        self.context.dt    = dt

        log.trace(f"Time: {self.context.time:.2f} | dt: {self.context.dt:.4f}")

        # Update modules
        for module in list(self.modules.values()) + [self]:
            module.update()

        # Render scene
        # self.engine.render()
        # self.context.window.swap_buffers()

    # # Pipeline

    @property
    def pipeline(self) -> dict[ShaderVariable]:
        """Get the pipeline of this instance and the bound non-Self modules"""
        return BrokenUtils.flatten([module.pipeline for module in self.modules])
