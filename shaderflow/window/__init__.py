from collections.abc import Callable
from pathlib import Path
from typing import Any

import moderngl
from attrs import define, field


class KeyModifiers:
    shift: Any = False
    ctrl: Any = False
    alt: Any = False

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"<KeyModifiers shift={self.shift} ctrl={self.ctrl} alt={self.alt}>"


class BaseKeys:
    # Action types
    ACTION_PRESS = 1
    ACTION_RELEASE = 0
    ACTION_REPEAT = 2

    # Special keys
    ESCAPE = 256
    SPACE = 32
    ENTER = 257
    PAGE_UP = 265
    PAGE_DOWN = 266
    LEFT = 263
    RIGHT = 262
    UP = 265
    DOWN = 264
    LEFT_SHIFT = 340
    RIGHT_SHIFT = 344
    LEFT_CTRL = 341
    RIGHT_CTRL = 345
    LEFT_ALT = 342
    RIGHT_ALT = 346

    TAB = 258
    COMMA = 44
    MINUS = 45
    PERIOD = 46
    SLASH = 47
    SEMICOLON = 59
    EQUAL = 61
    LEFT_BRACKET = 91
    RIGHT_BRACKET = 93
    BACKSLASH = 92
    BACKSPACE = 259
    INSERT = 260
    DELETE = 261
    HOME = 268
    END = 269
    CAPS_LOCK = 280

    F1 = 290
    F2 = 291
    F3 = 292
    F4 = 293
    F5 = 294
    F6 = 295
    F7 = 296
    F8 = 297
    F9 = 298
    F10 = 299
    F11 = 300
    F12 = 301

    NUMBER_0 = 48
    NUMBER_1 = 49
    NUMBER_2 = 50
    NUMBER_3 = 51
    NUMBER_4 = 52
    NUMBER_5 = 53
    NUMBER_6 = 54
    NUMBER_7 = 55
    NUMBER_8 = 56
    NUMBER_9 = 57

    NUMPAD_0 = 320
    NUMPAD_1 = 321
    NUMPAD_2 = 322
    NUMPAD_3 = 323
    NUMPAD_4 = 324
    NUMPAD_5 = 325
    NUMPAD_6 = 326
    NUMPAD_7 = 327
    NUMPAD_8 = 328
    NUMPAD_9 = 329

    A = 65
    B = 66
    C = 67
    D = 68
    E = 69
    F = 70
    G = 71
    H = 72
    I = 73
    J = 74
    K = 75
    L = 76
    M = 77
    N = 78
    O = 79
    P = 80
    Q = 81
    R = 82
    S = 83
    T = 84
    U = 85
    V = 86
    W = 87
    X = 88
    Y = 89
    Z = 90


class MouseButtons:
    left = 1
    right = 2
    middle = 3


class MouseButtonStates:
    left = False
    right = False
    middle = False

    @property
    def any(self) -> bool:
        return self.left or self.right or self.middle

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"<MouseButtonStates left={self.left} right={self.right} middle={self.middle}>"


def dummy_func(*args: Any, **kwargs: Any) -> None:
    pass


@define(init=False)
class BaseWindow:
    name: str = "base"
    keys = BaseKeys
    mouse = MouseButtons

    _title: str = field(default="ModernGL", init=False)
    _gl_version: tuple[int, int] = field(default=(3, 3), init=False)
    _size: tuple[int, int] = field(default=(1280, 720), init=False)
    _resizable: bool = field(default=True, init=False)
    _visible: bool = field(default=True, init=False)
    _fullscreen: bool = field(default=False, init=False)
    _vsync: bool = field(default=True, init=False)
    _fixed_aspect_ratio: float | None = field(default=None, init=False)
    _samples: int = field(default=0, init=False)
    _cursor: bool = field(default=True, init=False)
    _backend: str | None = field(default=None, init=False)
    _headless: bool = field(default=False, init=False)

    _width: int = field(init=False)
    _height: int = field(init=False)
    _buffer_width: int = field(init=False)
    _buffer_height: int = field(init=False)

    _exit_key: Any = field(init=False)
    _fs_key: Any = field(init=False)

    resize_func: Callable[[int, int], None] = field(default=dummy_func, init=False)
    close_func: Callable[[], None] = field(default=dummy_func, init=False)
    iconify_func: Callable[[bool], None] = field(default=dummy_func, init=False)
    key_event_func: Callable[[str | int, int, KeyModifiers], None] = field(default=dummy_func, init=False)
    mouse_position_event_func: Callable[[int, int, int, int], None] = field(default=dummy_func, init=False)
    mouse_press_event_func: Callable[[int, int, int], None] = field(default=dummy_func, init=False)
    mouse_release_event_func: Callable[[int, int, int], None] = field(default=dummy_func, init=False)
    mouse_drag_event_func: Callable[[int, int, int, int], None] = field(default=dummy_func, init=False)
    mouse_scroll_event_func: Callable[[float, float], None] = field(default=dummy_func, init=False)
    unicode_char_entered_func: Callable[[str], None] = field(default=dummy_func, init=False)
    files_dropped_event_func: Callable[[int, int, list[str | Path]], None] = field(default=dummy_func, init=False)

    _ctx: moderngl.Context = field(init=False)
    _viewport: tuple[int, int, int, int] = field(factory=lambda: (0, 0, 0, 0), init=False)
    _close: bool = field(default=False, init=False)
    _key_pressed_map: dict[str | int, bool] = field(factory=dict, init=False)
    _modifiers: KeyModifiers = field(factory=KeyModifiers, init=False)
    _mouse_buttons: MouseButtonStates = field(factory=MouseButtonStates, init=False)
    _mouse_pos: tuple[float, float] = field(factory=lambda: (0.0, 0.0), init=False)
    _mouse_exclusivity: bool = field(default=False, init=False)

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
        self._title = title
        self._gl_version = gl_version
        self._size = size
        self._resizable = resizable
        self._visible = visible
        self._fullscreen = fullscreen
        self._vsync = vsync
        self._fixed_aspect_ratio = aspect_ratio
        self._samples = samples
        self._cursor = cursor
        self._backend = backend

        self._width, self._height = int(self._size[0]), int(self._size[1])
        self._buffer_width, self._buffer_height = self._width, self._height

        self._viewport = (0, 0, 0, 0)
        self._close = False
        self._key_pressed_map = {}
        self._modifiers = KeyModifiers()
        self._mouse_buttons = MouseButtonStates()
        self._mouse_pos = (0, 0)
        self._mouse_exclusivity = False

        if self._fullscreen:
            self._resizable = False

        if self.keys is None:
            raise ValueError(f"Window class {self.__class__} missing keys attribute")

        self._exit_key = self.keys.ESCAPE
        self._fs_key = self.keys.F11

    def init_mgl_context(self) -> None:
        self._ctx = moderngl.create_context(require=self.gl_version_code)

    @property
    def ctx(self) -> moderngl.Context:
        return self._ctx

    @property
    def backend(self) -> str | None:
        return self._backend

    @property
    def gl_version(self) -> tuple[int, int]:
        return self._gl_version

    @property
    def headless(self) -> bool:
        return self._headless

    @property
    def fbo(self) -> moderngl.Framebuffer:
        return self._ctx.screen

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def size(self) -> tuple[int, int]:
        return self._width, self._height

    @size.setter
    def size(self, value: tuple[int, int]) -> None:
        self._width, self._height = int(value[0]), int(value[1])

    @property
    def buffer_size(self) -> tuple[int, int]:
        return self._buffer_width, self._buffer_height

    @property
    def position(self) -> tuple[int, int]:
        return (0, 0)

    @position.setter
    def position(self, value: tuple[int, int]) -> None:
        pass

    @property
    def viewport(self) -> tuple[int, int, int, int]:
        return self._viewport

    @property
    def pixel_ratio(self) -> float:
        return self.buffer_size[0] / self.size[0]

    @property
    def viewport_width(self) -> int:
        return self._viewport[2]

    @property
    def viewport_height(self) -> int:
        return self._viewport[3]

    @property
    def resizable(self) -> bool:
        return self._resizable

    @resizable.setter
    def resizable(self, value: bool) -> None:
        self._resizable = value

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def hidden(self) -> bool:
        return not self._visible

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    @fullscreen.setter
    def fullscreen(self, value: bool) -> None:
        self._set_fullscreen(value)
        self._fullscreen = value

    @property
    def fullscreen_key(self) -> Any:
        return self._fs_key

    @fullscreen_key.setter
    def fullscreen_key(self, value: Any) -> None:
        self._fs_key = value

    @property
    def exit_key(self) -> Any:
        return self._exit_key

    @exit_key.setter
    def exit_key(self, value: Any) -> None:
        self._exit_key = value

    @property
    def vsync(self) -> bool:
        return self._vsync

    @vsync.setter
    def vsync(self, value: bool) -> None:
        self._set_vsync(value)
        self._vsync = value

    @property
    def aspect_ratio(self) -> float:
        if self._fixed_aspect_ratio:
            return self._fixed_aspect_ratio
        return self.width / self.height

    @aspect_ratio.setter
    def aspect_ratio(self, value: float | None) -> None:
        self._fixed_aspect_ratio = value

    @property
    def samples(self) -> int:
        return self._samples

    @property
    def cursor(self) -> bool:
        return self._cursor

    @cursor.setter
    def cursor(self, value: bool) -> None:
        self._cursor = value

    @property
    def mouse_exclusivity(self) -> bool:
        return self._mouse_exclusivity

    @mouse_exclusivity.setter
    def mouse_exclusivity(self, value: bool) -> None:
        self._mouse_exclusivity = value

    @property
    def modifiers(self) -> KeyModifiers:
        return self._modifiers

    @property
    def mouse_states(self) -> MouseButtonStates:
        return self._mouse_buttons

    def _handle_mouse_button_state_change(self, button: int, pressed: bool) -> None:
        if button == self.mouse.left:
            self._mouse_buttons.left = pressed
        elif button == self.mouse.right:
            self._mouse_buttons.right = pressed
        elif button == self.mouse.middle:
            self._mouse_buttons.middle = pressed
        else:
            raise ValueError(f"Incompatible mouse button number: {button}")

    def _calc_mouse_delta(self, xpos: float, ypos: float) -> tuple[float, float]:
        dx, dy = xpos - self._mouse_pos[0], ypos - self._mouse_pos[1]
        self._mouse_pos = xpos, ypos
        return dx, dy

    @property
    def is_closing(self) -> bool:
        return self._close

    @is_closing.setter
    def is_closing(self, value: bool) -> None:
        self._close = value

    def close(self) -> None:
        self.is_closing = True
        self.close_func()

    def swap_buffers(self) -> None:
        raise NotImplementedError()

    def resize(self, width: int, height: int) -> None:
        if self.resize_func is not dummy_func:
            self.resize_func(width, height)

    def destroy(self) -> None:
        raise NotImplementedError()

    def _set_fullscreen(self, value: bool) -> None:
        raise NotImplementedError(f"Toggling fullscreen not supported by {self.name}")

    def _set_vsync(self, value: bool) -> None:
        raise NotImplementedError(f"Toggling vsync not supported by {self.name}")

    @property
    def gl_version_code(self) -> int:
        return self._gl_version[0] * 100 + self._gl_version[1] * 10

    def set_default_viewport(self) -> None:
        if self._fixed_aspect_ratio:
            expected_width = int(self._buffer_height * self._fixed_aspect_ratio)
            expected_height = int(expected_width / self._fixed_aspect_ratio)

            if expected_width > self._buffer_width:
                expected_width = self._buffer_width
                expected_height = int(expected_width / self._fixed_aspect_ratio)

            blank_space_x = self._buffer_width - expected_width
            blank_space_y = self._buffer_height - expected_height

            self._viewport = (
                blank_space_x // 2,
                blank_space_y // 2,
                expected_width,
                expected_height,
            )
        else:
            self._viewport = (0, 0, self._buffer_width, self._buffer_height)

        self.fbo.viewport = self._viewport
