from Broken import *

SHADERFLOW_DIRECTORIES = BrokenDirectories(app_name="ShaderFlow", app_author="BrokenSource")
SHADERFLOW_DIRECTORIES.SCENES  = SHADERFLOW_DIRECTORIES.PACKAGE.parent/"Scenes"
SHADERFLOW_DIRECTORIES.SHADERS = SHADERFLOW_DIRECTORIES.RESOURCES/"Shaders"

from .Sombrero import *
