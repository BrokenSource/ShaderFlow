from ShaderFlow import *


class ShaderFlow(BrokenApp):
    def cli(self):
        self.broken_typer = BrokenTyper(description=SHADERFLOW_ABOUT)
        self.find_all_scenes()
        self.broken_typer(sys.argv[1:], shell=BROKEN_RELEASE and BrokenPlatform.OnWindows)

    def find_all_scenes(self) -> list[Path]:
        """Find all Scenes: Project directory and current directory"""
        direct = sys.argv.get(1) or ""
        files = set()

        # The user might point to a file or directory
        if (direct.endswith(".py")):
            files.add(BrokenPath(sys.argv.pop(1)))
        elif BrokenPath(direct, valid=True):
            files.update(BrokenPath(sys.argv.pop(1)).glob("**/*.py"))
        else:
            files.update(SHADERFLOW.RESOURCES.SCENES.glob("**/*.py"))

        # Add the files, exit if no scene was added
        if sum(list(map(self.add_scene_file, files))) == 0:
            log.warning("No ShaderFlow Scenes found")
            exit(1)

    def add_scene_file(self, file: Path) -> bool:
        """Add classes that inherit from ShaderFlowScene from a file to the CLI"""
        if not (file := BrokenPath(file, valid=True)):
            return False

        if not (code := BrokenPath.read_text(file)):
            return False

        # Skip hidden directories
        if ("__" in str(file)):
            return False

        # Optimization: Only parse files with ShaderFlowScene on it
        if not "ShaderFlowScene" in code:
            return False

        # Find all class definition inheriting from ShaderFlowScene
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
                if base.id != ShaderFlowScene.__name__:
                    continue
                classes.append(node)

        # No Scene class found
        if not classes:
            return

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
            if ShaderFlowScene not in scene.__bases__:
                continue

            # "Decorator"-like function to create a function that runs the scene
            def partial_run(scene: ShaderFlowScene):
                def run_scene(ctx: TyperContext):
                    SHADERFLOW.DIRECTORIES.CURRENT_SCENE = file.parent
                    instance = scene()
                    instance.cli(*ctx.args)
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
        app = ShaderFlow()
        app.cli()

if __name__ == "__main__":
    main()
