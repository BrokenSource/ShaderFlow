import sys

from parsenaut._cyclopts import Launcher

import shaderflow


def main():
    app = Launcher(keyword="Scene")
    app.smart(package=shaderflow.package)
    app.cli(sys.argv[1:])

if __name__ == "__main__":
    main()
