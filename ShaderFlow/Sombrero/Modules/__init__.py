from .. import *
from .SombreroCamera import *
from .SombreroContext import *
from .SombreroMouse import *
from .SombreroShader import *

SombreroModule.broken_extend("context", SombreroContext)
SombreroModule.broken_extend("mouse", SombreroMouse)
SombreroModule.broken_extend("camera", SombreroCamera)
