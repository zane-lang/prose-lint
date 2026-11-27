"""Turn a source file into prose segments.

``language_for`` maps a file name to a language, and ``extract`` returns the
prose segments of a file in that language.
"""

from __future__ import annotations

from pathlib import PurePath

from ..segment import Extracted
from .blocks import parse_blocks
from .comments import Source, extract_comments

LANGUAGES = ("markdown", "ocaml", "c", "zane", "python", "hash", "toml", "dune", "scheme", "nix", "javascript", "typescript", "lua", "lean", "astro")

EXTENSIONS = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".mll": "ocaml",
    ".c": "c",
    ".h": "c",
    ".cc": "c",
    ".cpp": "c",
    ".cxx": "c",
    ".hh": "c",
    ".hpp": "c",
    ".hxx": "c",
    ".zn": "zane",
    ".py": "python",
    ".pyi": "python",
    ".sh": "hash",
    ".bash": "hash",
    ".zsh": "hash",
    ".yml": "hash",
    ".yaml": "hash",
    ".mk": "hash",
    ".cmake": "hash",
    ".opam": "hash",
    ".toml": "toml",
    ".cr": "hash",
    ".nix": "nix",
    ".ps1": "hash",
    ".psm1": "hash",
    ".scm": "scheme",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "javascript",
    ".lua": "lua",
    ".lean": "lean",
    ".astro": "astro",
}

FILE_NAMES = {
    "dune": "dune",
    "dune-project": "dune",
    "dune-workspace": "dune",
    "Makefile": "hash",
    "GNUmakefile": "hash",
    "makefile": "hash",
    "justfile": "hash",
    "Justfile": "hash",
    ".justfile": "hash",
    "Dockerfile": "hash",
    "CMakeLists.txt": "hash",
}


def language_for(path: str, extra: dict[str, str] | None = None) -> str | None:
    """Return the language of ``path``, or ``None`` for a file prose-lint does not read.

    ``extra`` maps file extensions (``".rs"``) or file names (``"BUILD"``) to
    languages and takes precedence over the built-in tables.
    """
    p = PurePath(path)
    extra = extra or {}
    for key in (p.name, p.suffix.lower()):
        if key in extra:
            return extra[key]
    if p.name in FILE_NAMES:
        return FILE_NAMES[p.name]
    return EXTENSIONS.get(p.suffix.lower())


def extract(text: str, language: str) -> Extracted:
    if language == "markdown":
        s = Source(text)
        return parse_blocks(s.lines(0, len(text)), front_matter=True)
    return extract_comments(text, language)
