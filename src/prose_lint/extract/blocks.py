"""Block structure: split Markdown-like lines into prose segments.

Markdown files use this parser directly. Comment extractors strip their
comment markers first and then hand the remaining lines to the same parser,
so a doc comment with a fenced example or a bullet list splits the same way
a Markdown file does.
"""

from __future__ import annotations

import re

from ..ptext import PText, join_lines
from ..segment import DIRECTIVE_RE, HEADING, PARAGRAPH, TABLE_CELL, Extracted, Segment, find_directives
from .inline import CODE_SPAN_RE, MARKDOWN, clean_inline

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:\s+|$)")
ATX_CLOSE_RE = re.compile(r"\s+#+\s*$")
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)\s*$")
THEMATIC_RE = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])(\s+|$)(\[[ xX]\]\s+)?")
QUOTE_RE = re.compile(r"^ {0,3}>\s?")
LINK_DEF_RE = re.compile(r"^ {0,3}\[[^\]^]+\]:\s*\S")
FOOTNOTE_DEF_RE = re.compile(r"^ {0,3}\[\^[^\]]+\]:\s*")
TABLE_DELIM_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
RAW_HTML_OPEN_RE = re.compile(r"^\s*<(pre|script|style|textarea)\b", re.I)
HTML_COMMENT_OPEN_RE = re.compile(r"<!--")
HTML_COMMENT_CLOSE_RE = re.compile(r"-->")
DIRECTIVE_TEXT_RE = re.compile(r"prose-lint:\s*ignore.*$")
# A line made only of punctuation is decoration (``-----``, ``*****``).
DECORATION_RE = re.compile(r"^[\s\W_]*$")


def _lstrip(pt: PText, n: int) -> PText:
    return pt.slice(n, len(pt))


def parse_blocks(
    lines: list[PText],
    *,
    dialect: str = MARKDOWN,
    indented_code: bool = True,
    front_matter: bool = False,
    out: Extracted | None = None,
    one_block: bool = False,
) -> Extracted:
    """Parse ``lines`` into segments and add them to ``out``.

    With ``one_block``, all segments form one block for suppression comments;
    the comment extractors use it so that a directive covers the whole comment.
    """
    out = out if out is not None else Extracted()
    shared = out.new_block() if one_block else None

    def block() -> int:
        return shared if shared is not None else out.new_block()

    para: list[PText] = []
    para_kind = PARAGRAPH
    fence: str | None = None
    raw_html: str | None = None
    in_comment = False
    in_list = False
    list_indent = 0
    in_table = False
    table_block = 0
    prev_blank = True

    def flush(kind: str | None = None) -> None:
        nonlocal para, para_kind
        if para:
            _emit(out, para, kind or para_kind, dialect, block())
        para = []
        para_kind = PARAGRAPH

    i = 0
    if front_matter and lines and lines[0].text.strip() == "---":
        i = 1
        while i < len(lines) and lines[i].text.strip() not in ("---", "..."):
            i += 1
        i += 1

    while i < len(lines):
        line = lines[i]
        lineno = line.pos_at(0)[0] if line.pos else None
        i += 1
        # Block quote markers go first, so a quoted fence or table is
        # recognized like an unquoted one.
        while QUOTE_RE.match(line.text):
            line = _lstrip(line, QUOTE_RE.match(line.text).end())
        text = line.text

        if fence is not None:
            stripped = text.strip()
            if stripped.startswith(fence[0] * len(fence)) and set(stripped) == {fence[0]}:
                fence = None
            continue
        if raw_html is not None:
            if re.search(rf"</{raw_html}\s*>", text, re.I):
                raw_html = None
            continue
        if lineno is not None:
            out.directives.extend(_directives(text, lineno, dialect, in_comment))
        if in_comment:
            m = HTML_COMMENT_CLOSE_RE.search(text)
            if not m:
                continue
            in_comment = False
            line = _lstrip(line, m.end())
            text = line.text

        # An HTML comment that opens on this line and does not close on it.
        opens = [m.start() for m in HTML_COMMENT_OPEN_RE.finditer(text)]
        if opens and not HTML_COMMENT_CLOSE_RE.search(text, opens[-1]):
            in_comment = True
            line = line.slice(0, opens[-1])
            text = line.text
        if dialect != MARKDOWN:
            line = line.replace(DIRECTIVE_TEXT_RE, lambda m: ("", False))
            text = line.text

        if not text.strip() or (
            dialect != MARKDOWN and DECORATION_RE.match(text) and len(text.strip()) >= 3
        ):
            flush()
            in_table = False
            prev_blank = True
            continue

        if FENCE_RE.match(text):
            flush()
            fence = FENCE_RE.match(text).group(1)
            prev_blank = False
            continue
        if RAW_HTML_OPEN_RE.match(text):
            flush()
            tag = RAW_HTML_OPEN_RE.match(text).group(1)
            if not re.search(rf"</{tag}\s*>", text, re.I):
                raw_html = tag
            continue

        indent = len(text) - len(text.lstrip(" "))
        if text.startswith("\t"):
            indent = 4
        # Indented code: four columns past the enclosing list item's content,
        # or past the margin outside a list, after a blank line.
        code_indent = list_indent + 4 if in_list else 4
        if indented_code and indent >= code_indent and prev_blank and not para:
            continue

        if in_table:
            _emit_table_row(out, line, dialect, table_block)
            continue
        if "|" in text and i < len(lines) and TABLE_DELIM_RE.match(lines[i].text) and "-" in lines[i].text:
            flush()
            table_block = block()
            _emit_table_row(out, line, dialect, table_block)
            i += 1
            in_table = True
            continue

        # A setext underline also matches the thematic break, so it goes first.
        m = SETEXT_RE.match(text)
        if m and para and not prev_blank:
            flush(HEADING)
            prev_blank = True
            continue
        if THEMATIC_RE.match(text):
            flush()
            prev_blank = True
            continue
        m = ATX_RE.match(text)
        if m:
            flush()
            body = _lstrip(line, m.end())
            cm = ATX_CLOSE_RE.search(body.text)
            if cm:
                body = body.slice(0, cm.start())
            para = [body]
            flush(HEADING)
            prev_blank = True
            continue
        if LINK_DEF_RE.match(text):
            flush()
            continue
        m = FOOTNOTE_DEF_RE.match(text)
        if m:
            flush()
            line = _lstrip(line, m.end())
        m = LIST_RE.match(line.text)
        if m and (m.group(3) or m.end() == len(line.text)):
            flush()
            in_list = True
            list_indent = len(m.group(1)) + len(m.group(2)) + max(1, min(len(m.group(3)), 4))
            line = _lstrip(line, m.end())
            if not line.text.strip():
                prev_blank = False
                continue
        elif prev_blank and indent < list_indent:
            in_list = False

        para.append(line)
        prev_blank = False

    flush()
    return out


DIRECTIVE_MENTION_RE = re.compile(r"[`'\"\u201c]\s*$")


def _directives(text: str, lineno: int, dialect: str, in_comment: bool):
    """Return the suppression directives on one line.

    In Markdown a directive counts only inside an HTML comment. In a code
    comment it counts anywhere, unless a backtick or a quote opens right before
    it, which marks a mention such as `prose-lint: ignore`.
    """
    if dialect != MARKDOWN:
        return [
            d
            for d, m in _directive_matches(text, lineno)
            if not DIRECTIVE_MENTION_RE.search(text[: m.start()])
        ]
    # Blank out code spans, so a directive quoted in inline code is a mention.
    text = CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)
    found = []
    pos = 0
    if in_comment:
        close = HTML_COMMENT_CLOSE_RE.search(text)
        end = close.start() if close else len(text)
        found += find_directives(text[:end], lineno)
        pos = end
    for m in re.finditer(r"<!--(.*?)(?:-->|$)", text[pos:]):
        found += find_directives(m.group(1), lineno)
    return found


def _directive_matches(text: str, lineno: int):
    for m in DIRECTIVE_RE.finditer(text):
        for d in find_directives(m.group(0), lineno):
            yield d, m


def _emit(out: Extracted, lines: list[PText], kind: str, dialect: str, block: int) -> None:
    stripped = [ln.strip() for ln in lines]
    raw = join_lines(ln for ln in stripped if ln.text)
    if not raw.text:
        return
    pt = clean_inline(raw, dialect).strip()
    if not pt.text or not any(c.isalpha() for c in pt.text):
        return
    first = raw.pos_at(0)[0]
    last = raw.pos_at(len(raw) - 1)[0]
    out.segments.append(Segment(kind, pt, first, last, block))


def _emit_table_row(out: Extracted, line: PText, dialect: str, block: int) -> None:
    text = line.text
    if TABLE_DELIM_RE.match(text):
        return
    # Split on pipes that are not escaped and not inside a code span.
    in_code = [False] * len(text)
    for m in CODE_SPAN_RE.finditer(text):
        in_code[m.start() : m.end()] = [True] * (m.end() - m.start())
    start = 0
    cells = []
    for j, ch in enumerate(text):
        if ch == "|" and not in_code[j] and (j == 0 or text[j - 1] != "\\"):
            cells.append(line.slice(start, j))
            start = j + 1
    cells.append(line.slice(start, len(text)))
    for cell in cells:
        if cell.text.strip():
            _emit(out, [cell], TABLE_CELL, dialect, block)
