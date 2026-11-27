"""Sentence-level cases for each rule: defects it must report, and sentences it must pass."""

import pytest

BAD = [
    # personified-verb
    ("The triple says it is x86_64.", "personified-verb"),
    ("The text says so.", "personified-verb"),
    ("The field, which tells the linker where to look, is optional.", "personified-verb"),
    ("This means that the parser must backtrack.", "personified-verb"),
    ("The type knows its own size.", "personified-verb"),
    ("The value wants a positive count.", "personified-verb"),
    ("The flag decides the target and tells the linker where to look.", "personified-verb"),
    ("`fixture_pairing.ml` says which fixture each golden file uses.", "personified-verb"),
    ("Let the type decide the layout.", "personified-verb"),
    ("The flag wants to say which target to use.", "personified-verb"),
    ("The values exist, and they decide the layout.", "personified-verb"),
    ("`guide.markdown` says which page comes first.", "personified-verb"),
    # placeholder-noun
    ("The case of a name says what it is.", "placeholder-noun"),
    ("What the step does is documented below.", "placeholder-noun"),
    ("The parser looks up a name in the table.", "placeholder-noun"),
    ("The thing returns early.", "placeholder-noun"),
    ("There is a way to skip the check.", "placeholder-noun"),
    ("Something calls the hook twice.", "placeholder-noun"),
    ("Pick the one that matches the target.", "placeholder-noun"),
    ("Is what the step does documented below?", "placeholder-noun"),
    ("The log shows what happens next.", "placeholder-noun"),
    ("The docs explain what the flag means for the build.", "placeholder-noun"),
    # self-reference
    ("The case of a name says what it is.", "self-reference"),
    ("The text says so.", "self-reference"),
    ("A worker pool runs many workers doing the same thing.", "self-reference"),
    ("The blocks stay where they are.", "self-reference"),
    # stale-ending
    ("Which fixture each golden file is for is fixture_pairing.ml.", "stale-ending"),
    ("How the parser recovers is described in recovery.md.", "stale-ending"),
    ("The build supports C, OCaml, Python and so on.", "stale-ending"),
    ("The lexer reads numbers, strings, etc.", "stale-ending"),
    ("Where the cache is stored is config.yaml.", "stale-ending"),
    ("Which fixture each golden file is for is `fixture_pairing.ml`.", "stale-ending"),
]

GOOD = [
    "fixture_pairing.ml pairs each golden file with its fixture.",
    "A worker pool runs many workers that run the same step.",
    "The linker reports an error.",
    "The list holds the elements.",
    "The signature declares the return type.",
    "An identifier's case shows whether it is a type or a variable: types start upper-case, variables lower-case.",
    "The parser reads the file and closes it.",
    "The compiler decides which overload to call.",
    "The user tells the build which target to use.",
    "We say that a value is live when a later read uses it.",
    "That is to say, the cache is empty.",
    "Does the parser accept a trailing comma?",
    "What does the flag change?",
    "The field name must be unique.",
    "When the build fails, the log is empty.",
    "Whether or not the cache is warm, the build reads every file.",
    "The `name` field holds the package name.",
    "The function returns the element type.",
    "Only an unescaped double quote closes it.",
    'The verb "say" takes a subject.',
    "The reach of the closure is the reach of what it captures.",
    "A variadic C function is reached the same way.",
    "A project wants a stable API, and the package decides its own version.",
    "Users read the log, and they decide which warning to fix first.",
    "`List.map` decides the order of the calls.",
    "Needless to say, the cache is empty.",
    "When the cache is warm the build is fast.",
    'Write "the element type" instead of "the thing".',
    "The phrase \u201cwhat it is\u201d is a free relative clause.",
]


@pytest.mark.parametrize("sentence,rule", BAD)
def test_reports_defect(lint, sentence, rule):
    rules = {f.rule for f in lint(sentence)}
    assert rule in rules, f"{rule} missed: {sentence!r} gave {sorted(rules)}"


@pytest.mark.parametrize("sentence", GOOD)
def test_passes_good_sentence(lint, sentence):
    found = lint(sentence)
    assert not found, f"{sentence!r} gave {[(f.rule, f.message) for f in found]}"


def test_finding_position_points_at_verb(lint):
    (f,) = [f for f in lint("Intro.\n\nThe triple says it is x86_64.") if f.rule == "personified-verb"]
    assert (f.line, f.column, f.end_column) == (3, 12, 16)


def test_headings_skip_sentence_shape_rules(lint):
    """A heading is a fragment: placeholder-noun reads it, self-reference does not."""
    assert {f.rule for f in lint("# The case of a name says what it is\n")} == {"placeholder-noun", "personified-verb"}


def test_pseudo_cleft_advice(lint):
    (f,) = [f for f in lint("What the method does is return the cached value.") if f.rule == "stale-ending"]
    assert "state the action directly" in f.message
