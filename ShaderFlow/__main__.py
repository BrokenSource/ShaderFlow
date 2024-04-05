import re
import sys
from pathlib import Path
import time

from typer import Context


import Broken
from Broken.Base import (
    BrokenPath,
    BrokenPlatform,
    BrokenProfiler,
    BrokenTyper,
    apply,
)
from Broken.Logging import log
from Broken.Project import BrokenApp
from Broken.Spinner import BrokenSpinner
from ShaderFlow import SHADERFLOW

from Broken.Loaders.LoaderString import LoaderString

SHADERFLOW_ABOUT = """
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨

©️ Broken Source Software, AGPL-3.0-only License.
"""

class ShaderFlowManager(BrokenApp):
    def cli(self):
        self.broken_typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        start = time.perf_counter()
        with BrokenSpinner("Finding ShaderFlow Scenes"):
            self.find_all_scenes()
        log.info(f"Found ShaderFlow Scenes in {time.perf_counter() - start:.4f}s")
        self.broken_typer(sys.argv[1:], shell=Broken.RELEASE and BrokenPlatform.OnWindows)

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        direct = sys.argv[1] if (len(sys.argv) > 1) else ""
        files = set()

        # The user might point to a file or directory
        if (direct.endswith(".py")):
            files.add(BrokenPath(sys.argv.pop(1)))
        elif BrokenPath(direct, valid=True):
            files.update(BrokenPath(sys.argv.pop(1)).rglob("*.py"))
        else:
            files.update(SHADERFLOW.DIRECTORIES.REPOSITORY.glob("Community/**/*.py"))
            files.update(SHADERFLOW.RESOURCES.SCENES.rglob("*.py"))
            files.update(Path.cwd().glob("*.py"))

        # Add the files, exit if no scene was added
        if sum(apply(self.add_scene_file, files)) == 0:
            log.warning("No ShaderFlow Scenes found")
            exit(1)

    docscene = re.compile(r"class\s+(\w+)\s*\(.*?(?:Scene).*\):\s*(?:\"\"\"((?:\n|.)*?)\"\"\")?")
    """Matches any class that contains "Scene" on the inheritance and its docstring"""

    def add_scene_file(self, file: Path) -> bool:
        """Add classes that inherit from Scene from a file to the CLI"""

        # Must be a valid path with string content
        if not (file := BrokenPath(file, valid=True)):
            return False
        if not (code := LoaderString(file)):
            return False

        # Match all scenes and their optional docstrings
        for match in ShaderFlowManager.docscene.finditer(code):
            name, docstring = match.groups()

            def partial_run(file, name, code):
                def run_scene(ctx: Context):
                    SHADERFLOW.DIRECTORIES.CURRENT_SCENE = file.parent
                    try:
                        # Note: Point of trust transfer to the file the user is running
                        exec(compile(code, file.stem, "exec"), namespace := {})
                        scene = namespace[name]
                        instance = scene()
                        instance.cli(*ctx.args)
                    finally:
                        instance.destroy()
                return run_scene

            if ("pyapp" in str(file)):
                panel = "🎥 Built-in release ShaderScenes"
            else:
                panel = f"🎥 ShaderScenes at [bold]({file})[/bold]"

            # Create the command
            self.broken_typer.command(
                callable=partial_run(file, name, code),
                name=name.lower(),
                help=(docstring or "No description available"),
                panel=panel,
                add_help_option=False,
                context=True,
            )

        return True

def main():
    with BrokenProfiler("SHADERFLOW"):
        SHADERFLOW.welcome()
        app = ShaderFlowManager()
        app.cli()

if __name__ == "__main__":
    main()
