from dearlog import logger  # isort: split

from importlib.metadata import metadata

__meta__:   dict = metadata(__package__)
__about__:   str = __meta__.get("Summary")
__author__:  str = __meta__.get("Author")
__version__: str = __meta__.get("Version")

from pathlib import Path

RESOURCES: Path = Path(__file__).parent/"resources"

import os

# Nvidia: Fix cpu usage on glfw.swap_buffers when vsync is off and the gpu is overwhelmed
# - https://forums.developer.nvidia.com/t/glxswapbuffers-gobbling-up-a-full-cpu-core-when-vsync-is-off/156635
# - https://forums.developer.nvidia.com/t/gl-yield-and-performance-issues/27736
os.environ.setdefault("__GL_YIELD", "USLEEP")

from broken.project import BrokenProject

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=__about__,
)
