import itertools
from typing import Annotated

from cyclopts import App, Parameter


class CycloUtils:

    @staticmethod
    def chain(app: App) -> callable:
        """Implements known commands chaining in meta app"""
        def meta(*tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)]):
            if (splits := [n for (n, token) in enumerate(tokens) if token in app]):
                for start, end in itertools.pairwise(splits + [len(tokens)]):
                    app(tokens[start:end], result_action=app[tokens[start]].result_action)
                return None
            return app()
        app.meta.default(meta)
