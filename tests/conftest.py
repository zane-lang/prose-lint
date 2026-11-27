import os

import pytest

from prose_lint.config import Config
from prose_lint.lint import lint_text, make_rules

UPDATE = os.environ.get("PROSE_LINT_UPDATE") == "1"


@pytest.fixture(scope="session")
def lint():
    rules = make_rules(Config())

    def run(text, language="markdown", path="t.md"):
        return lint_text(text, language, path, rules)

    return run
