from . import *


@functools.lru_cache(maxsize=None)
def __uppercase2camelcase__(name: str) -> str:
    # Convert stuff like (NUMPAD_9 -> Numpad9) and (Home -> Home)
    return "".join([word.capitalize() for word in name.split("_")])

@define
class SombreroKeyboard(SombreroModule):
    Keys = None

    __pressed__: Dict[int, bool] = Factory(dict)

    def pressed(self, key: int | ModernglKeys=None) -> bool:
        return self.__pressed__.setdefault(key, False)

    def __call__(self, *a, **k) -> bool:
        return self.pressed(*a, **k)

    def __pipeline__(self) -> Iterable[ShaderVariable]:
        return # Fixme: Faster pipeline for Keyboard (+Dynamics? Maybe on a array?)

        # Iterate on the class attributes, no __dict__ as isn't instance
        for name in dir(ModernglKeys):

            # Skip dunder internal objects
            if name.startswith("__"):
                continue

            # Skip actions
            if name.startswith("ACTION_"):
                continue

            # Get the Keyboard key id
            key = getattr(SombreroKeyboard.Keys, name)

            # Send the key state to the pipeline
            yield ShaderVariable(
                qualifier="uniform",
                type="bool",
                name=f"{self.prefix}Key{__uppercase2camelcase__(name)}",
                value=self.__pressed__.setdefault(key, False),
            )

    def __handle__(self, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Keyboard.Press):
            self.__pressed__[message.key] = (message.action != SombreroKeyboard.Keys.ACTION_RELEASE)

