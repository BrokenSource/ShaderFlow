from dearlog import logger  # isort: split

from importlib.metadata import metadata

__meta__:   dict = metadata(__package__)
__about__:   str = __meta__.get("Summary")
__author__:  str = __meta__.get("Author")
__version__: str = __meta__.get("Version")

from pathlib import Path

from platformdirs import PlatformDirs

package = Path(__file__).parent
"""Path to the package directory"""

resources = Path(__file__).parent/"resources"
"""Path to the package resources directory"""

directories = PlatformDirs(
    appname=__package__,
    ensure_exists=True,
    opinion=True,
)

import os

# Fix cpu usage on glfw.swap_buffers when vsync is off and the gpu is overwhelmed
# https://forums.developer.nvidia.com/t/glxswapbuffers-gobbling-up-a-full-cpu-core-when-vsync-is-off/156635
# https://forums.developer.nvidia.com/t/gl-yield-and-performance-issues/27736
os.environ.setdefault("__GL_YIELD", "USLEEP")

# Fix cpu usage in medium-sized numpy matrix multiplications
# Warn: For PyTorch CPU set `torch.set_num_threads(multiprocessing.cpu_count())`
# https://github.com/numpy/numpy/issues/18669#issuecomment-820510379
os.environ.setdefault("OMP_NUM_THREADS", "1")
