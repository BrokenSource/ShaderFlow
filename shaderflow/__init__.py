from dearlog import logger # isort: split

import importlib.metadata

__version__: str = importlib.metadata.version(__package__)
__about__:   str = "🔥 Modular shader engine designed for simplicity and speed"

from broken.project import BrokenProject

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=__about__,
)
