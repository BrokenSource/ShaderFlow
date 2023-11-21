from Broken import *

# Simplify full module path for moderngl imgui integration
ModernglImguiIntegration = moderngl_window.integrations.imgui.ModernglWindowRenderer

# Directories
SHADERFLOW_DIRECTORIES         = BrokenDirectories(app_name="ShaderFlow")
SHADERFLOW_DIRECTORIES.SCENES  = SHADERFLOW_DIRECTORIES.PACKAGE/"Scenes"
SHADERFLOW_DIRECTORIES.SHADERS = SHADERFLOW_DIRECTORIES.RESOURCES/"Shaders"

# Identifier for modules
SombreroID    = uuid.uuid4
SombreroScene = None

if (DETERMINISTIC_UUIDS := True):
    SombreroID = lambda: uuid.UUID(int=random.randint(0, 2**128))
    random.seed(0)

# isort: off
from .SombreroShader import *
from .SombreroModule import *
from .Modules import *
from .SombreroEngine import *
from .SombreroScene import *

# Make modules findable as property on the scene
SombreroModule.make_findable(SombreroContext)
SombreroModule.make_findable(SombreroEngine)
