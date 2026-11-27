"""Text with a source position for every character.

The extractors rewrite source text heavily: they drop comment markers, code
spans and Markdown punctuation. ``PText`` carries, for each remaining
character, the 1-based line and column it came from, so a finding on the
cleaned text still reports the place in the original file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

Pos = tuple[int, int]


@dataclass
class PText:
    text: str = ""
    pos: list[Pos] = field(default_factory=list)
    code: list[bool] = field(default_factory=list)

    @classmethod
    def from_source(cls, text: str, line: int, col: int) -> "PText":
        """Build a PText for ``text`` that starts at ``line``:``col`` and spans one line."""
        return cls(text, [(line, col + i) for i in range(len(text))], [False] * len(text))

    def __len__(self) -> int:
        return len(self.text)

    def append(self, other: "PText") -> None:
        self.text += other.text
        self.pos.extend(other.pos)
        self.code.extend(other.code)

    def append_char(self, ch: str, pos: Pos, code: bool = False) -> None:
        self.text += ch
        self.pos.append(pos)
        self.code.append(code)

    def append_str(self, s: str, pos: Pos, code: bool = False) -> None:
        """Append ``s`` with every character mapped to the single position ``pos``."""
        self.text += s
        self.pos.extend([pos] * len(s))
        self.code.extend([code] * len(s))

    def slice(self, start: int, end: int) -> "PText":
        return PText(self.text[start:end], self.pos[start:end], self.code[start:end])

    def pos_at(self, i: int) -> Pos:
        if not self.pos:
            return (1, 1)
        return self.pos[min(max(i, 0), len(self.pos) - 1)]

    def group(self, m: re.Match[str], g: int | str) -> "PText":
        """Return the part of this text that group ``g`` of match ``m`` covers."""
        return self.slice(m.start(g), m.end(g))

    def strip(self) -> "PText":
        start, end = 0, len(self.text)
        while start < end and self.text[start].isspace():
            start += 1
        while end > start and self.text[end - 1].isspace():
            end -= 1
        return self.slice(start, end)

    def replace(
        self,
        pattern: re.Pattern[str],
        repl: Callable[[re.Match[str]], "tuple[str, bool] | PText | None"],
    ) -> "PText":
        """Replace every match of ``pattern``.

        ``repl`` returns one of three values: ``(replacement, is_code)``, whose
        characters all map to the position of the first matched character; a
        ``PText``, which keeps its own positions; or ``None``, which keeps the
        match unchanged.
        """
        out = PText()
        last = 0
        for m in pattern.finditer(self.text):
            r = repl(m)
            if r is None:
                continue
            out.append(self.slice(last, m.start()))
            if isinstance(r, PText):
                out.append(r)
            else:
                text, is_code = r
                out.append_str(text, self.pos_at(m.start()), is_code)
            last = m.end()
        out.append(self.slice(last, len(self.text)))
        return out


def join_lines(lines: Iterable[PText]) -> PText:
    """Join one-line texts with a newline that maps to the end of the previous line."""
    out = PText()
    first = True
    for ln in lines:
        if not first:
            if out.pos:
                line, col = out.pos[-1]
                out.append_char("\n", (line, col + 1))
            else:
                out.append_char("\n", ln.pos_at(0))
        out.append(ln)
        first = False
    return out
