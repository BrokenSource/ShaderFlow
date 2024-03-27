from __future__ import annotations

import Broken
import ShaderFlow.Resources as ShaderFlowResources
from Broken.Base import BrokenPath
from Broken.Project import BrokenProject

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

Broken.PROJECT = SHADERFLOW

# Fixme: Required optimal? Maybe once when shaders fail
BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)
