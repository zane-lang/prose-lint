"""Word lists the rules share. The configuration can extend each list."""

# Verbs of speech, thought and will. A person or a program may do these; a
# value, a file or a type may not.
PERSONIFIED_VERBS = frozenset(
    """
    say tell decide know want think believe mean understand care wish hope feel
    like prefer remember forget realize realise assume insist agree disagree
    promise complain claim ask intend try expect worry refuse admit pretend
    guess doubt notice learn choose
    """.split()
)

# Nouns that may be the subject of a verb in PERSONIFIED_VERBS: people, and
# programs or program parts that run and act.
AGENT_NOUNS = frozenset(
    """
    user reader writer author maintainer contributor developer programmer
    engineer reviewer tester person people human team owner admin
    administrator operator customer client caller callee member designer
    committee community audience student teacher

    compiler linker assembler loader parser lexer tokenizer scanner checker
    typechecker interpreter runtime vm program tool script command cli shell
    kernel os server daemon service worker scheduler process thread function
    method procedure routine subroutine closure lambda callback handler hook
    driver plugin library framework engine analyzer analyser optimizer
    optimiser generator formatter linter solver resolver builder build pass
    backend frontend browser editor ide system machine computer cpu processor
    test harness bot agent model algorithm implementation application app
    binary executable pipeline emitter printer encoder decoder serializer
    deserializer validator verifier prover evaluator inliner allocator
    collector manager controller router dispatcher planner installer
    toolchain debugger profiler preprocessor transpiler bundler consumer
    producer publisher subscriber sender receiver listener observer
    """.split()
)

# Pronouns that refer to people.
AGENT_PRONOUNS = frozenset(
    """
    i we you he she they one someone somebody everyone everybody anyone anybody
    nobody who whoever us me him her them
    """.split()
)

# Pronouns that refer to objects, values and clauses, never to people.
THING_PRONOUNS = frozenset(
    "it this that these those which what something anything everything nothing".split()
)

RELATIVE_PRONOUNS = frozenset("which that who whom".split())

# Nouns that stand in for the term a sentence should name.
PLACEHOLDER_NOUNS = frozenset("thing stuff".split())
PLACEHOLDER_PRONOUNS = frozenset("something somewhere somehow".split())
