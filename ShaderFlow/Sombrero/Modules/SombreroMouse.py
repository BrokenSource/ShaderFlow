from . import *


@attrs.define
class SombreroMouse(SombreroModule):
    def action(self):
        self.relay(SombreroMessage.Mouse.Position(x=1, y=2))
        log.info(f"Mouse got context: {self.context}")

    def on_message(self, hash: SombreroHash, bound: bool, message: SombreroMessage):
        ...