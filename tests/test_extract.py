"""Extraction cases: code and mentions that must stay out of the prose, and prose that must stay in."""

import pytest

BAD = "The value decides the size."

QUIET = [
    # A directive inside a fenced example or an inline code span is a mention.
    ("markdown", "```md\n<!-- prose-lint: ignore-file -->\n```\n\n" + BAD + "\n", 1),
    ("markdown", "Write `<!-- prose-lint: ignore-file -->` to turn a file off.\n\n" + BAD + "\n", 1),
    # A fence inside a block quote.
    ("markdown", "> ```\n> " + BAD + "\n> ```\n", 0),
    # Indented code inside a list item, after a blank line.
    ("markdown", "- An item.\n\n      " + BAD + "\n", 0),
    ("markdown", "- An item.\n\n  " + BAD + "\n", 1),
    # A pipe inside a double-backtick code span does not split the cell.
    ("markdown", "| Code | Note |\n|---|---|\n| ``a | the value decides`` | Fine. |\n", 0),
    # Generic types stay as code; real HTML tags disappear.
    ("c", "// The function returns Option<thing> for a missing key.\nint f(void);\n", 0),
    ("c", "// The <b>value</b> decides the size.\nint f(void);\n", 1),
    # C++ raw strings with a prefix.
    ("c", 'const char *s = u8R"(// The value decides the size.)";\n', 0),
    ("c", 'const wchar_t *s = LR"x(/* The value decides the size. */)x";\n', 0),
    # An escaped triple quote does not end a TOML multi-line string.
    ("toml", 'a = """one \\""" # The value decides the size."""\n', 0),
    # Every literal of an implicitly concatenated docstring is read.
    ("python", '"""The flag decides the target. """ "The value decides the size."\n', 2),
]


@pytest.mark.parametrize("language,text,count", QUIET)
def test_extraction(lint, language, text, count):
    found = [f for f in lint(text, language) if f.rule == "personified-verb"]
    assert len(found) == count, [(f.line, f.column, f.message) for f in found]


def test_setext_heading_is_a_heading(lint):
    rules = {f.rule for f in lint("The case of a name says what it is\n---\n")}
    assert "self-reference" not in rules and "personified-verb" in rules


@pytest.mark.parametrize(
    "name,language",
    [
        ("init.lua", "lua"),
        ("Proof.lean", "lean"),
        ("Page.astro", "astro"),
        ("site.mjs", "javascript"),
        ("view.tsx", "javascript"),
        ("zane.cr", "hash"),
        ("flake.nix", "hash"),
        ("install.ps1", "hash"),
        ("highlights.scm", "dune"),
    ],
)
def test_language_for(name, language):
    from prose_lint.extract import language_for

    assert language_for(name) == language
