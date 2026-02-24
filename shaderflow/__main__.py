import contextlib
import sys

import shaderflow
from shaderflow.launcher import SceneLauncher


def main():
    app = SceneLauncher()
    app.common(package=shaderflow.package)
    app.cli(sys.argv[1:])

if __name__ == "__main__":
    main()
