from Broken import *

# Simplify full module path for moderngl imgui integration
ModernglImguiIntegration = moderngl_window.integrations.imgui.ModernglWindowRenderer

# Directories
SHADERFLOW_DIRECTORIES         = BrokenDirectories(app_name="ShaderFlow")
SHADERFLOW_DIRECTORIES.SCENES  = SHADERFLOW_DIRECTORIES.PACKAGE/"Scenes"
SHADERFLOW_DIRECTORIES.SHADERS = SHADERFLOW_DIRECTORIES.RESOURCES/"Shaders"

# Configuration file
SHADERFLOW_CONFIG = BrokenDotmap(SHADERFLOW_DIRECTORIES.CONFIG/"ShaderFlow.toml")

# isort: off
from .SombreroShader import *
from .SombreroModule import *
from .Modules import *
from .SombreroEngine import *
from .SombreroScene import *

# Make modules findable as property on the scene
SombreroModule.make_findable(SombreroContext)
SombreroModule.make_findable(SombreroEngine)
