import moderngl
from attrs import define, field

from shaderflow.window import BaseKeys, BaseWindow


@define(init=False)
class Window(BaseWindow):
    name: str = "headless"
    keys = BaseKeys

    _fbo: moderngl.Framebuffer | None = field(default=None, init=False)
    _headless: bool = field(default=True, init=False)

    def __init__(
        self,
        title: str = "ModernGL",
        gl_version: tuple[int, int] = (3, 3),
        size: tuple[int, int] = (1280, 720),
        resizable: bool = True,
        visible: bool = True,
        fullscreen: bool = False,
        vsync: bool = True,
        aspect_ratio: float | None = None,
        samples: int = 0,
        cursor: bool = True,
        backend: str | None = None,
    ) -> None:
        self._fbo = None
        self._headless = True
        super().__init__(
            title=title,
            gl_version=gl_version,
            size=size,
            resizable=resizable,
            visible=visible,
            fullscreen=fullscreen,
            vsync=vsync,
            aspect_ratio=aspect_ratio,
            samples=samples,
            cursor=cursor,
            backend=backend,
        )
        self.init_mgl_context()
        self.set_default_viewport()

    @property
    def fbo(self) -> moderngl.Framebuffer:
        if self._fbo is None:
            raise RuntimeError("No framebuffer created yet")
        return self._fbo

    def init_mgl_context(self) -> None:
        if self._backend is not None:
            self._ctx = moderngl.create_standalone_context(
                require=self.gl_version_code,
                backend=self._backend,
            )
        else:
            self._ctx = moderngl.create_standalone_context(
                require=self.gl_version_code,
            )
        self._create_fbo()
        self.use()

    def _create_fbo(self) -> None:
        if self._fbo:
            for attachment in self._fbo.color_attachments:
                attachment.release()
            if self._fbo.depth_attachment:
                self._fbo.depth_attachment.release()
            self._fbo.release()

        size = (self._width, self._height)
        self._fbo = self.ctx.framebuffer(
            color_attachments=self.ctx.texture(size, 4, samples=self._samples),
            depth_attachment=self.ctx.depth_texture(size, samples=self._samples),
        )

    @property
    def size(self) -> tuple[int, int]:
        return self._width, self._height

    @size.setter
    def size(self, value: tuple[int, int]) -> None:
        if value == (self._width, self._height):
            return
        self._width, self._height = value
        self._create_fbo()

    def use(self) -> None:
        if self._fbo is None:
            raise RuntimeError("No framebuffer created yet")
        self._fbo.use()

    def swap_buffers(self) -> None:
        self._ctx.finish()

    def _set_fullscreen(self, value: bool) -> None:
        pass

    def _set_vsync(self, value: bool) -> None:
        pass

    def destroy(self) -> None:
        self._ctx.release()
