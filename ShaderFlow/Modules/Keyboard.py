from . import *


@functools.lru_cache(maxsize=None)
def __camel__(name: str) -> str:
    # Convert stuff like (NUMPAD_9 -> Numpad9) and (Home -> Home)
    return "".join([word.capitalize() for word in name.split("_")])

@define
class ShaderFlowKeyboard(ShaderFlowModule):
    Keys    = None
    DirKeys = None

    _pressed: Dict[int, bool] = Factory(dict)

    @staticmethod
    def set_keymap(keymap: ModernglKeys) -> None:
        ShaderFlowKeyboard.DirKeys = {key: getattr(keymap, key) for key in dir(keymap) if not key.startswith("_")}
        ShaderFlowKeyboard.Keys = keymap

    def pressed(self, key: int | ModernglKeys=None) -> bool:
        return self._pressed.setdefault(key, False)

    def __call__(self, *a, **k) -> bool:
        return self.pressed(*a, **k)

    def pipeline(self) -> Iterable[ShaderVariable]:
        return
        for name, key in ShaderFlowKeyboard.DirKeys.items():
            yield ShaderVariable("uniform", "bool", f"iKey{__camel__(name)}", self._pressed.setdefault(key, False))

    def handle(self, message: ShaderFlowMessage):
        if isinstance(message, ShaderFlowMessage.Keyboard.Press):
            self._pressed[message.key] = (message.action != ShaderFlowKeyboard.Keys.ACTION_RELEASE)

