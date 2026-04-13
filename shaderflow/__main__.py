import sys

from parsenaut._cyclopts import Launcher

import shaderflow


def main():
    launcher = Launcher(keyword="Scene")
    launcher.smart(package=shaderflow.package)
    launcher.cli(sys.argv[1:])

if __name__ == "__main__":
    main()
