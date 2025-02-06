import sys

from Broken import BrokenLauncher
from ShaderFlow import SHADERFLOW


class ShaderFlowApp(BrokenLauncher):
    def main(self):
        self.find_projects(tag="Scene")
        self.cli(*sys.argv[1:])

def main():
    ShaderFlowApp(PROJECT=SHADERFLOW)

if __name__ == "__main__":
    main()
