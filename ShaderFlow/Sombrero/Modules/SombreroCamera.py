from . import *


@attrs.define
class SombreroCamera(SombreroModule):
    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage) -> None:
        if not bound: return

        if isinstance(message, SombreroMessage.Mouse.Position):
            print(f"Camera got mouse position: {message}")
