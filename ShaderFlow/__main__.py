import sys

from Broken import BrokenApp, BrokenProfiler
from ShaderFlow import SHADERFLOW


class ShaderFlowApp(BrokenApp):
    def main(self):
        self.find_projects(tag="Scene")
        self.typer(sys.argv[1:])

def main():
    with BrokenProfiler("SHADERFLOW"):
        ShaderFlowApp(PROJECT=SHADERFLOW)

if __name__ == "__main__":
    main()
