from broken import BrokenProject, __version__

SHADERFLOW_ABOUT = """
🔥 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨
• Warn: Make sure you trust the file you are running!
"""

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=SHADERFLOW_ABOUT,
)
