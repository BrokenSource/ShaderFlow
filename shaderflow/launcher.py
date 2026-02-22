import re
import runpy
from collections import deque
from pathlib import Path

import typer
from attrs import Factory, define
from typer import Typer

import shaderflow


@define
class SceneLauncher:
    cli: Typer = Factory(lambda: Typer(
        help=shaderflow.__about__,
        no_args_is_help=True,
        add_completion=False,
    ))

    tag: str = "Scene"
    """Search classes that contains 'tag' in their inheritance"""

    def common(self, package: Path=None) -> None:
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

    @property
    def regex(self) -> re.Pattern:
        return re.compile(
            r"^class\s+(\w+)\s*\(.*?(?:" + self.tag + r").*\):\s*(?:\"\"\"((?:\n|.)*?)\"\"\")?",
            re.MULTILINE
        )

    def search(self, script: Path) -> bool:
        if not (script := Path(script)).exists():
            return False

        def wrapper(script: Path, clsname: str):
            def run(ctx: typer.Context):
                # Warn: Point of trust transfer to the file the user is running
                runpy.run_path(script)[clsname]().cli(*ctx.args)
            return run

        # Match all projects and their optional docstrings
        matches = list(self.regex.finditer(script.read_text()))

        # Add a command for each match
        for match in matches:
            clsname, docstring = match.groups()
            self.cli.command(
                name=clsname.lower(),
                help=(docstring or "No description provided"),
                rich_help_panel=f"📦 {self.tag}s at ({script})",
                add_help_option=False,
                context_settings=dict(
                    allow_extra_args=True,
                    ignore_unknown_options=True,
                )
            )(wrapper(script, clsname))

        return bool(matches)
