import ShaderFlow.Resources as ShaderFlowResources
from Broken import BrokenPath, BrokenProject

SHADERFLOW_ABOUT ="""
🔥 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨
• Warn: Make sure you trust the file you are running
"""

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
    ABOUT=SHADERFLOW_ABOUT,
)

BrokenPath.recreate(SHADERFLOW.DIRECTORIES.DUMP, echo=False)
