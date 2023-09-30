from Broken import *

ModernglImguiIntegration = moderngl_window.integrations.imgui.ModernglWindowRenderer

# Directories
SHADERFLOW_DIRECTORIES = BrokenDirectories(app_name="ShaderFlow", app_author="BrokenSource")
SHADERFLOW_DIRECTORIES.SCENES  = SHADERFLOW_DIRECTORIES.PACKAGE.parent/"Scenes"
SHADERFLOW_DIRECTORIES.SHADERS = SHADERFLOW_DIRECTORIES.RESOURCES/"Shaders"

# Identifier for modules
SombreroHash = uuid.uuid4
SombreroScene = None

# isort: off
from .SombreroMessage import *
from .SombreroShader import *
from .SombreroModule import *
from .Modules import *
from .SombreroScene import *

# Make modules findable as property on the scene
SombreroModule.make_findable(SombreroContext)
