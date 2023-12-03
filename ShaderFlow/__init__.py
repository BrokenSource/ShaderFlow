from Broken import *

SHADERFLOW_DIRECTORIES = BrokenDirectories(__file__, "ShaderFlow")
SHADERFLOW_CONFIG      = BrokenDotmap(SHADERFLOW_DIRECTORIES.CONFIG/"ShaderFlow.toml")

from .Sombrero import *
