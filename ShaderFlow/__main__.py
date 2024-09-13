from Broken import BrokenApp
from ShaderFlow import SHADERFLOW


class ShaderFlowApp(BrokenApp):
    def main(self):
        self.find_projects(tag="Scene")
        self.typer()

def main():
    ShaderFlowApp(PROJECT=SHADERFLOW)

if __name__ == "__main__":
    main()
