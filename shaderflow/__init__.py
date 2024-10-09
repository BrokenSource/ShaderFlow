import shaderflow.resources as resources
from broken import BrokenPath, BrokenProject

SHADERFLOW_ABOUT ="""
🔥 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨
• Warn: Make sure you trust the file you are running
"""

SHADERFLOW = BrokenProject(
    package=__file__,
    name="ShaderFlow",
    author="BrokenSource",
    resources=resources,
    about=SHADERFLOW_ABOUT,
)

BrokenPath.recreate(SHADERFLOW.directories.dump, echo=False)
