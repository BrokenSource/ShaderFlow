from . import *


@attrs.define
class SombreroContext(SombreroModule):
    width:  int = 1920
    height: int = 1080
