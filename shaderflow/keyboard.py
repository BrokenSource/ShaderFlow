import functools
from collections.abc import Iterable
from typing import TYPE_CHECKING, Union

from attrs import Factory, define

from shaderflow.message import ShaderMessage
from shaderflow.module import ShaderModule
from shaderflow.variable import ShaderVariable, Uniform

if TYPE_CHECKING:
    from moderngl_window.context.base import BaseKeys as ModernglKeys


@functools.lru_cache(maxsize=None)
def __camel__(name: str) -> str:
    # Convert stuff like (NUMPAD_9 -> Numpad9) and (Home -> Home)
    return "".join([word.capitalize() for word in name.split("_")])

@define
class ShaderKeyboard(ShaderModule):
    Keys    = None
    DirKeys = None

    _pressed: dict[int, bool] = Factory(dict)

    @staticmethod
    def set_keymap(keymap: 'ModernglKeys') -> None:
        ShaderKeyboard.DirKeys = {key: getattr(keymap, key) for key in dir(keymap) if not key.startswith("_")}
        ShaderKeyboard.Keys = keymap

    def pressed(self, key: Union[int, 'ModernglKeys']=None) -> bool:
        return self._pressed.setdefault(key, False)

    def __call__(self, *a, **k) -> bool:
        return self.pressed(*a, **k)

    def pipeline(self) -> Iterable[ShaderVariable]:
        return
        for name, key in ShaderKeyboard.DirKeys.items():
            yield Uniform("bool", f"iKey{__camel__(name)}", self._pressed.setdefault(key, False))

    def handle(self, message: ShaderMessage):
        if isinstance(message, ShaderMessage.Keyboard.Press):
            self._pressed[message.key] = (message.action != ShaderKeyboard.Keys.ACTION_RELEASE)

