import importlib.metadata

from broken import BrokenProject

__version__ = importlib.metadata.version(__package__)

SHADERFLOW_ABOUT = "🔥 Modular shader engine designed for simplicity and speed"

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=SHADERFLOW_ABOUT,
)
