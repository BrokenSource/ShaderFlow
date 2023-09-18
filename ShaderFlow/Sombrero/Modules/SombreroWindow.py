from . import *


@attrs.define(slots=False)
class SombreroWindow(SombreroModule):
    strict:                           bool = False
    window_render_func:               BrokenRelay = attrs.Factory(BrokenRelay)
    window_resize_func:               BrokenRelay = attrs.Factory(BrokenRelay)
    window_close_func:                BrokenRelay = attrs.Factory(BrokenRelay)
    window_iconify_func:              BrokenRelay = attrs.Factory(BrokenRelay)
    window_key_event_func:            BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_position_event_func: BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_press_event_func:    BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_release_event_func:  BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_drag_event_func:     BrokenRelay = attrs.Factory(BrokenRelay)
    window_mouse_scroll_event_func:   BrokenRelay = attrs.Factory(BrokenRelay)
    window_unicode_char_entered_func: BrokenRelay = attrs.Factory(BrokenRelay)
    window_files_dropped_event_func:  BrokenRelay = attrs.Factory(BrokenRelay)
    window_on_generic_event_func:     BrokenRelay = attrs.Factory(BrokenRelay)

    # Imgui
    imgui: ModernglImguiIntegration = None


    @property
    def window(self) -> moderngl_window.BaseWindow:
        return self.context.window

    # # Window

    def create_window(self) -> None:
        moderngl_window.conf.settings.WINDOW["class"]        = f"moderngl_window.context.{self.context.backend}.Window"
        moderngl_window.conf.settings.WINDOW["title"]        = self.context.title
        moderngl_window.conf.settings.WINDOW["vsync"]        = False
        moderngl_window.conf.settings.WINDOW["samples"]      = self.context.msaa
        moderngl_window.conf.settings.WINDOW["size"]         = self.context.resolution
        moderngl_window.conf.settings.WINDOW["aspect_ratio"] = self.context.resolution[0]/self.context.resolution[1]

        # Create and assign shared window and context
        self.context.window = moderngl_window.create_window_from_settings()
        self.context.opengl = self.context.window.ctx

        # Create Imgui integration
        if self.context.backend != SombreroBackend.Headless:
            imgui.create_context()
            self.imgui = ModernglImguiIntegration(self.window)

        # Add Window callbacks and share them
        self.window.render_func               = self.window_render_func
        self.window.resize_func               = self.window_resize_func.bind(self.__window_resize_func__)
        self.window.close_func                = self.window_close_func.bind(self.__window_close_func__)
        # self.window.iconify_func              = self.window_iconify_func.bind(self.window_iconify_func)
        # self.window.key_event_func            = self.window_key_event_func.bind(self.keyboard.key_event_func)
        # self.window.mouse_position_event_func = self.window_mouse_position_event_func.bind(self.mouse.__mouse_position_event_func__)
        # self.window.mouse_press_event_func    = self.window_mouse_press_event_func.bind(self.mouse.__mouse_press_event_func__)
        # self.window.mouse_release_event_func  = self.window_mouse_release_event_func.bind(self.mouse.__mouse_release_event_func__)
        # self.window.mouse_drag_event_func     = self.window_mouse_drag_event_func.bind(self.mouse.__mouse_drag_event_func__)
        # self.window.mouse_scroll_event_func   = self.window_mouse_scroll_event_func.bind(self.mouse.__mouse_scroll_event_func__)
        # self.window.unicode_char_entered_func = self.window_unicode_char_entered_func.bind(self.__window_unicode_char_entered_func__)
        # self.window.files_dropped_event_func  = self.window_files_dropped_event_func.bind(self.__window_files_dropped_event_func__)
        # self.window.on_generic_event_func     = self.window_on_generic_event_func

    def __window_resize_func__(self, width: int, height: int) -> None:

        # Do nothing in Strict mode
        if self.strict:
            log.trace("Resizing Window does nothing strict mode")
            return

        self.relay(SombreroMessage.Window.Resize(width=width, height=height))

        # Resize Imgui
        if self.imgui:
            self.imgui.resize(width, height)

        # Set new window viewport
        self.window.fbo.viewport = (0, 0, width, height)

    def __window_close_func__(self) -> None:
        self.relay(SombreroMessage.Window.Close())

    def __window_iconify_func__(self, state: bool) -> None:
        self.relay(SombreroMessage.Window.Iconify(state=state))