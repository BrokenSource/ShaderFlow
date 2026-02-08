from dearlog import logger # isort: split

import os
import importlib.metadata

__version__: str = importlib.metadata.version(__package__)
__about__:   str = "🔥 Modular shader engine designed for simplicity and speed"

# Warn: If using PyTorch CPU, set `torch.set_num_threads(multiprocessing.cpu_count())`
# Huge CPU usage for little to no speed up on matrix multiplication of NumPy's BLAS
# - https://github.com/numpy/numpy/issues/18669#issuecomment-820510379
os.environ.setdefault("OMP_NUM_THREADS", "1")

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
