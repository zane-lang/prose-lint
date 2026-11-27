"""The interface every rule implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..segment import Segment

ERROR = "error"
WARN = "warn"
SEVERITIES = (ERROR, WARN)


@dataclass(frozen=True)
class Hit:
    """A rule's report of one defect, as a character range in the segment text."""

    start: int
    end: int
    message: str


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    end_line: int
    end_column: int
    rule: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }


class Rule:
    id: str = ""
    severity: str = ERROR
    summary: str = ""
    # Segment kinds the rule reads; sentence-shape rules leave out headings
    # and table cells.
    kinds: frozenset[str] = frozenset({"paragraph", "heading", "table-cell"})

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self.options = options or {}

    def word_list(self, name: str, default: Iterable[str]) -> frozenset[str]:
        """Return a default word list, extended by ``extra-<name>`` from the configuration."""
        extra = self.options.get(f"extra-{name}", [])
        return frozenset(default) | frozenset(w.lower() for w in extra)

    def check(self, sent, seg: Segment) -> Iterable[Hit]:
        raise NotImplementedError


def is_code(seg: Segment, tok) -> bool:
    """Report whether a token came from a code span or another code token."""
    return any(seg.text.code[tok.idx : tok.idx + len(tok.text)])


def span_text(sent, start: int, end: int) -> str:
    """Return the text of tokens ``start`` to ``end`` (document indices, inclusive)."""
    doc = sent.doc
    return doc[start : end + 1].text
