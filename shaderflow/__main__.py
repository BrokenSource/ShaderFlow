import sys

from broken.core.launcher import BrokenLauncher
from shaderflow import SHADERFLOW


class ShaderLauncher(BrokenLauncher):
    def main(self):
        self.find_projects(tag="Scene")
        self.cli(*sys.argv[1:])

def main():
    ShaderLauncher(PROJECT=SHADERFLOW).main()

if __name__ == "__main__":
    main()
