import glfw
import imgui
import moderngl
import quaternion
import samplerate
import scipy
import ShaderFlow.Resources as ShaderFlowResources
import soundcard
from intervaltree import IntervalTree
from moderngl_window.context.base import BaseKeys as ModernglKeys
from moderngl_window.context.base import BaseWindow as ModernglWindow
from moderngl_window.integrations.imgui import \
    ModernglWindowRenderer as ModernglImgui

import Broken
from Broken import *

SHADERFLOW_ABOUT = f"""
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨

©️ Broken Source Software, AGPLv3-only License.
"""

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

Broken.PROJECT = SHADERFLOW

# Fixme: Required optimal? Maybe once when shaders fail
BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)

# isort: off
from .Common import *
from .Core   import *
