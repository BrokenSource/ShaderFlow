from .. import *
from .SombreroShader import *

# isort: split

from .SombreroCamera import *
from .SombreroContext import *
from .SombreroMouse import *

SombreroModule.broken_extend("context", SombreroContext)
SombreroModule.broken_extend("mouse", SombreroMouse)
SombreroModule.broken_extend("camera", SombreroCamera)
