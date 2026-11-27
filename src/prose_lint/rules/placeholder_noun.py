"""placeholder-noun: a vague noun or a free relative clause in place of the
exact term ("a name", "the thing", "what it is", "what the step does")."""

from __future__ import annotations

from ..segment import Segment
from .base import ERROR, Hit, Rule, is_code
from .words import PLACEHOLDER_NOUNS, PLACEHOLDER_PRONOUNS

INDEFINITE = frozenset("a an some any another one".split())


class PlaceholderNoun(Rule):
    id = "placeholder-noun"
    severity = ERROR
    summary = "A placeholder noun or a free relative clause stands where the exact term belongs."

    def __init__(self, options=None):
        super().__init__(options)
        self.nouns = self.word_list("nouns", PLACEHOLDER_NOUNS)

    def check(self, sent, seg: Segment):
        question = sent.text.rstrip().endswith("?")
        for tok in sent:
            if is_code(seg, tok):
                continue
            low = tok.lower_
            lemma = tok.lemma_.lower()

            if low == "what" and tok.tag_ == "WP" and not question:
                clause = _clause(tok)
                yield Hit(
                    clause.start_char,
                    clause.end_char,
                    f'"{clause.text}" is a free relative clause; name the exact term instead, '
                    'such as "the element type" or "the verb\'s symbol"',
                )
            elif tok.pos_ == "NOUN" and lemma in self.nouns:
                np = _noun_phrase(tok)
                yield Hit(np.start_char, np.end_char, f'"{np.text}" is a placeholder; name the exact term')
            elif tok.pos_ == "PRON" and low in PLACEHOLDER_PRONOUNS or (
                tok.pos_ == "ADV" and low in PLACEHOLDER_PRONOUNS
            ):
                yield Hit(tok.idx, tok.idx + len(tok.text), f'"{tok.text}" is a placeholder; name the exact term')
            elif tok.pos_ == "NOUN" and lemma == "way" and _determiner(tok) in INDEFINITE:
                np = _noun_phrase(tok)
                yield Hit(np.start_char, np.end_char, f'"{np.text}" is a placeholder; name the method, step or option')
            elif tok.pos_ == "NOUN" and lemma == "name" and _bare(tok):
                np = _noun_phrase(tok)
                yield Hit(
                    np.start_char,
                    np.end_char,
                    f'"{np.text}" is a placeholder; name the kind of name, such as "an identifier" or "a field name"',
                )
            elif low in ("one", "ones") and tok.pos_ in ("NOUN", "PRON", "NUM") and _determiner(tok) in (
                "the",
                "which",
            ):
                np = _noun_phrase(tok)
                yield Hit(np.start_char, np.end_char, f'"{np.text}" is a placeholder; repeat the exact term')
            elif lemma == "kind" and tok.pos_ == "NOUN" and _possessed(tok) and not _has_of(tok):
                np = _noun_phrase(tok)
                yield Hit(np.start_char, np.end_char, f'"{np.text}" is a placeholder; name the kind')


def _clause(what):
    """Return the span of the free relative clause that ``what`` opens."""
    doc = what.doc
    head = what.head if what.head.i > what.i else what
    end = head.i
    for c in head.rights:
        if c.dep_ in ("conj", "cc", "punct", "appos", "parataxis", "advcl", "npadvmod"):
            break
        end = max(end, c.right_edge.i)
    while end > what.i and (doc[end].is_punct or doc[end].dep_ in ("cc", "punct")):
        end -= 1
    return doc[what.i : end + 1]


def _noun_phrase(tok):
    doc = tok.doc
    return doc[tok.left_edge.i : tok.i + 1]


def _determiner(tok) -> str:
    for c in tok.children:
        if c.dep_ in ("det", "predet") or (c.dep_ == "nummod" and c.lower_ == "one"):
            return c.lower_
    return ""


def _bare(tok) -> bool:
    """Report whether ``tok`` stands with only an indefinite article and no modifier."""
    if _determiner(tok) not in ("a", "an", "some", "any"):
        return False
    return not any(c.dep_ in ("compound", "amod", "prep", "acl", "relcl", "poss", "nmod") for c in tok.children)


def _possessed(tok) -> bool:
    return any(c.dep_ == "poss" for c in tok.children) or _determiner(tok) in ("the", "this", "that")


def _has_of(tok) -> bool:
    return any(c.dep_ == "prep" and c.lower_ == "of" for c in tok.children)
