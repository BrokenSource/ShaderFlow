import glfw
import imgui
import moderngl
import quaternion
import ShaderFlow.Resources as ShaderFlowResources
import soundcard

from Broken import *

SHADERFLOW = PROJECT = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

try:
    import fluidsynth
except ImportError:
    pass

BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)

from .Sombrero import *
