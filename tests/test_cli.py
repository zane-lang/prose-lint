"""Exit codes, JSON output, configuration and determinism."""

import json
import subprocess
import sys
from pathlib import Path

from prose_lint.cli import main

BAD = "The text says so.\n"
WARN_ONLY = "The lexer reads numbers, strings, etc.\n"
GOOD = "The linker reports an error.\n"


def write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "bad.md", BAD)
    write(tmp_path, "warn.md", WARN_ONLY)
    write(tmp_path, "good.md", GOOD)
    assert main(["--no-config", "good.md"]) == 0
    assert main(["--no-config", "warn.md"]) == 0
    assert main(["--no-config", "bad.md"]) == 1
    assert main(["--no-config", "missing.md"]) == 2
    assert main(["--no-config", "--disable", "no-such-rule", "good.md"]) == 2


def test_text_format(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "docs/bad.md", BAD)
    main(["--no-config", "docs"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("docs/bad.md:1:10: personified-verb: ")


def test_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "bad.md", BAD + WARN_ONLY)
    assert main(["--no-config", "--json", "bad.md"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"] == {"files": 1, "errors": 2, "warnings": 1}
    first = data["findings"][0]
    assert set(first) == {"path", "line", "column", "end_line", "end_column", "rule", "severity", "message"}
    assert data["findings"][-1]["severity"] == "warn"


def test_config_disable_exclude_severity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "bad.md", BAD)
    write(tmp_path, "vendor/x.md", BAD)
    write(
        tmp_path,
        "prose-lint.toml",
        'disable = ["self-reference"]\nexclude = ["vendor"]\n\n'
        '[rules.personified-verb]\nseverity = "warn"\n',
    )
    assert main(["."]) == 0
    out = capsys.readouterr().out
    assert "vendor" not in out
    assert "self-reference" not in out
    assert "personified-verb" in out and "(warning)" in out
    assert main(["--enable", "self-reference", "."]) == 1


def test_pyproject_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "bad.md", BAD)
    write(tmp_path, "pyproject.toml", '[tool.prose-lint]\ndisable = ["personified-verb", "self-reference"]\n')
    assert main(["bad.md"]) == 0


def test_config_extends_word_lists(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "a.md", "The oracle decides the order.\n")
    assert main(["--no-config", "a.md"]) == 1
    write(tmp_path, "prose-lint.toml", '[rules.personified-verb]\nextra-agents = ["oracle"]\n')
    assert main(["a.md"]) == 0


def test_config_languages(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "a.rs", "// The flag decides the target.\nfn main() {}\n")
    assert main(["--no-config", "a.rs"]) == 2
    write(tmp_path, "prose-lint.toml", '[languages]\n".rs" = "c"\n')
    assert main(["a.rs"]) == 1


def test_bad_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "a.md", GOOD)
    write(tmp_path, "prose-lint.toml", 'disable = ["nope"]\n')
    assert main(["a.md"]) == 2
    assert "unknown rule 'nope'" in capsys.readouterr().err


def test_stdin(monkeypatch, capsys):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("// The flag decides the target.\n"))
    assert main(["--no-config", "--stdin-filename", "x.c", "-"]) == 1
    assert capsys.readouterr().out.startswith("x.c:1:13: personified-verb:")


def test_deterministic_across_processes(tmp_path):
    """Two separate processes, with the files in different orders, print the same findings."""
    root = Path(__file__).parent / "fixtures" / "languages"
    files = sorted(str(p) for p in root.iterdir() if not p.name.endswith(".expected"))
    cmd = [sys.executable, "-m", "prose_lint", "--no-config", "--json"]
    a = subprocess.run(cmd + files, capture_output=True, text=True, check=False).stdout
    b = subprocess.run(cmd + files[::-1], capture_output=True, text=True, check=False).stdout
    assert a and a == b


def test_explicit_file_respects_exclude(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "vendor/x.md", BAD)
    write(tmp_path, "prose-lint.toml", 'exclude = ["vendor"]\n')
    assert main(["vendor/x.md"]) == 0


def test_glob_character_class(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "docs/generated/3-old/a.md", BAD)
    write(tmp_path, "docs/keep.md", GOOD)
    write(tmp_path, "prose-lint.toml", 'exclude = ["docs/generated/[0-9]*/**"]\n')
    assert main(["docs"]) == 0


def test_pyproject_non_table(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "a.md", GOOD)
    write(tmp_path, "pyproject.toml", '[tool]\nprose-lint = []\n')
    assert main(["--config", "pyproject.toml", "a.md"]) == 2
    assert "must be a table" in capsys.readouterr().err


def test_unreadable_directory(tmp_path, monkeypatch, capsys):
    import prose_lint.cli as cli

    monkeypatch.chdir(tmp_path)
    write(tmp_path, "docs/a.md", GOOD)
    real_walk = cli.os.walk

    def walk(top, onerror=None):
        onerror(PermissionError(13, "Permission denied", str(Path(top) / "locked")))
        yield from real_walk(top)

    monkeypatch.setattr(cli.os, "walk", walk)
    assert main(["--no-config", "docs"]) == 2
    assert "Permission denied" in capsys.readouterr().err
