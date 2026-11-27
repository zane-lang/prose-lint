"""personified-verb: a value, a file or a type as the subject of a verb of
speech, thought or will ("the triple says", "the flag decides")."""

from __future__ import annotations

import re

from ..segment import Segment
from .base import ERROR, Hit, Rule, is_code
from .words import (
    AGENT_NOUNS,
    AGENT_PRONOUNS,
    PERSONIFIED_VERBS,
    RELATIVE_PRONOUNS,
    THING_PRONOUNS,
)

FILE_NAME_RE = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,5}$")


class PersonifiedVerb(Rule):
    id = "personified-verb"
    severity = ERROR
    summary = "A value, file, type or other thing is the subject of a verb such as 'says' or 'decides'."

    def __init__(self, options=None):
        super().__init__(options)
        self.verbs = self.word_list("verbs", PERSONIFIED_VERBS)
        self.agents = self.word_list("agents", AGENT_NOUNS)

    def check(self, sent, seg: Segment):
        for verb in sent:
            if verb.pos_ != "VERB" or verb.lemma_.lower() not in self.verbs or is_code(seg, verb):
                continue
            if _fixed_phrase(verb):
                continue
            subj = _subject(verb)
            if subj is None:
                continue
            thing = self._thing(subj, seg)
            if thing is None:
                continue
            yield Hit(
                verb.idx,
                verb.idx + len(verb.text),
                f'"{thing}" is not a person or a program and cannot "{verb.lemma_.lower()}"; '
                "make the program or person that acts the subject, or use a verb such as "
                '"holds", "marks", "declares" or "determines"',
            )

    def _thing(self, subj, seg: Segment) -> str | None:
        """Return the subject phrase, or ``None`` when the subject is a person or a program."""
        phrase = subj.doc[subj.left_edge.i : subj.i + 1].text
        if is_code(seg, subj):
            return phrase if FILE_NAME_RE.search(subj.text) else None
        low = subj.lower_
        if low in AGENT_PRONOUNS:
            return None
        if low in THING_PRONOUNS:
            return phrase
        if subj.pos_ == "PROPN":
            return phrase if FILE_NAME_RE.search(subj.text) else None
        if subj.pos_ != "NOUN":
            return None
        if subj.lemma_.lower() in self.agents or low in self.agents:
            return None
        return phrase


def _fixed_phrase(verb) -> bool:
    """Skip idioms that use these verbs without a subject that acts.

    Examples: "that is to say", "needless to say", "so to speak".
    """
    if verb.lemma_ == "say":
        prev = verb.nbor(-1) if verb.i > 0 else None
        if prev is not None and prev.lower_ == "to":
            return True
    return False


def _subject(verb):
    """Find the subject of ``verb``, following coordination and control verbs."""
    v = verb
    for _ in range(6):
        subs = [c for c in v.children if c.dep_ == "nsubj"]
        if subs:
            s = subs[0]
            if s.lower_ in RELATIVE_PRONOUNS and v.dep_ == "relcl":
                return v.head
            return s
        if v.dep_ == "conj" and v.head.pos_ in ("VERB", "AUX"):
            v = v.head
            continue
        if v.dep_ == "xcomp":
            objs = [c for c in v.head.children if c.dep_ in ("dobj", "obj")]
            if objs:
                return objs[0]
            if v.head.lemma_ == "be":
                return None
            v = v.head
            continue
        if v.dep_ == "acl" and v.tag_ == "VBG":
            return v.head
        return None
    return None
