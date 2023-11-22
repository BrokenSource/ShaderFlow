from Broken import *

# Simplify full module path for moderngl imgui integration
ModernglImguiIntegration = moderngl_window.integrations.imgui.ModernglWindowRenderer

# Directories
SHADERFLOW_DIRECTORIES         = BrokenDirectories(app_name="ShaderFlow")
SHADERFLOW_DIRECTORIES.SCENES  = SHADERFLOW_DIRECTORIES.PACKAGE/"Scenes"
SHADERFLOW_DIRECTORIES.SHADERS = SHADERFLOW_DIRECTORIES.RESOURCES/"Shaders"

# Configuration file
SHADERFLOW_CONFIG = BrokenDotmap(SHADERFLOW_DIRECTORIES.CONFIG/"ShaderFlow.toml")

from .Sombrero import *
