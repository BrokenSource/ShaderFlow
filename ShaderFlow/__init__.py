import ShaderFlow.Resources as ShaderFlowResources

from Broken import *

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

from .Sombrero import *
