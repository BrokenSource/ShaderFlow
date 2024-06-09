import re
import sys
from pathlib import Path

from typer import Context

from Broken import (
    BrokenApp,
    BrokenPath,
    BrokenProfiler,
    BrokenTyper,
    log,
)
from ShaderFlow import SHADERFLOW

SHADERFLOW_ABOUT = """
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨
• Warn: Make sure you trust the File you are running

©️ Broken Source Software, AGPL-3.0 License.
"""

class ShaderFlowApp(BrokenApp):
    def cli(self):
        self.broken_typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        self.find_all_scenes()
        self.broken_typer(sys.argv[1:])

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        direct = sys.argv[1] if (len(sys.argv) > 1) else ""
        files = set()

        # The user might point to a file or directory
        if (direct.endswith(".py")):
            files.add(Path(sys.argv.pop(1)))
        elif (len(sys.argv) > 1) and Path(sys.argv[1]).exists():
            files.update(Path(sys.argv.pop(1)).rglob("*.py"))
        else:
            files.update(SHADERFLOW.DIRECTORIES.REPOSITORY.glob("Community/**/*.py"))
            files.update(SHADERFLOW.RESOURCES.SCENES.rglob("*.py"))
            files.update(Path.cwd().glob("*.py"))

        # Add the files, exit if no scene was added
        if sum(map(self.add_scene_file, files)) == 0:
            log.warning("No ShaderFlow Scenes found")
            exit(1)

    docscene = re.compile(r"^class\s+(\w+)\s*\(.*?(?:Scene).*\):\s*(?:\"\"\"((?:\n|.)*?)\"\"\")?", re.MULTILINE)
    """Matches any valid Python class that contains "Scene" on the inheritance and its optional docstring"""

    def add_scene_file(self, file: Path) -> bool:
        """Add classes that inherit from Scene from a file to the CLI"""

        # Must be a valid path with string content
        if not (file := BrokenPath(file).valid()):
            return False
        if not (code := file.read_text(encoding="utf-8")):
            return False

        def partial_run(file, name, code):
            def run_scene(ctx: Context):
                # Note: Point of trust transfer to the file the user is running
                exec(compile(code, file, "exec"), namespace := {})
                scene = namespace[name]
                instance = scene()
                instance.cli(*ctx.args)
            return run_scene

        # Match all scenes and their optional docstrings
        for match in ShaderFlowApp.docscene.finditer(code):
            name, docstring = match.groups()
            self.broken_typer.command(
                target=partial_run(file, name, code),
                name=name.lower(),
                help=(docstring or "No description provided"),
                panel=f"🎥 ShaderScenes at [bold]({file})[/bold]",
                add_help_option=False,
                context=True,
            )

        return True

def main():
    with BrokenProfiler("SHADERFLOW"):
        shaderflow = ShaderFlowApp()
        shaderflow.cli()

if __name__ == "__main__":
    main()
