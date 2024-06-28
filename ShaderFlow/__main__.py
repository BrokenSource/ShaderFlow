from Broken import BrokenApp
from ShaderFlow import SHADERFLOW

SHADERFLOW_ABOUT = """
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨
• Warn: Make sure you trust the File you are running

©️ Broken Source Software, AGPL-3.0 License.
"""

class ShaderFlowApp(BrokenApp):
    def main(self):
        self.typer.description = SHADERFLOW_ABOUT
        self.find_projects(tag="Scene")
        self.typer()

def main():
    ShaderFlowApp(PROJECT=SHADERFLOW)

if __name__ == "__main__":
    main()
