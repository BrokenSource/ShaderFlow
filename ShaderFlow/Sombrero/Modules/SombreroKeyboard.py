from . import *


@functools.lru_cache(maxsize=None)
def __uppercase2camelcase__(name: str) -> str:
    # Convert stuff like (NUMPAD_9 -> Numpad9) and (Home -> Home)
    return "".join([word.capitalize() for word in name.split("_")])

@define
class SombreroKeyboard(SombreroModule):
    Keys    = None
    DirKeys = None

    __pressed__: Dict[int, bool] = Factory(dict)

    @staticmethod
    def set_keymap(keymap: ModernglKeys) -> None:
        SombreroKeyboard.DirKeys = {key: getattr(keymap, key) for key in dir(keymap) if not key.startswith("_")}
        SombreroKeyboard.Keys = keymap

    def pressed(self, key: int | ModernglKeys=None) -> bool:
        return self.__pressed__.setdefault(key, False)

    def __call__(self, *a, **k) -> bool:
        return self.pressed(*a, **k)

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        return
        for name, key in SombreroKeyboard.DirKeys.items():
            yield ShaderVariable(
                qualifier="uniform",
                type="bool",
                name=f"{self.prefix}Key{__uppercase2camelcase__(name)}",
                value=self.__pressed__.setdefault(key, False),
            )

    def __handle__(self, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Keyboard.Press):
            self.__pressed__[message.key] = (message.action != SombreroKeyboard.Keys.ACTION_RELEASE)

