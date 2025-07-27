from broken import BrokenProject, __version__

SHADERFLOW_ABOUT = "🔥 Modular shader engine designed for simplicity and speed"

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=SHADERFLOW_ABOUT,
)
