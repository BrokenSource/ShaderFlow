from Broken import *

from . import Resources

SHADERFLOW = BrokenProject(
    __file__=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=Resources,
)

# Project directories
SHADERFLOW.SHADERS  = SHADERFLOW.RESOURCES/"Shaders"
SHADERFLOW.FRAGMENT = SHADERFLOW.SHADERS/"Fragment"
SHADERFLOW.VERTEX   = SHADERFLOW.SHADERS/"Vertex"

from .Sombrero import *
