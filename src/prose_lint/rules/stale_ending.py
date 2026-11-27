"""stale-ending: a sentence that ends on no new fact.

Two shapes trigger the rule. The first opens with a wh-clause as its subject
and puts the actor last ("Which fixture each golden file is for is
fixture_pairing.ml"); the actor belongs in front ("fixture_pairing.ml pairs
each golden file with its fixture"). The second ends on a filler phrase that
adds nothing ("and so on", "etc.").
"""

from __future__ import annotations

from ..segment import PARAGRAPH, Segment
from .base import WARN, Hit, Rule, is_code

WH_OPENERS = frozenset("what which whether how who why where when".split())
# "When" and "where" also open adverbial clauses ("When the cache is warm the
# build is fast"), so for them the final "is" must have no subject of its own.
ADVERBIAL_OPENERS = frozenset(("where", "when"))
# The longest tail after the final "is" that still counts as a bare
# complement, such as "fixture_pairing.ml" or "documented below".
MAX_TAIL = 4

FILLERS = (
    ("etc",),
    ("etc.",),
    ("and", "so", "on"),
    ("and", "so", "forth"),
    ("and", "the", "like"),
    ("and", "similar"),
    ("or", "similar"),
    ("and", "such"),
    ("and", "more"),
    ("and", "others"),
    ("or", "so"),
    ("as", "above"),
    ("as", "before"),
    ("as", "described", "above"),
    ("as", "mentioned", "above"),
    ("as", "mentioned", "before"),
    ("as", "mentioned", "earlier"),
)


class StaleEnding(Rule):
    id = "stale-ending"
    severity = WARN
    summary = "The sentence ends on no new fact: a wh-clause subject that leaves the actor last, or a filler ending."
    kinds = frozenset({PARAGRAPH})

    def check(self, sent, seg: Segment):
        toks = [t for t in sent if not t.is_space]
        words = [t for t in toks if not (t.is_punct and t.text != "etc.")]
        if not words:
            return
        hit = None if is_code(seg, words[-1]) else self._filler(words)
        if hit:
            yield hit
            return
        hit = self._wh_subject(sent, seg, toks, words)
        if hit:
            yield hit

    def _filler(self, words):
        lows = [w.lower_ for w in words]
        for filler in FILLERS:
            n = len(filler)
            if len(lows) > n and tuple(lows[-n:]) == filler:
                first, last = words[-n], words[-1]
                text = first.doc[first.i : last.i + 1].text
                return Hit(
                    first.idx,
                    last.idx + len(last.text),
                    f'the sentence ends on the filler "{text}"; list the remaining items or end on the last fact',
                )
        return None

    def _wh_subject(self, sent, seg, toks, words):
        first = words[0]
        if first.lower_ not in WH_OPENERS or sent.text.rstrip().endswith("?"):
            return None
        bes = [t for t in words[2:] if t.lemma_ == "be" and t.pos_ in ("AUX", "VERB")]
        if not bes:
            return None
        be = bes[-1]
        # The opening clause needs two words at least ("How the parser
        # recovers"); "Which is" is no clause.
        if len([t for t in words if first.i < t.i < be.i]) < 2:
            return None
        # "Whether the cache is warm, the build is slow" opens with an adverbial clause.
        if any(t.text in (",", ":", ";") for t in toks if first.i < t.i < be.i):
            return None
        if first.lower_ in ADVERBIAL_OPENERS:
            prev = be.doc[be.i - 1]
            if prev.dep_ in ("nsubj", "nsubjpass", "expl") and prev.head in (be, be.head):
                return None
        tail = [t for t in words if t.i > be.i]
        if not tail or len(tail) > MAX_TAIL:
            return None
        opener = first.doc[first.i : be.i].text
        complement = first.doc[tail[0].i : tail[-1].i + 1].text
        if tail[0].pos_ == "VERB" and tail[0].tag_ in ("VB", "VBP", "VBZ"):
            # "What the method does is return the cached value."
            advice = "state the action directly, with the actor as the subject"
        elif any(t.pos_ in ("NOUN", "PROPN", "PRON") or is_code(seg, t) for t in tail) and not any(
            t.tag_ == "VBN" for t in tail
        ):
            advice = f'make "{complement}" the subject of an action verb'
        else:
            advice = "put the actor first, as the subject of an action verb"
        return Hit(
            first.idx,
            tail[-1].idx + len(tail[-1].text),
            f'the sentence opens with the clause "{opener}" and leaves "{complement}" for the end; {advice}',
        )
