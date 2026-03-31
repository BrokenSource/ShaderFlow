import re
import runpy
import sys
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from attrs import Factory, define
from cyclopts import App, Parameter

import shaderflow

if TYPE_CHECKING:
    from shaderflow.scene import ShaderScene

@define
class SceneLauncher:
    cli: App = Factory(lambda: App(
        usage=f"{sys.argv[0]} <scene> --help",
        version=shaderflow.__version__,
        help=shaderflow.__about__,
        help_flags=[],
    ))

    def common(self, package: Path) -> None:
        search = deque()

        # Search all local files
        search.extend(Path.cwd().glob("*.py"))

        # Only scan local files when found
        if sum(map(self.search, search)):
            return None

        search.clear()

        # Search repository examples or projects
        if (package := Path(package)).exists():
            search.extend((package.parent/"examples").rglob("*.py"))
            search.extend((package.parent/"projects").rglob("*.py"))

        # Search bundled examples
        search.extend((package/"resources").rglob("*.py"))

        for path in search:
            self.search(path)

    def search(self, script: Path) -> bool:
        """Safe search classes without running script, add to cli"""

        def wrapper(script: Path, clsname: str):
            def run(*args: Annotated[str, Parameter(
                allow_leading_hyphen=True,
                show=False,
            )]):
                sys.argv[1:] = args

                # Warn: Point of trust transfer to the file the user is running
                scene: ShaderScene = runpy.run_path(str(script))[clsname]()
                scene.cli.meta(args)

            return run

        # Match all projects and their optional docstrings
        pattern = re.compile(r"^class\s+(\w+)\s*\(.*?(?:Scene).*\):\s*(?:\"\"\"((?:\n|.)*?)\"\"\")?", re.MULTILINE)
        matches = list(pattern.finditer(script.read_text()))

        # Add a command for each match
        for match in matches:
            clsname, docstring = match.groups()
            self.cli.command(
                wrapper(script, clsname),
                name=clsname.lower(),
                help=(docstring or "No description provided"),
                group=f"📦 Scenes at ({script})",
            )

        return bool(matches)
