# List the recipes.
default:
    @just --list

# Install the locked dependencies.
sync:
    uv sync --frozen

# Run the test suite.
test *args:
    uv run --frozen pytest {{args}}

# Rewrite the expected outputs of the golden tests.
golden:
    PROSE_LINT_UPDATE=1 uv run --frozen pytest tests/test_golden.py

# Check this repository's own prose.
prose:
    uv run --frozen prose-lint README.md justfile pyproject.toml src tests/conftest.py tests/test_cli.py tests/test_golden.py tests/test_rules.py

# Update uv.lock and the hashed requirements file for pip users.
lock:
    uv lock
    uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.lock
