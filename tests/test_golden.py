"""Golden tests: each fixture's expected output lives next to it in ``<name>.expected``.

Run ``PROSE_LINT_UPDATE=1 just test`` to rewrite the expected files after an
intended change, and review the diff.
"""

from pathlib import Path

import pytest

from prose_lint.cli import main

from conftest import UPDATE

ROOT = Path(__file__).parent
FIXTURES = sorted(p for p in (ROOT / "fixtures").rglob("*") if p.is_file() and p.suffix != ".expected")


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.relative_to(ROOT / "fixtures").as_posix())
def test_golden(fixture, capsys, monkeypatch):
    monkeypatch.chdir(ROOT / "fixtures")
    rel = fixture.relative_to(ROOT / "fixtures").as_posix()
    main(["--no-config", rel])
    out = capsys.readouterr().out
    expected = fixture.with_name(fixture.name + ".expected")
    if UPDATE:
        expected.write_text(out, encoding="utf-8")
    assert out == expected.read_text(encoding="utf-8")
