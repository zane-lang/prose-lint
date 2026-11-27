"""Run the rules over the segments of one file."""

from __future__ import annotations

from .config import Config
from .extract import extract
from .nlp import parse
from .rules import RULES, Finding, Rule
from .segment import apply_directives


def make_rules(cfg: Config, extra_disabled: set[str] = frozenset(), enabled: set[str] = frozenset()) -> list[Rule]:
    rules = []
    for rid in sorted(RULES):
        if (rid in cfg.disabled or rid in extra_disabled) and rid not in enabled:
            continue
        rule = RULES[rid](cfg.options.get(rid))
        rule.severity = cfg.severity.get(rid, rule.severity)
        rules.append(rule)
    return rules


def lint_text(text: str, language: str, path: str, rules: list[Rule]) -> list[Finding]:
    ex = extract(text, language)
    file_off = apply_directives(ex)
    if None in file_off:
        return []
    findings: set[Finding] = set()
    for seg in ex.segments:
        active = [
            r
            for r in rules
            if seg.kind in r.kinds
            and r.id not in file_off
            and r.id not in seg.suppressed
            and None not in seg.suppressed
        ]
        if not active:
            continue
        doc = parse(seg.text.text)
        for sent in doc.sents:
            for rule in active:
                for hit in rule.check(sent, seg):
                    line, col = seg.text.pos_at(hit.start)
                    end_line, end_col = seg.text.pos_at(hit.end - 1)
                    findings.add(
                        Finding(path, line, col, end_line, end_col + 1, rule.id, rule.severity, hit.message)
                    )
    return sorted(findings, key=lambda f: (f.line, f.column, f.rule, f.message))
