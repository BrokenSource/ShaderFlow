from collections.abc import Iterable

from attrs import Factory, define

from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.variable import ShaderVariable, Uniform
from shaderflow.window import BaseKeys


@define
class ShaderKeyboard(ShaderModule):
    Keys: type[BaseKeys] | None = None
    DirKeys: dict[str, int] | None = None

    _pressed: dict[int, bool] = Factory(dict)

    @staticmethod
    def set_keymap(keymap: type[BaseKeys]) -> None:
        ShaderKeyboard.DirKeys = {key: getattr(keymap, key) for key in dir(keymap) if not key.startswith("_")}
        ShaderKeyboard.Keys = keymap

    def pressed(self, key: int | None = None) -> bool:
        if key is None:
            return any(self._pressed.values())
        return self._pressed.setdefault(key, False)

    def __call__(self, *a, **k) -> bool:
        return self.pressed(*a, **k)

    def pipeline(self) -> Iterable[ShaderVariable]:
        if ShaderKeyboard.DirKeys is None:
            return
        for name, key in ShaderKeyboard.DirKeys.items():
            yield Uniform("bool", f"iKey{name}", self._pressed.setdefault(key, False))

    def handle(self, message: ShaderMessage):
        if isinstance(message, ShaderMessage.Keyboard.Press):
            if ShaderKeyboard.Keys is not None:
                self._pressed[message.key] = (message.action != ShaderKeyboard.Keys.ACTION_RELEASE)
