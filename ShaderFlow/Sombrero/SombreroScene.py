from . import *


@attrs.define
class SombreroScene(SombreroModule):

    # ---------------------------------------------------------------------------------------------|

    # Note: You can suggest more metadata fields

    # Basic - Required
    __name__     = "Untitled"
    __author__   = ["Broken Source"]
    __license__  = "AGPL-3.0-only"

    # Contact information - Optional
    __credits__  = ["ShaderFlow"]
    __email__    = None
    __email__    = None
    __website__  = None
    __github__   = None
    __twitter__  = None
    __telegram__ = None
    __discord__  = None
    __youtube__  = None

    # ---------------------------------------------------------------------------------------------|

    # Registry
    modules: Dict[SombreroID, SombreroModule] = attrs.field(factory=dict)

    # Base classes and utils for a Scene
    vsync:     BrokenVsync       = attrs.field(factory=BrokenVsync)
    client:    BrokenVsyncClient = None
    typer_app: typer.Typer       = None
    ffmpeg:    BrokenFFmpeg      = None

    # Internal state flags
    __quit__:      bool = False
    __rendering__: bool = False
    __realtime__:  bool = False

    def __attrs_post_init__(self):

        # Register scene to the scene, welp, it's required
        self.register(self)

        # Add default modules
        self.child(SombreroEngine).render_to_window()
        self.add(SombreroContext)

    def __handle__(self, message: SombreroMessage) -> None:
        if isinstance(message, SombreroMessage.Window.Close):
            self.quit()

    def __update__(self, dt: float):

        # Temporal
        self.context.time += dt * self.context.time_scale
        self.context.dt    = dt * self.context.time_scale

        # Update modules
        for module in list(self.modules.values()) + [self]:
            module.update()

        # Swap window buffers
        self.context.window.swap_buffers()

    # ---------------------------------------------------------------------------------------------|
    # Modules and messaging

    def register(self, module: SombreroModule) -> SombreroModule:
        """
        Register a module in the Scene's modules registry

        Args:
            module (SombreroModule): Module to register

        Returns:
            SombreroModule: The module registered
        """
        log.action(f"{module.who} New module registered")
        self.modules[module.uuid] = module
        module.scene = self
        return module

    # ---------------------------------------------------------------------------------------------|
    # Scene script directories

    @property
    def directory(self) -> Path:
        """Directory of the current Scene script"""
        # Fixme: How to deal with ShaderFlow as a dependency scenario?
        return SHADERFLOW_DIRECTORIES.SHADERFLOW_CURRENT_SCENE

    def read_file(self, file: Path, bytes: bool=False) -> str | bytes:
        """
        Read a file relative to the current Scene script

        Args:
            file (Path): File to read, relative to the current Scene script directory
            bytes (bool, optional): Whether to read the file as bytes, defaults to text

        Returns:
            str | bytes: File contents
        """
        file = self.directory/file
        return file.read_bytes() if bytes else file.read_text()

    # ---------------------------------------------------------------------------------------------|
    # User actions

    def cli(self, *args: List[str]):
        self.typer_app = BrokenTyper.typer_app()
        args = list(args)

        # Run scene command
        self.typer_app.command(
            help="Launch the Scene in Realtime or Render to a video file",
            **BrokenTyper.with_context()
        )(self.main)

        # Settings command (optional)
        self.typer_app.command(
            help="Custom configuration of the Scene if any",
            **BrokenTyper.with_context()
        )(self.settings)

        # Implicitly add main command by default
        # Fixme: Automatically find valid commands
        # Fixme: This is a recurring issue
        if (not args) or (args[0] not in ("settings")):
            args.insert(0, "main")

        # Launch the CLI
        self.typer_app(args or sys.argv)

    @abstractmethod
    def settings(self):
        """Optional scene settings to be configured on the CLI"""
        pass

    def quit(self) -> None:
        """
        Stops the scene main loop created in the loop method
        """
        self.__quit__ = True

    def main(self,
        render:   Annotated[bool, typer.Option(help="Render the scene to a video file")]=False,
        name:     Annotated[str,  typer.Option(help="Name of the video file or absolute path, defaults to (DATA/$scene-$date.mp4)'")]=None,
        headless: Annotated[bool, typer.Option(help="Headless rendering")]=False,
        preset:   Annotated[str,  typer.Option(help="FFmpeg render preset")]=None,
        open:     Annotated[bool, typer.Option(help="Open the output directory after rendering?")]=False,
    ) -> Path | None:

        # Set useful state flags
        self.__realtime__  = not render
        self.__rendering__ = render

        # Headless rendering
        self.context.backend = SombreroBackend.Headless if headless else self.context.backend
        self.context.init_window()
        self.setup()
        self.context.title = f"ShaderFlow | {self.__name__} Scene | BrokenSource"

        # Create Vsync client with deltatime support
        if self.__realtime__:
            self.client = self.vsync.new(self.__update__, frequency=self.context.fps, dt=True)

        else:
            # Get video output path - if not absolute, save to data directory
            output = Path(name or f"{self.__name__} ({arrow.now().format('YYYY-MM-DD_HH-mm-ss')}).mp4")
            output = output if output.is_absolute() else SHADERFLOW_DIRECTORIES.DATA/output

            # Create FFmpeg process
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

            # Apply preset
            self.ffmpeg = (
                self.ffmpeg
                .video_codec(FFmpegVideoCodec.H264)
                .preset(FFmpegH264Preset.Slow)
                .tune(FFmpegH264Tune.Film)
                .quality(FFmpegH264Quality.High)
            )

            log.todo("Apply FFmpeg SombreroScene rendering preset")

            # Add progress bar
            progress_bar = tqdm(
                total=self.context.time_end * self.context.fps,
                desc="Rendering video",
                leave=False,
                unit="Frame"
            )

            # Add output video
            self.ffmpeg.output(output)
            self.ffmpeg = self.ffmpeg.pipe()

        # Main rendering loop
        while not self.__quit__:

            # Update the Scene:
            # - Dynamic deltatime for realtime
            # - Static  deltatime for rendering
            if self.__realtime__:
                self.vsync.next()
            else:
                self.__update__(1/self.context.fps)

            # Rendering logic
            if self.__rendering__:

                # Update progress bar
                progress_bar.update(1)

                # Write new frame to FFmpeg
                self.ffmpeg.write(self.context.window.fbo.read(components=3))

                # Quit if rendered until the end
                if self.context.time >= self.context.time_end:
                    log.info(f"Finished rendering ({output})")

                    # Close objects
                    self.context.window.destroy()
                    self.ffmpeg.close()

                    # Open output directory
                    if open: BrokenPath.open_in_file_explorer(output.parent)

                    return output
