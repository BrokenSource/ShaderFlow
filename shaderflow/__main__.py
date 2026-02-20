import sys

import shaderflow
from broken.launcher import BrokenLauncher
from broken.project import BrokenProject

SHADERFLOW = BrokenProject(
    PACKAGE=__file__,
    APP_NAME="ShaderFlow",
    ABOUT=shaderflow.__about__,
)

class ShaderLauncher(BrokenLauncher):
    def main(self):
        self.find_projects(tag="Scene")
        self.cli(*sys.argv[1:])

def main():
    ShaderLauncher(PROJECT=SHADERFLOW).main()

if __name__ == "__main__":
    main()
