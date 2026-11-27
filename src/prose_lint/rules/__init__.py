"""The rule registry. Each module defines one rule."""

from .base import ERROR, SEVERITIES, WARN, Finding, Hit, Rule
from .personified_verb import PersonifiedVerb
from .placeholder_noun import PlaceholderNoun
from .self_reference import SelfReference
from .stale_ending import StaleEnding

RULES: dict[str, type[Rule]] = {
    cls.id: cls for cls in (PersonifiedVerb, PlaceholderNoun, SelfReference, StaleEnding)
}

__all__ = ["ERROR", "WARN", "SEVERITIES", "Finding", "Hit", "Rule", "RULES"]
