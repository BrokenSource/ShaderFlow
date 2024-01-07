from ShaderFlow import *

SHADERFLOW_ABOUT = f"""
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨

©️  2023 Broken Source Software, AGPLv3-only License.
"""

class ShaderFlowCLI:
    def __init__(self):
        self.typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        self.find_all_scenes()
        self.typer(sys.argv[1:])

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        files  = set(SHADERFLOW.DIRECTORIES.PACKAGE.glob("**/*.py"))
        files |= set(Path.cwd().glob("**/*.py"))
        list(map(self.add_scene_file, files))

    def add_scene_file(self, file: Path) -> None:
        """Add classes that inherit from SombreroScene from a file to the CLI"""
        file = BrokenPath.true_path(file)

        # Skip hidden directories
        if ("__" in str(file)):
            return

        # Find all class definition inheriting from SombreroScene
        classes = []

        try:
            parsed = ast.parse(file.read_text())
        except Exception as e:
            log.error(f"Failed to parse file [{file}]: {e}")
            return

        for node in ast.walk(parsed):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                if not isinstance(base, ast.Name):
                    continue
                if base.id != SombreroScene.__name__:
                    continue
                classes.append(node)

        # Skip files without SombreroScene classes
        if not classes:
            return

        # Execute the file to get the classes, output to namespace dictionary
        # NOTE: This is a dangerous operation, scene files should be trusted
        try:
            exec(compile(file.read_text(), file.stem, 'exec'), namespace := {})
        except Exception as e:
            log.error(f"Failed to execute file [{file}]: {e}")
            return

        # Find all scenes on the compiled namespace
        for scene in namespace.values():
            if not isinstance(scene, type):
                continue
            if SombreroScene not in scene.__bases__:
                continue

            # "Decorator"-like function to create a function that runs the scene
            def run_scene_template(scene: SombreroScene):
                def run_scene(ctx: typer.Context):
                    log.info(f"Running SombreroScene ({scene.__name__})")
                    SHADERFLOW.DIRECTORIES.CURRENT_SCENE = file.parent
                    instance = scene()
                    instance.cli(*ctx.args)
                return run_scene

            # Create the command
            self.typer.command(
                callable=run_scene_template(scene),
                name=scene.__name__.lower(),
                help=f"{scene.__doc__ or ''}",
                panel=f"🎥 Sombrero Scenes at file [bold]({file})[/bold]",
                add_help_option=False,
                context=True,
            )

def main():
    with BrokenProfiler("SHADERFLOW"):
        ShaderFlowCLI()

if __name__ == "__main__":
    main()
