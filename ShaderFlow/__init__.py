from __future__ import annotations

import Broken
from Broken import *

_spinner = yaspin(text="Loading Library: ShaderFlow")
_spinner.start()

import cv2
import glfw
import imgui
import moderngl
import quaternion
import samplerate
import scipy
import ShaderFlow.Resources as ShaderFlowResources
import soundcard
import turbojpeg
from intervaltree import IntervalTree
from moderngl_window.context.base import BaseKeys as ModernglKeys
from moderngl_window.context.base import BaseWindow as ModernglWindow
from moderngl_window.integrations.imgui import \
    ModernglWindowRenderer as ModernglImgui

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
from .Common  import *
from .Message import *
from .Module  import *
from .Texture import *
from .Modules import *
from .Shader  import *
from .Scene   import *
from .Texture import *

_spinner.stop()
