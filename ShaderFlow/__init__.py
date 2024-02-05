import os

import ShaderFlow.Resources as ShaderFlowResources

# -------------------------------------------------------------------------------------------------|
# Hack to install path dependencies at runtime.
while bool(os.environ.get("PYAPP", False)):
    try:
        import Broken
        break
    except ImportError:
        print("Installing path dependencies... (Any errors should be ok to ignore)")

    import importlib.resources
    import subprocess
    import sys

    # Fixme: Why PYAPP_PASS_LOCATION isn't passed on Linux?
    if os.name != "nt":
        sys.argv = sys.argv[1:]
        sys.argv.insert(0, sys.executable)

    # Pip acronym and install maybe required packages
    PIP = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]

    # Install bundled wheels.. in our wheel
    for wheel in (importlib.resources.files(ShaderFlowResources)/"Wheels").glob("*.whl"):
        subprocess.run(PIP + [str(wheel)])
    break
# -------------------------------------------------------------------------------------------------|

from Broken import *
from Broken.Optional.BrokenAudio import *

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    APP_AUTHOR="BrokenSource",
    RESOURCES=ShaderFlowResources,
)

# Reset the dump directory
BrokenPath.resetdir(SHADERFLOW.DIRECTORIES.DUMP, echo=False)

from .Sombrero import *
