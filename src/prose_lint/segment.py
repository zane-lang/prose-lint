"""Prose blocks that the extractors hand to the rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ptext import PText

# Segment kinds. Sentence-shape rules skip headings and table cells, because
# those hold fragments rather than sentences.
PARAGRAPH = "paragraph"
HEADING = "heading"
TABLE_CELL = "table-cell"


@dataclass
class Segment:
    kind: str
    text: PText
    start_line: int
    end_line: int
    # Segments with the same block number form one block for suppression
    # comments: all cells of one table, or all paragraphs of one code comment.
    block: int = 0
    # Rule ids that a suppression comment turns off for this segment; ``None``
    # in the set stands for every rule.
    suppressed: set[str | None] = field(default_factory=set)


@dataclass(frozen=True)
class Directive:
    line: int
    # ``None`` turns off every rule.
    rules: frozenset[str] | None
    file_wide: bool


@dataclass
class Extracted:
    segments: list[Segment] = field(default_factory=list)
    directives: list[Directive] = field(default_factory=list)
    blocks: int = 0

    def new_block(self) -> int:
        self.blocks += 1
        return self.blocks


DIRECTIVE_RE = re.compile(
    r"prose-lint:\s*(?P<verb>ignore-file|ignore)\b(?P<rules>(?:[\s,]+[a-z][a-z0-9-]*)*)"
)


def find_directives(text: str, line: int) -> list[Directive]:
    """Return the suppression directives in one line of comment text."""
    found = []
    for m in DIRECTIVE_RE.finditer(text):
        ids = frozenset(r for r in re.split(r"[\s,]+", m.group("rules")) if r)
        found.append(Directive(line, ids or None, m.group("verb") == "ignore-file"))
    return found


def apply_directives(ex: Extracted) -> set[str | None]:
    """Attach each directive to its segment and return the file-wide rule set.

    A directive applies to the block whose lines contain it. A directive on
    a line of its own applies to the first block after it.
    """
    file_wide: set[str | None] = set()
    segs = sorted(ex.segments, key=lambda s: (s.start_line, s.end_line))
    for d in ex.directives:
        ids: set[str | None] = {None} if d.rules is None else set(d.rules)
        if d.file_wide:
            file_wide |= ids
            continue
        target = next((s for s in segs if s.start_line <= d.line <= s.end_line), None)
        if target is None:
            target = next((s for s in segs if s.start_line > d.line), None)
        if target is not None:
            for s in segs:
                if s.block == target.block:
                    s.suppressed |= ids
    return file_wide
