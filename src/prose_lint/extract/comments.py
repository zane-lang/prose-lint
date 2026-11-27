"""Comment extraction for source files.

Each lexer below reads string and character literals as well as comments, so
a comment marker inside a string (``"// not a comment"``) never starts a
comment. The lexers return raw comments; ``comments_to_segments`` groups
adjacent line comments, strips the markers and decoration, drops lines of
commented-out code and hands the rest to the block parser.
"""

from __future__ import annotations

import ast
import bisect
import io
import re
import tokenize
from dataclasses import dataclass

from ..ptext import PText
from ..segment import Extracted
from .blocks import parse_blocks
from .inline import COMMENT, DOCSTRING, OCAMLDOC


@dataclass
class RawComment:
    # "line" for a comment that runs to the end of its line, "block" for a
    # delimited comment, "docstring" for a Python docstring.
    style: str
    # Offsets into the source of the comment's content, without its markers.
    start: int
    end: int
    # True when only whitespace precedes the comment on its first line.
    own_line: bool
    # The marker character of a line comment ("/", "#", ";"), for grouping.
    marker: str = ""


class Source:
    def __init__(self, text: str) -> None:
        self.text = text
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_col(self, offset: int) -> tuple[int, int]:
        """Return the 1-based line and column of ``offset``."""
        i = bisect.bisect_right(self.line_starts, offset) - 1
        return i + 1, offset - self.line_starts[i] + 1

    def own_line(self, offset: int) -> bool:
        line, col = self.line_col(offset)
        start = self.line_starts[line - 1]
        return not self.text[start:offset].strip()

    def lines(self, start: int, end: int) -> list[PText]:
        """Split ``text[start:end]`` into one ``PText`` per source line."""
        out = []
        pos = start
        for part in self.text[start:end].split("\n"):
            line, col = self.line_col(pos)
            out.append(PText.from_source(part, line, col))
            pos += len(part) + 1
        return out


# ---------------------------------------------------------------- lexers


def _skip_string(src: str, i: int, quote: str, *, multiline: bool) -> int:
    """Return the offset after the string literal whose opening quote is at ``i``."""
    j = i + 1
    while j < len(src):
        ch = src[j]
        if ch == "\\":
            j += 2
            continue
        if ch == quote:
            return j + 1
        if ch == "\n" and not multiline:
            return j
        j += 1
    return j


C_CHAR_RE = re.compile(r"'(?:\\.[^'\n]{0,8}|[^\\'\n])'")
CPP_RAW_RE = re.compile(r'(?:u8|[uUL])?R"([^()\\ \t\n]{0,16})\(')


def lex_c(
    src: str, *, block_comments: bool = True, char_literals: bool = True, js: bool = False
) -> list[RawComment]:
    """Lex C and C++ (``block_comments``), Zane (line comments only) or JavaScript (``js``).

    JavaScript and TypeScript quote strings with ``'`` as well as ``"``, and
    template literals in backticks span lines.
    """
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == '"':
            i = _skip_string(src, i, '"', multiline=False)
        elif js and ch == "'":
            i = _skip_string(src, i, "'", multiline=False)
        elif js and ch == "`":
            i = _skip_string(src, i, "`", multiline=True)
        elif js and ch in "uULR":
            i += 1
        elif ch == "'" and char_literals:
            m = C_CHAR_RE.match(src, i)
            i = m.end() if m else i + 1
        elif ch in "uULR" and char_literals and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] == "_")):
            m = CPP_RAW_RE.match(src, i)
            if m:
                close = src.find(")" + m.group(1) + '"', m.end())
                i = n if close < 0 else close + len(m.group(1)) + 2
            else:
                i += 1
        elif src.startswith("//", i):
            j = i
            while j < n and src[j] == "/":
                j += 1
            if j < n and src[j] == "!":
                j += 1
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(RawComment("line", j, end, s.own_line(i), "/"))
            i = end
        elif block_comments and src.startswith("/*", i):
            j = i + 2
            while j < n and src[j] in "*!":
                j += 1
            close = src.find("*/", i + 2)
            end = n if close < 0 else close
            # ``/**/`` closes at once; the content is then empty.
            j = min(j, end)
            out.append(RawComment("block", j, end, s.own_line(i)))
            i = n if close < 0 else close + 2
        else:
            i += 1
    return out


OCAML_CHAR_RE = re.compile(
    r"'(?:[^\\'\n]|\\(?:[\\'\"ntbr ]|[0-9]{3}|x[0-9a-fA-F]{2}|o[0-7]{3}|u\{[0-9a-fA-F]+\}))'"
)
OCAML_QUOTED_RE = re.compile(r"\{([a-z_]*)\|")


def lex_ocaml(src: str) -> list[RawComment]:
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == '"':
            i = _skip_string(src, i, '"', multiline=True)
        elif ch == "'":
            m = OCAML_CHAR_RE.match(src, i)
            i = m.end() if m else i + 1
        elif ch == "{" and OCAML_QUOTED_RE.match(src, i):
            m = OCAML_QUOTED_RE.match(src, i)
            close = src.find("|" + m.group(1) + "}", m.end())
            i = n if close < 0 else close + len(m.group(1)) + 2
        elif src.startswith("(*", i):
            start = i
            j = i + 2
            while j < n and src[j] == "*" and not src.startswith("*)", j):
                j += 1
            content = j
            depth = 1
            while j < n and depth:
                if src[j] == '"':
                    j = _skip_string(src, j, '"', multiline=True)
                elif src.startswith("(*", j):
                    depth += 1
                    j += 2
                elif src.startswith("*)", j):
                    depth -= 1
                    j += 2
                elif src[j] == "{" and OCAML_QUOTED_RE.match(src, j):
                    m = OCAML_QUOTED_RE.match(src, j)
                    close = src.find("|" + m.group(1) + "}", m.end())
                    j = n if close < 0 else close + len(m.group(1)) + 2
                else:
                    j += 1
            end = j - 2 if depth == 0 else n
            out.append(RawComment("block", content, max(content, end), s.own_line(start)))
            i = j
        else:
            i += 1
    return out


def lex_hash(src: str, *, toml: bool = False) -> list[RawComment]:
    """Lex ``#`` comments (shell, TOML, YAML, Makefile and similar files).

    A ``#`` starts a comment at the start of a line or after whitespace.
    Quotes are tracked within one line only, because an apostrophe in a
    YAML or shell word would otherwise swallow the rest of the file. TOML
    triple-quoted strings span lines and are tracked across them.
    """
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    if src.startswith("#!"):
        i = src.find("\n")
        i = n if i < 0 else i
    while i < n:
        ch = src[i]
        if toml and src.startswith("'''", i):
            close = src.find("'''", i + 3)
            i = n if close < 0 else close + 3
        elif toml and src.startswith('"""', i):
            i = _skip_toml_basic(src, i + 3)
        elif ch in "\"'":
            i = _skip_string(src, i, ch, multiline=False) if ch == '"' else _skip_single(src, i)
        elif ch == "#" and (i == 0 or src[i - 1].isspace()):
            j = i
            while j < n and src[j] == "#":
                j += 1
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(RawComment("line", j, end, s.own_line(i), "#"))
            i = end
        else:
            i += 1
    return out


def _skip_toml_basic(src: str, j: int) -> int:
    """Return the offset after a TOML multi-line basic string whose content starts at ``j``."""
    while j < len(src):
        if src[j] == "\\":
            j += 2
        elif src.startswith('"""', j):
            # A closing delimiter may carry up to two extra quotes: """"".
            j += 3
            while j < len(src) and src[j] == '"':
                j += 1
            return j
        else:
            j += 1
    return j


def _skip_single(src: str, i: int) -> int:
    """Skip a single-quoted string, or only the quote when it does not close on its line."""
    close = src.find("'", i + 1)
    newline = src.find("\n", i + 1)
    if close < 0 or (0 <= newline < close):
        return i + 1
    return close + 1


def lex_dune(src: str) -> list[RawComment]:
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == '"':
            i = _skip_string(src, i, '"', multiline=True)
        elif src.startswith("#|", i):
            close = src.find("|#", i + 2)
            end = n if close < 0 else close
            out.append(RawComment("block", i + 2, end, s.own_line(i)))
            i = n if close < 0 else close + 2
        elif ch == ";":
            j = i
            while j < n and src[j] == ";":
                j += 1
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(RawComment("line", j, end, s.own_line(i), ";"))
            i = end
        else:
            i += 1
    return out


def lex_python(src: str) -> list[RawComment]:
    s = Source(src)
    out: list[RawComment] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return lex_hash(src)
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        (row, col) = tok.start
        if row == 1 and tok.string.startswith("#!"):
            continue
        start = s.line_starts[row - 1] + col
        j = start
        while j < len(src) and src[j] == "#":
            j += 1
        out.append(RawComment("line", j, start + len(tok.string), s.own_line(start), "#"))
    out.extend(_python_docstrings(src, s, tokens))
    out.sort(key=lambda c: c.start)
    return out


STRING_PREFIX_RE = re.compile(r"[rRuUbBfF]*(\"\"\"|'''|\"|')")


def _python_docstrings(src: str, s: Source, tokens) -> list[RawComment]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if not body or not isinstance(body[0], ast.Expr):
            continue
        value = body[0].value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        start = _offset(src, s, value.lineno, value.col_offset)
        end = _offset(src, s, value.end_lineno, value.end_col_offset)
        # Adjacent literals ("""a""" "b") form one docstring; each literal
        # contributes its own content.
        for tok in tokens:
            if tok.type != tokenize.STRING:
                continue
            tstart = s.line_starts[tok.start[0] - 1] + tok.start[1]
            if not start <= tstart < end:
                continue
            m = STRING_PREFIX_RE.match(src, tstart)
            if not m:
                continue
            quote = m.group(1)
            out.append(RawComment("docstring", m.end(), tstart + len(tok.string) - len(quote), s.own_line(tstart)))
    return out


def _offset(src: str, s: Source, lineno: int, byte_col: int) -> int:
    """Convert an ``ast`` position (1-based line, UTF-8 byte column) to an offset."""
    start = s.line_starts[lineno - 1]
    end = src.find("\n", start)
    line = src[start : end if end >= 0 else len(src)]
    return start + len(line.encode("utf-8")[:byte_col].decode("utf-8", "ignore"))


LUA_LONG_RE = re.compile(r"\[(=*)\[")


def lex_lua(src: str) -> list[RawComment]:
    """Lex Lua: ``--`` line comments, ``--[[ ]]`` block comments and long strings.

    A long bracket may carry ``=`` signs (``--[==[ ... ]==]``); the closing
    bracket carries the same number.
    """
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    if src.startswith("#!"):
        i = src.find("\n")
        i = n if i < 0 else i
    while i < n:
        ch = src[i]
        if ch in "\"'":
            i = _skip_string(src, i, ch, multiline=False)
        elif ch == "[" and LUA_LONG_RE.match(src, i):
            m = LUA_LONG_RE.match(src, i)
            close = src.find("]" + m.group(1) + "]", m.end())
            i = n if close < 0 else close + len(m.group(1)) + 2
        elif src.startswith("--", i):
            m = LUA_LONG_RE.match(src, i + 2)
            if m:
                close = src.find("]" + m.group(1) + "]", m.end())
                end = n if close < 0 else close
                out.append(RawComment("block", m.end(), end, s.own_line(i)))
                i = n if close < 0 else close + len(m.group(1)) + 2
                continue
            j = i
            while j < n and src[j] == "-":
                j += 1
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(RawComment("line", j, end, s.own_line(i), "-"))
            i = end
        else:
            i += 1
    return out


LEAN_CHAR_RE = re.compile(r"'(?:\\(?:[\\'\"nrt0]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4})|[^\\'\n])'")
LEAN_RAW_RE = re.compile(r'r(#*)"')


def lex_lean(src: str) -> list[RawComment]:
    """Lex Lean 4: ``--`` line comments and nested ``/- -/`` block comments.

    Doc comments (``/-- -/``) and module docs (``/-! -/``) are block comments
    whose markers the lexer strips. A ``'`` inside an identifier (``h'``)
    starts no character literal.
    """
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        prev = src[i - 1] if i else ""
        if ch == '"':
            i = _skip_string(src, i, '"', multiline=True)
        elif ch == "r" and not (prev.isalnum() or prev in "_'.") and LEAN_RAW_RE.match(src, i):
            m = LEAN_RAW_RE.match(src, i)
            close = src.find('"' + m.group(1), m.end())
            i = n if close < 0 else close + 1 + len(m.group(1))
        elif ch == "'" and not (prev.isalnum() or prev in "_'.") and LEAN_CHAR_RE.match(src, i):
            i = LEAN_CHAR_RE.match(src, i).end()
        elif src.startswith("/-", i):
            start = i
            j = i + 2
            while j < n and src[j] in "-!" and not src.startswith("-/", j):
                j += 1
            content = j
            depth = 1
            while j < n and depth:
                if src.startswith("/-", j):
                    depth += 1
                    j += 2
                elif src.startswith("-/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            end = j - 2 if depth == 0 else n
            out.append(RawComment("block", content, max(content, end), s.own_line(start)))
            i = j
        elif src.startswith("--", i):
            j = i
            while j < n and src[j] == "-":
                j += 1
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(RawComment("line", j, end, s.own_line(i), "-"))
            i = end
        else:
            i += 1
    return out


ASTRO_FENCE_RE = re.compile(r"\A---[ \t]*\n(.*?\n)?---[ \t]*(?:\n|\Z)", re.S)
ASTRO_RAW_RE = re.compile(r"<(script|style)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)


def _shifted(comments: list[RawComment], offset: int) -> list[RawComment]:
    for c in comments:
        c.start += offset
        c.end += offset
    return comments


def lex_astro(src: str) -> list[RawComment]:
    """Lex an Astro component.

    The ``---`` fenced frontmatter and each ``<script>`` and ``<style>``
    element hold JavaScript, TypeScript or CSS, which the JavaScript lexer
    reads. The template between them holds HTML comments (``<!-- -->``)
    and JSX-style comments in expressions (``{/* */}``).
    """
    s = Source(src)
    out: list[RawComment] = []
    i, n = 0, len(src)
    m = ASTRO_FENCE_RE.match(src)
    if m:
        if m.group(1):
            out.extend(_shifted(lex_c(m.group(1), js=True), m.start(1)))
        i = m.end()
    while i < n:
        if src.startswith("<!--", i):
            close = src.find("-->", i + 4)
            end = n if close < 0 else close
            out.append(RawComment("block", i + 4, end, s.own_line(i)))
            i = n if close < 0 else close + 3
        elif src.startswith("{/*", i):
            close = src.find("*/", i + 3)
            end = n if close < 0 else close
            out.append(RawComment("block", i + 3, end, s.own_line(i)))
            i = n if close < 0 else close + 2
        elif src[i] == "<" and ASTRO_RAW_RE.match(src, i):
            r = ASTRO_RAW_RE.match(src, i)
            out.extend(_shifted(lex_c(r.group(2), js=True), r.start(2)))
            i = r.end()
        else:
            i += 1
    return out


# ------------------------------------------------------------- cleanup

# Tool pragmas and file headers that are not prose.
PRAGMA_RE = re.compile(
    r"^\s*(?:noqa|type:\s|pragma\b|pylint:|fmt:|isort:|mypy:|ruff:|eslint|prettier-|clang-format"
    r"|NOLINT|-\*-|SPDX-|vim?:|@ts-|istanbul\b|shellcheck\b|cspell:|codespell:|ocamlformat\b"
    r"|Copyright\b|\(c\)\s)",
    re.I,
)

CODE_END_RE = re.compile(r"(?:[;{]|\{\s*\}|\bthen|\bdo|\bbegin|=>|->|:=)\s*$")
CODE_ONLY_CLOSER_RE = re.compile(r"^\s*(?:[}\])]+[;,)]*|end|done|fi|esac|in)\s*$")
CODE_START_RE = re.compile(
    r"^\s*(?:#\s*(?:include|define|ifn?def|if|endif|pragma)\b|import\s+[\w.]+\s*;?$|from\s+[\w.]+\s+import\b"
    r"|def\s+\w+\s*\(|class\s+\w+\s*[:(]|return\b.*[;)]\s*$|let\s+(?:rec\s+)?\w+.*=|fn\s+\w+\s*[(<]"
    r"|func\s+\w+\s*\(|(?:var|const|val|auto|int|char|void|static)\s+\w+\s*[=;(\[]"
    r"|(?:if|for|while|switch)\s*\(|}\s*else\b|elif\b.*:$|else\s*:$|printf\s*\(|print\s*\("
    r"|console\.\w+\(|\$\s+\w|>>>\s|\.\.\.\s)"
)
ASSIGN_RE = re.compile(r"^\s*[\w.\[\]\"'>-]+\s*(?:=|:=|\+=|-=|\*=|/=|\|=)\s*\S")
CALL_RE = re.compile(r"^\s*[\w.:>-]+\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*[;,]?\s*$")
WORD_RUN_RE = re.compile(r"(?:\b[A-Za-z][a-z']*\b[,]?\s+){4,}[A-Za-z]")
SYMBOLS = set("{}()[];=<>+*/&|^%$\\")


def looks_like_code(text: str) -> bool:
    """Guess whether one comment line is commented-out code."""
    t = text.strip()
    if not t:
        return False
    if CODE_ONLY_CLOSER_RE.match(t) or CODE_START_RE.match(t) or CALL_RE.match(t):
        return True
    has_prose = bool(WORD_RUN_RE.search(t))
    if CODE_END_RE.search(t) and not (has_prose and t.endswith(("do", "then", "begin"))):
        return not has_prose or t.endswith((";", "{"))
    if ASSIGN_RE.match(t) and not has_prose:
        return True
    non_space = [c for c in t if not c.isspace()]
    symbols = sum(1 for c in non_space if c in SYMBOLS)
    return not has_prose and symbols / len(non_space) > 0.25


def _dedent(lines: list[PText], skip_first: bool) -> list[PText]:
    rest = lines[1:] if skip_first else lines
    indents = [len(ln.text) - len(ln.text.lstrip()) for ln in rest if ln.text.strip()]
    cut = min(indents) if indents else 0
    out = []
    for k, ln in enumerate(lines):
        if skip_first and k == 0:
            out.append(ln.strip())
        else:
            lead = len(ln.text) - len(ln.text.lstrip())
            out.append(ln.slice(min(cut, lead), len(ln)))
    return out


STAR_PREFIX_RE = re.compile(r"^\s*\*(?![*)/])\s?")
TRAILING_STARS_RE = re.compile(r"\s*\*+\s*$")


def _block_lines(s: Source, c: RawComment) -> list[PText]:
    lines = s.lines(c.start, c.end)
    if len(lines) > 1:
        rest = [ln for ln in lines[1:] if ln.text.strip()]
        if rest and all(STAR_PREFIX_RE.match(ln.text) or ln.text.strip() == "*" for ln in rest):
            lines = [lines[0]] + [
                ln.slice(STAR_PREFIX_RE.match(ln.text).end(), len(ln))
                if STAR_PREFIX_RE.match(ln.text)
                else PText()
                for ln in lines[1:]
            ]
    last = lines[-1]
    m = TRAILING_STARS_RE.search(last.text)
    if m:
        lines[-1] = last.slice(0, m.start())
    return _dedent(lines, skip_first=True)


OCAML_BLOCK_OPEN_RE = re.compile(r"\{\[|\{v\s|\{v$")


def _drop_ocaml_code_blocks(lines: list[PText]) -> list[PText]:
    """Drop ``{[ ... ]}`` and ``{v ... v}`` regions that span lines."""
    out: list[PText] = []
    closer: str | None = None
    for ln in lines:
        if closer is not None:
            k = ln.text.find(closer)
            if k < 0:
                out.append(PText())
                continue
            ln = ln.slice(k + len(closer), len(ln))
            closer = None
        m = OCAML_BLOCK_OPEN_RE.search(ln.text)
        if m:
            want = "]}" if m.group(0).startswith("{[") else "v}"
            if ln.text.find(want, m.end()) < 0:
                closer = want
                ln = ln.slice(0, m.start())
        out.append(ln)
    return out


DOC_SECTION_RE = re.compile(
    r"^\s*(?:Args|Arguments|Parameters|Params|Returns?|Yields?|Raises|Exceptions|Examples?|Notes?"
    r"|Attributes|See Also|References|Warnings?|Todo|Methods|Other Parameters|Keyword Arguments)\s*:?\s*$"
)
DOC_ARG_RE = re.compile(r"^\s*\*{0,2}[A-Za-z_]\w*(?:\s*\([^)]*\))?\s*:\s+")
DOCTEST_RE = re.compile(r"^\s*(?:>>>|\.\.\.)(?:\s|$)")


def _docstring_lines(lines: list[PText]) -> list[PText]:
    """Drop doctest examples and literal blocks; split argument lists into items."""
    out: list[PText] = []
    in_doctest = False
    literal_indent: int | None = None
    for ln in lines:
        text = ln.text
        indent = len(text) - len(text.lstrip())
        if literal_indent is not None:
            if not text.strip() or indent > literal_indent:
                out.append(PText())
                continue
            literal_indent = None
        if DOCTEST_RE.match(text):
            in_doctest = True
            out.append(PText())
            continue
        if in_doctest:
            if text.strip():
                out.append(PText())
                continue
            in_doctest = False
        if DOC_SECTION_RE.match(text):
            out.append(PText())
            continue
        m = DOC_ARG_RE.match(text)
        if m:
            out.append(PText())
            ln = ln.slice(m.end(), len(ln))
        if ln.text.rstrip().endswith("::"):
            literal_indent = indent
            stripped = ln.text.rstrip()
            ln = ln.slice(0, len(stripped) - 1)
        out.append(ln)
    return out


# A JSDoc or LuaLS annotation line (``@param name the name``) documents a
# signature in a fixed syntax, not a sentence.
TAG_LINE_RE = re.compile(r"^\s*@[A-Za-z]")


def comments_to_segments(src: str, comments: list[RawComment], dialect: str, *, tags: bool = False) -> Extracted:
    s = Source(src)
    out = Extracted()
    groups: list[list[RawComment]] = []
    for c in comments:
        if c.style == "line" and groups and groups[-1][-1].style == "line":
            prev = groups[-1][-1]
            if (
                prev.marker == c.marker
                and prev.own_line == c.own_line
                and s.line_col(c.start)[0] == s.line_col(prev.start)[0] + 1
            ):
                groups[-1].append(c)
                continue
        groups.append([c])

    for group in groups:
        first = group[0]
        if first.style == "line":
            lines = [s.lines(c.start, c.end)[0] for c in group]
            lines = _dedent(lines, skip_first=False)
        else:
            lines = _block_lines(s, first)
        group_dialect = dialect
        if first.style == "docstring":
            lines = _docstring_lines(lines)
            group_dialect = DOCSTRING
        if dialect == OCAMLDOC:
            lines = _drop_ocaml_code_blocks(lines)
        cleaned = []
        for ln in lines:
            if PRAGMA_RE.match(ln.text) or looks_like_code(ln.text) or (tags and TAG_LINE_RE.match(ln.text)):
                cleaned.append(PText())
            else:
                cleaned.append(ln)
        parse_blocks(cleaned, dialect=group_dialect, indented_code=False, out=out, one_block=True)
    return out


def extract_comments(src: str, language: str) -> Extracted:
    if language == "ocaml":
        return comments_to_segments(src, lex_ocaml(src), OCAMLDOC)
    if language == "c":
        return comments_to_segments(src, lex_c(src), COMMENT)
    if language == "zane":
        return comments_to_segments(src, lex_c(src, block_comments=False, char_literals=False), COMMENT)
    if language == "python":
        return comments_to_segments(src, lex_python(src), COMMENT)
    if language == "hash":
        return comments_to_segments(src, lex_hash(src), COMMENT)
    if language == "toml":
        return comments_to_segments(src, lex_hash(src, toml=True), COMMENT)
    if language == "dune":
        return comments_to_segments(src, lex_dune(src), COMMENT)
    if language == "javascript":
        return comments_to_segments(src, lex_c(src, js=True), COMMENT, tags=True)
    if language == "lua":
        return comments_to_segments(src, lex_lua(src), COMMENT, tags=True)
    if language == "lean":
        return comments_to_segments(src, lex_lean(src), COMMENT)
    if language == "astro":
        return comments_to_segments(src, lex_astro(src), COMMENT, tags=True)
    raise ValueError(f"no comment lexer for language {language!r}")
