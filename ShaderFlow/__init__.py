import Broken
import ShaderFlow.Resources as ShaderFlowResources
from Broken import BrokenPath, BrokenProject

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

Broken.set_project(SHADERFLOW)
BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)
