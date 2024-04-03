import ast
import sys
from pathlib import Path

from typer import Context

import Broken
from Broken.Base import (
    BrokenPath,
    BrokenPlatform,
    BrokenProfiler,
    BrokenTyper,
    apply,
)
from Broken.Loaders.LoaderString import LoaderString
from Broken.Logging import log
from Broken.Project import BrokenApp
from Broken.Spinner import BrokenSpinner
from ShaderFlow import SHADERFLOW
from ShaderFlow.Scene import ShaderScene

SHADERFLOW_ABOUT = """
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨

©️ Broken Source Software, AGPL-3.0-only License.
"""

class ShaderFlowManager(BrokenApp):
    def cli(self):
        self.broken_typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        with BrokenSpinner("Finding ShaderFlow Scenes"):
            self.find_all_scenes()
        self.broken_typer(sys.argv[1:], shell=Broken.RELEASE and BrokenPlatform.OnWindows)

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        direct = sys.argv[1] if (len(sys.argv) > 1) else ""
        files = set()

        # The user might point to a file or directory
        if (direct.endswith(".py")):
            files.add(BrokenPath(sys.argv.pop(1)))
        elif BrokenPath(direct, valid=True):
            files.update(BrokenPath(sys.argv.pop(1)).glob("**/*.py"))
        else:
            files.update(SHADERFLOW.DIRECTORIES.REPOSITORY.glob("Community/**/*.py"))
            files.update(SHADERFLOW.RESOURCES.SCENES.glob("**/*.py"))

        # Add the files, exit if no scene was added
        if sum(apply(self.add_scene_file, files)) == 0:
            log.warning("No ShaderFlow Scenes found")
            exit(1)

    def add_scene_file(self, file: Path) -> bool:
        """Add classes that inherit from Scene from a file to the CLI"""
        if not (file := BrokenPath(file, valid=True)):
            return False

        if not (code := LoaderString(file)):
            return False

        # Skip hidden directories
        if ("__" in str(file)):
            return False

        # Optimization: Only parse files with Scene on it
        if ("ShaderScene" not in code):
            return False

        # Find all class definition inheriting from Scene
        classes = []

        try:
            parsed = ast.parse(code)
        except Exception as e:
            log.error(f"Failed to parse file ({file}): {e}")
            return False

        for node in ast.walk(parsed):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                if not isinstance(base, ast.Name):
                    continue
                if base.id != ShaderScene.__name__:
                    continue
                classes.append(node)

        # No Scene class found
        if not classes:
            return False

        # Execute the file to get the classes, output to namespace dictionary
        # NOTE: This is a dangerous operation, scene files should be trusted
        try:
            exec(compile(code, file.stem, "exec"), namespace := {})
        except Exception as e:
            log.error(f"Failed to execute file ({file}): {e}")
            return False

        # Find all scenes on the compiled namespace
        for scene in namespace.values():
            if not isinstance(scene, type):
                continue
            if ShaderScene not in scene.__bases__:
                continue

            # "Decorator"-like function to create a function that runs the scene
            def partial_run(scene: ShaderScene):
                def run_scene(ctx: Context):
                    SHADERFLOW.DIRECTORIES.CURRENT_SCENE = file.parent
                    try:
                        instance = scene()
                        instance.cli(*ctx.args)
                    except BaseException as e:
                        raise e
                    finally:
                        instance.destroy()
                return run_scene

            if ("pyapp" in str(file)):
                panel = "🎥 Built-in release ShaderFlow Scenes"
            else:
                panel = f"🎥 ShaderFlow Scenes at file [bold]({file})[/bold]"

            # Create the command
            self.broken_typer.command(
                callable=partial_run(scene),
                name=scene.__name__.lower(),
                help=f"{scene.__doc__ or 'No description available'}",
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
