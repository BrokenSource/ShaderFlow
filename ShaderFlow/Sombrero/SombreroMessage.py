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
            # Real
            x:  int = 0
            y:  int = 0
            dx: int = 0
            dy: int = 0

            # Normalized
            u:  float = 0.0
            v:  float = 0.0
            du: float = 0.0
            dv: float = 0.0

        @attrs.define
        class Press:
            button: int = 0

            # Real
            x: int = 0
            y: int = 0

            # Normalized
            u: float = 0.0
            v: float = 0.0

        @attrs.define
        class Release:
            button: int = 0

            # Real
            x: int = 0
            y: int = 0

            # Normalized
            u: float = 0.0
            v: float = 0.0

        @attrs.define
        class Drag:
            # Real
            x:  int = 0
            y:  int = 0
            dx: int = 0
            dy: int = 0

            # Normalized
            u:  float = 0.0
            v:  float = 0.0
            du: float = 0.0
            dv: float = 0.0

        @attrs.define
        class Scroll:
            # Real
            dx: int = 0
            dy: int = 0

            # Normalized
            du: float = 0.0
            dv: float = 0.0

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

    # # Engine

    class Engine:

        @attrs.define
        class RecreateTextures:
            ...

        @attrs.define
        class ReloadShaders:
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
