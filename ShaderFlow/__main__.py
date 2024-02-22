from ShaderFlow import *

SHADERFLOW_ABOUT = f"""
🌵 Imagine ShaderToy, on a Manim-like architecture. That's ShaderFlow.\n
• Tip: run "shaderflow (scene) --help" for More Options ✨

©️ Broken Source Software, AGPLv3-only License.
"""

class ShaderFlow(BrokenApp):
    def cli(self):
        self.broken_typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        self.find_all_scenes()
        self.broken_typer(sys.argv[1:], shell=BROKEN_RELEASE and BrokenPlatform.OnWindows)

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        with halo.Halo(text="Finding SombreroScenes"):
            files  = set(SHADERFLOW.RESOURCES.SCENES.glob("**/*.py"))
            files |= set(Path.cwd().glob("**/*.py"))
            list(map(self.add_scene_file, files))

    def add_scene_file(self, file: Path) -> None:
        """Add classes that inherit from SombreroScene from a file to the CLI"""
        if not (file := BrokenPath(file, valid=True)):
            return
        code = file.read_text()

        # Skip hidden directories
        if ("__" in str(file)):
            return

        # Substrings "ShaderFlow" and "SombreroScene" must be present
        if not all(substring in code for substring in ("ShaderFlow", "SombreroScene")):
            return

        # Find all class definition inheriting from SombreroScene
        classes = []

        try:
            parsed = ast.parse(code)
        except Exception as e:
            log.error(f"Failed to parse file ({file}): {e}")
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
            exec(compile(code, file.stem, "exec"), namespace := {})
        except Exception as e:
            log.error(f"Failed to execute file ({file}): {e}")
            return

        # Find all scenes on the compiled namespace
        for scene in namespace.values():
            if not isinstance(scene, type):
                continue
            if SombreroScene not in scene.__bases__:
                continue

            # "Decorator"-like function to create a function that runs the scene
            def run_scene_template(scene: SombreroScene):
                def run_scene(ctx: TyperContext):
                    SHADERFLOW.DIRECTORIES.CURRENT_SCENE = file.parent
                    instance = scene()
                    instance.cli(*ctx.args)
                return run_scene

            if BROKEN_RELEASE:
                panel = "🎥 Built-in release Sombrero Scenes"
            else:
                panel = f"🎥 Sombrero Scenes at file [bold]({file})[/bold]"

            # Create the command
            self.broken_typer.command(
                callable=run_scene_template(scene),
                name=scene.__name__.lower(),
                help=f"{scene.__doc__ or 'No description available'}",
                panel=panel,
                add_help_option=False,
                context=True,
            )

def main():
    with BrokenProfiler("SHADERFLOW"):
        SHADERFLOW.welcome()
        app = ShaderFlow()
        app.cli()

if __name__ == "__main__":
    main()
