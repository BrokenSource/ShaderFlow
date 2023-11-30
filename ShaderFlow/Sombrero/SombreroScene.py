from . import *


@attrs.define
class SombreroScene(SombreroModule):

    # Registry
    modules: Dict[SombreroID, SombreroModule] = attrs.field(factory=dict)

    # Metadata
    name: str = "Untitled Sombrero Scene"

    # Base classes and utils for a Scene
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
        self.add(SombreroContext)
        self.context.backend = SombreroBackend.GLFW
        self.context.title = f"ShaderFlow | {self.name} | BrokenSource"
        self.setup()

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        # Fixme: How to deal with ShaderFlow as a dependency scenario?
        return SHADERFLOW_DIRECTORIES.SHADERFLOW_CURRENT_SCENE

    def register(self, module: SombreroModule) -> SombreroModule:
        """Register a module in the scene"""
        log.info(f"{module.who} Registering module")
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

            self.__ffmpeg__.write(self.context.window.fbo.read(components=3))

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

    __ffmpeg__: BrokenFFmpeg = attrs.field(factory=BrokenFFmpeg)

    @property
    def ffmpeg(self) -> BrokenFFmpeg:
        self.__ffmpeg__ = (
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

        return self.__ffmpeg__
