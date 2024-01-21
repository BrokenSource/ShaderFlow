from . import *


@functools.lru_cache(maxsize=None)
def __uppercase2camelcase__(name: str) -> str:
    # Convert stuff like (NUMPAD_9 -> Numpad9) and (Home -> Home)
    return "".join([word.capitalize() for word in name.split("_")])

@define
class SombreroKeyboard(SombreroModule):
    Keys = None

    __pressed__: Dict[int, bool] = Factory(dict)

    def is_pressed(self,
        key:   int | ModernglKeys=None,
        alt:   bool=False,
        ctrl:  bool=False,
        shift: bool=False,
    ) -> bool:
        return all([
            self.__pressed__.setdefault(key, False)     if key   else True,
            self.__pressed__.setdefault("ALT", False)   if alt   else True,
            self.__pressed__.setdefault("CTRL", False)  if ctrl  else True,
            self.__pressed__.setdefault("SHIFT", False) if shift else True,
        ])

    def __call__(self, *a, **k) -> bool:
        return self.is_pressed(*a, **k)

    def pipeline(self) -> Iterable[ShaderVariable]:
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

    def handle(self, message: SombreroMessage):
        if isinstance(message, SombreroMessage.Keyboard.Press):
            self.__pressed__[message.key] = (message.action != SombreroKeyboard.Keys.ACTION_RELEASE)
            self.__pressed__["ALT"]       = (message.modifiers.alt)
            self.__pressed__["CTRL"]      = (message.modifiers.ctrl)
            self.__pressed__["SHIFT"]     = (message.modifiers.shift)

