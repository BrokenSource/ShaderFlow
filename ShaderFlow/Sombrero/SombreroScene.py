from . import *


@attrs.define
class SombreroScene(SombreroModule):
    modules: Dict[SombreroID, SombreroModule] = attrs.field(factory=dict)

    # Base classes and utils for a Scene
    ffmpeg: BrokenFFmpeg      = attrs.field(factory=BrokenFFmpeg, repr=False)
    vsync:  BrokenVsync       = attrs.field(factory=BrokenVsync)
    client: BrokenVsyncClient = None

    # Internal state
    __quit__:      bool = False
    __recording__: bool = False

    def __attrs_post_init__(self):

        # Register scene to the scene, welp, it's required
        self.register(self)

        # Add default modules
        self.child(SombreroEngine).render_to_window()
        self.add(SombreroContext).init()
        self.setup()

    def register(self, module: SombreroModule) -> SombreroModule:
        """Register a module in the scene"""
        log.trace(f"({module.suuid}) Registering module ({module.__class__.__name__})")
        self.modules[module.uuid] = module
        module.scene = self
        return module

    def __handle__(self, message: SombreroMessage) -> None:
        if isinstance(message, SombreroMessage.Window.Close):
            self.quit()

    # # Loop wise

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
        self.__quit__ = True

    def run(self) -> None:
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

            if not self.__recording__:
                continue

            self.ffmpeg.write(self.context.window.fbo.read(components=3))

    def __update__(self, dt: float):

        # Temporal
        self.context.time += dt * self.context.time_scale
        self.context.dt    = dt * self.context.time_scale

        # Update modules
        for module in list(self.modules.values()) + [self]:
            module.update()

        # Swap window buffers
        self.context.window.swap_buffers()

    # # Rendering

    def configure_ffmpeg(self) -> BrokenFFmpeg:
        self.ffmpeg = (
            BrokenFFmpeg()
            .quiet()
            .overwrite()
            .format(FFmpegFormat.Rawvideo)
            .pixel(FFmpegPixelFormat.RGB24)
            .resolution(*self.context.render_resolution)
            .framerate(self.context.fps)
            .filter(FFmpegFilterFactory.scale(*self.context.resolution))
            .filter(FFmpegFilterFactory.flip_vertical())
            .input("-")
        )

    @abstractmethod
    def render(self):
        self.configure_ffmpeg()
        ...