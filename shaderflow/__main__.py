import contextlib
import sys
from pathlib import Path

import shaderflow
from shaderflow.launcher import SceneLauncher


def main():
    app = SceneLauncher()
    app.common(package=shaderflow.package)

    with contextlib.suppress(SystemExit):
        app.cli(sys.argv[1:])

if __name__ == "__main__":
    main()
