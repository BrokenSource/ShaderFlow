import glfw
import imgui
import moderngl
import quaternion
import ShaderFlow.Resources as ShaderFlowResources
import soundcard
from intervaltree import IntervalTree
from moderngl_window.context.base import BaseKeys as ModernglKeys
from moderngl_window.context.base import BaseWindow as ModernglWindow
from moderngl_window.integrations.imgui import \
    ModernglWindowRenderer as ModernglImgui

from Broken import *

SHADERFLOW = PROJECT = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

# Fixme: Required optimal? Maybe once when shaders fail
BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)

# isort: off
from .Common  import *
from .Message import *
from .Module  import *
from .Modules import *
from .Engine  import *
from .Scene   import *

# Make modules findable as property on the scene
ShaderFlowModule.make_findable(ShaderFlowKeyboard)
ShaderFlowModule.make_findable(ShaderFlowCamera)
