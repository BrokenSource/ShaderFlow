from pathlib import Path
from typing import Any

import glfw
from attrs import define, field
from PIL import Image

from shaderflow.window import BaseKeys, BaseWindow

GLFW_key = int


@define(init=False)
class Window(BaseWindow):
    name: str = "glfw"
    keys = BaseKeys

    _mouse_button_map: dict[int, int] = field(init=False)
    _window: Any = field(init=False)
    _has_focus: bool = field(default=True, init=False)
    _non_fullscreen_size: tuple[int, int] = field(default=(1920, 1080), init=False)
    _non_fullscreen_position: tuple[int, int] = field(default=(0, 0), init=False)

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
        self._mouse_button_map = {0: 1, 1: 2, 2: 3}
        self._window = None
        self._has_focus = True
        # _non_fullscreen_size and _non_fullscreen_position have defaults
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

        if not glfw.init():
            raise ValueError("Failed to initialize glfw")

        glfw.window_hint(glfw.CONTEXT_CREATION_API, glfw.NATIVE_CONTEXT_API)
        glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, self.gl_version[0])
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, self.gl_version[1])
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
        glfw.window_hint(glfw.RESIZABLE, self.resizable)
        glfw.window_hint(glfw.VISIBLE, self.visible)
        glfw.window_hint(glfw.DOUBLEBUFFER, True)
        glfw.window_hint(glfw.DEPTH_BITS, 24)
        glfw.window_hint(glfw.STENCIL_BITS, 8)
        glfw.window_hint(glfw.SAMPLES, self.samples)
        glfw.window_hint(glfw.SCALE_TO_MONITOR, glfw.TRUE)

        monitor = None
        width = self._width if self._width > 0 else 1920
        height = self._height if self._height > 0 else 1080
        self._window = glfw.create_window(width, height, self.title, monitor, None)
        self._has_focus = True

        if self.fullscreen:
            self._set_fullscreen(True)

        if not self._window:
            glfw.terminate()
            raise ValueError("Failed to create window")

        self.cursor = self._cursor

        self._buffer_width, self._buffer_height = glfw.get_framebuffer_size(self._window)
        glfw.make_context_current(self._window)

        if self.vsync:
            glfw.swap_interval(1)
        else:
            glfw.swap_interval(0)

        glfw.set_key_callback(self._window, self.glfw_key_event_callback)
        glfw.set_cursor_pos_callback(self._window, self.glfw_mouse_event_callback)
        glfw.set_mouse_button_callback(self._window, self.glfw_mouse_button_callback)
        glfw.set_scroll_callback(self._window, self.glfw_mouse_scroll_callback)
        glfw.set_window_size_callback(self._window, self.glfw_window_resize_callback)
        glfw.set_char_callback(self._window, self.glfw_char_callback)
        glfw.set_window_focus_callback(self._window, self.glfw_window_focus)
        glfw.set_cursor_enter_callback(self._window, self.glfw_cursor_enter)
        glfw.set_window_iconify_callback(self._window, self.glfw_window_iconify)
        glfw.set_window_close_callback(self._window, self.glfw_window_close)

        self.init_mgl_context()
        self.set_default_viewport()

    def _set_fullscreen(self, value: bool) -> None:
        monitor = glfw.get_primary_monitor()
        mode = glfw.get_video_mode(monitor)
        refresh_rate = mode.refresh_rate if self.vsync else glfw.DONT_CARE
        self.resizable = not value
        glfw.window_hint(glfw.RESIZABLE, self.resizable)

        if value:
            self._non_fullscreen_size = self.width, self.height
            self._non_fullscreen_position = self.position
            glfw.set_window_monitor(
                self._window,
                monitor,
                0,
                0,
                mode.size.width,
                mode.size.height,
                refresh_rate,
            )
            glfw.window_hint(glfw.RED_BITS, mode.bits.red)
            glfw.window_hint(glfw.GREEN_BITS, mode.bits.green)
            glfw.window_hint(glfw.BLUE_BITS, mode.bits.blue)
            glfw.window_hint(glfw.REFRESH_RATE, mode.refresh_rate)
        else:
            glfw.set_window_monitor(
                self._window,
                None,
                *self._non_fullscreen_position,
                *self._non_fullscreen_size,
                refresh_rate,
            )

        if self.vsync:
            glfw.swap_interval(1)
        else:
            glfw.swap_interval(0)

    def _set_vsync(self, value: bool) -> None:
        glfw.swap_interval(value)

    @property
    def size(self) -> tuple[int, int]:
        return self._width, self._height

    @size.setter
    def size(self, value: tuple[int, int]) -> None:
        glfw.set_window_size(self._window, value[0], value[1])

    @property
    def position(self) -> tuple[int, int]:
        return glfw.get_window_pos(self._window)

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        glfw.set_window_pos(self._window, value[0], value[1])

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value
        if value:
            glfw.show_window(self._window)
        else:
            glfw.hide_window(self._window)

    @property
    def cursor(self) -> bool:
        return self._cursor

    @cursor.setter
    def cursor(self, value: bool) -> None:
        if not self.mouse_exclusivity:
            if value is True:
                glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_NORMAL)
            elif value is False:
                glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_HIDDEN)
        self._cursor = value

    @property
    def mouse_exclusivity(self) -> bool:
        return self._mouse_exclusivity

    @mouse_exclusivity.setter
    def mouse_exclusivity(self, value: bool) -> None:
        self._mouse_exclusivity = value
        if value is True:
            self._mouse_pos = glfw.get_cursor_pos(self._window)
            glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_DISABLED)
        else:
            self.cursor = self._cursor

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        glfw.set_window_title(self._window, value)
        self._title = value

    def swap_buffers(self) -> None:
        glfw.swap_buffers(self._window)
        glfw.poll_events()

    def _handle_modifiers(self, mods: GLFW_key) -> None:
        self._modifiers.shift = mods & 1 == 1
        self._modifiers.ctrl = mods & 2 == 2
        self._modifiers.alt = mods & 4 == 4

    def _set_icon(self, icon_path: Path) -> None:
        image = Image.open(icon_path)
        glfw.set_window_icon(self._window, 1, image)

    def glfw_key_event_callback(
        self, window: Any, key: GLFW_key, scancode: int, action: GLFW_key, mods: GLFW_key
    ) -> None:
        if self.exit_key is not None and key == self._exit_key:
            self.close()

        if action == self.keys.ACTION_PRESS and self._fs_key is not None and key == self._fs_key:
            self.fullscreen = not self.fullscreen

        self._handle_modifiers(mods)

        if action == self.keys.ACTION_PRESS:
            self._key_pressed_map[key] = True
        elif action == self.keys.ACTION_RELEASE:
            self._key_pressed_map[key] = False

        self.key_event_func(key, action, self._modifiers)

    def glfw_mouse_event_callback(self, window: Any, xpos: float, ypos: float) -> None:
        xpos, ypos = int(xpos), int(ypos)
        dx, dy = self._calc_mouse_delta(xpos, ypos)
        dx, dy = int(dx), int(dy)

        if self.mouse_states.any:
            self.mouse_drag_event_func(xpos, ypos, dx, dy)
        else:
            self.mouse_position_event_func(xpos, ypos, dx, dy)

    def glfw_mouse_button_callback(
        self, window: Any, button: GLFW_key, action: GLFW_key, mods: GLFW_key
    ) -> None:
        self._handle_modifiers(mods)
        button = self._mouse_button_map.get(button, -1)
        if button == -1:
            return

        xpos, ypos = glfw.get_cursor_pos(self._window)
        xpos, ypos = int(xpos), int(ypos)

        if action == glfw.PRESS:
            self._handle_mouse_button_state_change(button, True)
            self.mouse_press_event_func(xpos, ypos, button)
        else:
            self._handle_mouse_button_state_change(button, False)
            self.mouse_release_event_func(xpos, ypos, button)

    def glfw_mouse_scroll_callback(self, window: Any, x_offset: float, y_offset: float) -> None:
        self.mouse_scroll_event_func(x_offset, y_offset)

    def glfw_char_callback(self, window: Any, codepoint: int) -> None:
        self.unicode_char_entered_func(chr(codepoint))

    def glfw_window_resize_callback(self, window: Any, width: int, height: int) -> None:
        self._width, self._height = width, height
        self._buffer_width, self._buffer_height = glfw.get_framebuffer_size(self._window)
        self.set_default_viewport()
        self.resize_func(self._buffer_width, self._buffer_height)

    def glfw_window_focus(self, window: Any, focused: int) -> None:
        self._has_focus = focused == 1

    def glfw_cursor_enter(self, window: Any, enter: int) -> None:
        pass

    def glfw_window_iconify(self, window: Any, iconified: int) -> None:
        self._visible = iconified == 0
        self.iconify_func(iconified == 1)

    def glfw_window_close(self, window: Any) -> None:
        self.close()

    def destroy(self) -> None:
        glfw.terminate()
