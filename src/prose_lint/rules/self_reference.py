"""self-reference: a sentence that ends by pointing back at its own subject
("The case of a name says what it is", "The text says so", "many workers
doing the same thing")."""

from __future__ import annotations

from ..segment import PARAGRAPH, Segment
from .base import ERROR, Hit, Rule, is_code
from .words import PLACEHOLDER_NOUNS

TRAILING = frozenset(".!?;:,)]}\"'”’»…")
SINGULAR_PRONOUNS = frozenset("it itself".split())
PLURAL_PRONOUNS = frozenset("they them themselves".split())
# Words after a final pronoun that still leave the pronoun as the last content
# word: "what it is", "how it does", "as they are".
AUX_LEMMAS = frozenset("be do have can could will would shall should may might must".split())
PERSON_PRONOUNS = frozenset("i we you he she one".split())


class SelfReference(Rule):
    id = "self-reference"
    severity = ERROR
    summary = "The sentence ends on a pronoun or pro-form that points back at its own subject."
    kinds = frozenset({PARAGRAPH})

    def check(self, sent, seg: Segment):
        toks = [t for t in sent if not t.is_space]
        while toks and (toks[-1].is_punct or toks[-1].text in TRAILING):
            toks.pop()
        if len(toks) < 3:
            return
        last = toks[-1]
        low = last.lower_
        if is_code(seg, last):
            return

        # "says so", "does so"
        if low == "so" and toks[-2].pos_ in ("VERB", "AUX"):
            yield Hit(
                last.idx,
                last.idx + len(last.text),
                f'the sentence ends on "{toks[-2].text} so", which points back instead of stating the fact; '
                "state the fact itself",
            )
            return

        # "the same", "the same thing"
        same = _same_phrase(toks)
        if same is not None:
            start = same[0]
            yield Hit(
                start.idx,
                last.idx + len(last.text),
                f'the sentence ends on "{sent.doc[start.i : last.i + 1].text}", which points back at '
                "an earlier part of the sentence; name the step or value itself",
            )
            return

        # A clause that ends on its own pronoun subject: "says what it is",
        # "shows whether they are". An object pronoun ("closes it") usually
        # points at the previous sentence and does not count.
        k = len(toks) - 1
        while k > 0 and toks[k].lemma_.lower() in AUX_LEMMAS and toks[k].pos_ in ("AUX", "VERB"):
            k -= 1
        pron = toks[k]
        plow = pron.lower_
        if plow not in SINGULAR_PRONOUNS | PLURAL_PRONOUNS or k == len(toks) - 1:
            return
        if pron.dep_ not in ("nsubj", "nsubjpass") or pron.head.dep_ == "ROOT":
            return
        subject = _main_subject(sent)
        if subject is None or subject.lower_ in PERSON_PRONOUNS:
            return
        if not _agrees(pron, subject):
            return
        # A noun of the same number between the subject and the pronoun is the
        # more likely antecedent ("The parser reads the file and closes it").
        sub_end = subject.right_edge.i
        for t in sent.doc[sub_end + 1 : pron.i]:
            if t.pos_ in ("NOUN", "PROPN") and _agrees(pron, t):
                return
        subj_text = sent.doc[subject.left_edge.i : subject.right_edge.i + 1].text
        yield Hit(
            pron.idx,
            last.idx + len(last.text),
            f'the sentence ends on "{sent.doc[pron.i : last.i + 1].text}", which points back at '
            f'its own subject "{subj_text}"; end on the new fact instead',
        )


def _same_phrase(toks):
    """Return the tokens of a final "the same" or "the same thing", or ``None``."""
    words = [t.lower_ for t in toks[-3:]]
    if len(toks) >= 2 and words[-2:] == ["the", "same"]:
        return toks[-2:]
    if len(toks) >= 3 and words[-3:-1] == ["the", "same"] and toks[-1].lemma_.lower() in PLACEHOLDER_NOUNS | {
        "way",
        "one",
        "ones",
    }:
        return toks[-3:]
    if toks[-1].lower_ == "likewise":
        return toks[-1:]
    return None


def _main_subject(sent):
    root = sent.root
    for c in root.children:
        if c.dep_ in ("nsubj", "nsubjpass", "csubj"):
            return c
    return None


def _number(tok) -> str | None:
    low = tok.lower_
    if low in SINGULAR_PRONOUNS or low in ("this", "that"):
        return "Sing"
    if low in PLURAL_PRONOUNS or low in ("these", "those"):
        return "Plur"
    if tok.tag_ in ("NNS", "NNPS"):
        return "Plur"
    if tok.tag_ in ("NN", "NNP"):
        return "Sing"
    num = tok.morph.get("Number")
    return num[0] if num else None


def _agrees(pron, tok) -> bool:
    a, b = _number(pron), _number(tok)
    return a is not None and a == b
