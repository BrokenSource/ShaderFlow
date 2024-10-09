import sys

from broken import BrokenApp, BrokenProfiler
from shaderflow import SHADERFLOW


class ShaderFlowApp(BrokenApp):
    def main(self):
        self.find_projects(tag="Scene")
        self.typer(sys.argv[1:])

def main():
    with BrokenProfiler("SHADERFLOW"):
        ShaderFlowApp(project=SHADERFLOW)

if __name__ == "__main__":
    main()
