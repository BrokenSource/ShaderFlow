from . import *


class SombreroMessage:

    # # Special

    class Any:
        """Any data type"""
        data: Any

    # # Mouse

    class Mouse:

        @attrs.define
        class Position:
            x: int = None
            y: int = None
            dx: int = None
            dy: int = None

        @attrs.define
        class Press:
            x: int = None
            y: int = None
            button: int = None

        @attrs.define
        class Release:
            x: int = None
            y: int = None
            button: int = None

        @attrs.define
        class Drag:
            x: int = None
            y: int = None
            dx: int = None
            dy: int = None

        @attrs.define
        class Scroll:
            dx: int = None
            dy: int = None

    # # Window

    class Window:

        @attrs.define
        class Resize:
            width:  int = None
            height: int = None

        @attrs.define
        class Render:
            ...

        @attrs.define
        class Iconify:
            state: bool = None

        @attrs.define
        class FileDrop:
            files: list[str] = None

        @attrs.define
        class Close:
            ...

    # # Keyboard

    class Keyboard:

        @attrs.define
        class Key:
            key:       int = None
            action:    int = None
            modifiers: int = None

        @attrs.define
        class Unicode:
            char: str = None
