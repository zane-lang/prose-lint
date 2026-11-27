# prose-lint

prose-lint checks technical prose in Markdown files and code comments. It
parses each sentence with spaCy and reports four kinds of defect: personified
verbs, placeholder nouns, sentences that point back at their own subject, and
sentences that end on no new fact.

The spaCy model and every other dependency are pinned, and the parser runs on
one thread, so one input always produces the same findings on any machine.

## Install

prose-lint needs Python 3.11, 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/zane-lang/prose-lint
```

For a checkout, `uv sync` installs the locked dependencies, including the
`en_core_web_sm` 3.8.0 model. Without uv, `requirements.lock` lists every
package with its hash:

```bash
pip install --require-hashes -r requirements.lock && pip install --no-deps .
```

## Usage

```bash
prose-lint README.md docs src
```

prose-lint walks each directory, reads every file of a supported type and
prints one line per finding:

```text
docs/build.md:12:10: personified-verb: "The text" is not a person or a program and cannot "say"; ...
```

The fields are path, line, column, rule id and message. A finding from a rule
with severity `warn` ends with `(warning)`. When there are findings, a summary goes to standard error.

| Option | Effect |
|---|---|
| `--json` | Print findings and a summary as JSON. |
| `--config PATH` | Read this configuration file instead of searching for one. |
| `--no-config` | Ignore every configuration file. |
| `--disable RULE` | Turn off a rule. Repeatable. |
| `--enable RULE` | Turn on a rule that the configuration disables. Repeatable. |
| `--language LANG` | Read every file as `LANG`. |
| `--stdin-filename NAME` | Report this file name for `-` and pick its language from it. |
| `--list-rules` | Print the rules with their default severities. |

A path of `-` reads standard input.

The exit status is 0 when no finding has severity `error`, 1 when at least one
does, and 2 for a usage error, an unreadable file or an invalid configuration.

## Rules

| Rule id | Default severity | Defect |
|---|---|---|
| `personified-verb` | error | A value, a file or a type is the subject of a verb of speech, thought or will. |
| `placeholder-noun` | error | A vague noun or a free relative clause stands where the exact term belongs. |
| `self-reference` | error | The sentence ends on a pronoun or a pro-form that points back at its own subject. |
| `stale-ending` | warn | The sentence opens with a wh-clause and leaves the actor for the end, or ends on a filler phrase. |

### personified-verb

The rule looks for verbs such as "say", "tell", "decide", "know", "want" and
"mean". When the subject of one of these verbs is neither a person nor a
program, the rule reports the verb. A person or a program may decide or know;
a property, a value, a file or a type may not.

| Defect | Rewrite |
|---|---|
| "The triple says it is x86_64." | The triple names the x86_64 architecture. |
| "The flag tells the linker where to look." | The flag gives the linker a search path. |
| "This means that the parser must backtrack." | The parser must therefore backtrack. |

The subjects that may act are listed in `src/prose_lint/rules/words.py`:
people such as the user, programs such as the compiler, the linker, the
parser or a function, and projects and packages, which stand for the people
who maintain them. A subject that is a proper noun (`Git`, `OCaml`) passes
unless it looks like a file name.

### placeholder-noun

The rule reports free relative clauses whose verb is vague ("what it is",
"what the step does", "what happens") and placeholder nouns: "thing", "stuff", "something", an indefinite "a way" or
"a name" without a modifier, "the one", and "its kind". A free relative
clause with a specific verb, such as "what crosses the boundary", passes;
the vague verbs are listed in `src/prose_lint/rules/words.py`.

| Defect | Rewrite |
|---|---|
| "The case of a name says what it is." | An identifier's case shows whether it is a type or a variable. |
| "The parser looks up a name in the table." | The parser looks up the field name in the table. |
| "What the step does is documented below." | The next section documents the link step. |

### self-reference

The rule reports a sentence whose last words point back at an earlier part
of the same sentence: a clause that ends on its own pronoun subject ("says
what it is"), a final "so" ("the text says so"), and a final "the same",
"the same thing" or "the same one". A final "the same way" passes, because it
usually points at the method of the previous sentence.

| Defect | Rewrite |
|---|---|
| "A worker pool runs many workers doing the same thing." | A worker pool runs many workers that run the same step. |
| "The blocks stay where they are." | The blocks keep their addresses. |

### stale-ending

The rule reports two sentence shapes. In the first, a wh-clause is the
subject and the actor comes last:

| Defect | Rewrite |
|---|---|
| "Which fixture each golden file is for is fixture_pairing.ml." | fixture_pairing.ml pairs each golden file with its fixture. |
| "How the parser recovers is described in recovery.md." | recovery.md describes the parser's error recovery. |

The second shape ends on a filler phrase such as "etc.", "and so on" or "as
mentioned above".

## Supported files

| Language | Files | Prose that prose-lint reads |
|---|---|---|
| `markdown` | `.md`, `.markdown` | Paragraphs, headings, list items, quotes and table cells |
| `ocaml` | `.ml`, `.mli`, `.mll` | `(* *)` and `(** *)` comments, nested |
| `c` | `.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hh`, `.hpp`, `.hxx` | `//` and `/* */` comments |
| `zane` | `.zn` | `//` and `///` comments |
| `python` | `.py`, `.pyi` | `#` comments and docstrings |
| `hash` | `.sh`, `.bash`, `.zsh`, `.yml`, `.yaml`, `.mk`, `.cmake`, `.opam`, `.cr`, `.ps1`, `.psm1`, `Makefile`, `GNUmakefile`, `makefile`, `justfile`, `Justfile`, `.justfile`, `Dockerfile`, `CMakeLists.txt` | `#` comments |
| `toml` | `.toml` | `#` comments |
| `dune` | `dune`, `dune-project`, `dune-workspace` | `;` and `#\| \|#` comments |
| `scheme` | `.scm` | `;` comments and `#\| \|#` comments, nested |
| `javascript` | `.js`, `.mjs`, `.cjs`, `.jsx`, `.tsx` | `//` and `/* */` comments, including those inside a template literal's `${ }` substitution and a JSX element's `{ }` expressions; JSX text and a regular-expression literal start no string |
| `typescript` | `.ts`, `.mts`, `.cts` | The comments of `javascript`, without JSX, since `<T>value` in these files is a type assertion |
| `nix` | `.nix` | `#` and `/* */` comments, outside `"..."` strings and `''...''` indented strings |
| `lua` | `.lua` | `--` comments and `--[[ ]]` block comments, including long brackets with `=` signs such as `--[==[ ]==]` |
| `lean` | `.lean` | `--` comments and `/- -/` comments, nested, with `/-- -/` and `/-! -/` doc comments |
| `astro` | `.astro` | HTML comments in the template, and JavaScript comments in its `{ }` expressions; JavaScript comments in the `---` frontmatter and `<script>` elements, and `/* */` comments in `<style>` elements |

Each lexer reads string and character literals as well as comments, so a
comment marker inside a string literal starts no comment. Before analysis,
prose-lint removes:

- fenced code blocks, indented code blocks, HTML blocks and YAML front matter
  from Markdown;
- comment markers and the leading `*` of each line of a block comment;
- lines of commented-out code, such as `// return 0;`;
- tool pragmas such as `# noqa` and `# type: ignore`;
- JSDoc and LuaLS annotation lines such as `@param name the name`, in
  JavaScript, Lua and Astro files;
- doctest examples, literal blocks and `Args:` headers from docstrings;
- `{[ ]}` code blocks and `@param` tags from ocamldoc comments.

An inline code span stays in the sentence as a code token, so the parser still
sees a noun: ``the `parse_date` function`` reads as "the parse_date
function". No rule reports a code token as a placeholder. Text in double
quotes counts as a mention and becomes a code token as well, so a sentence
can quote a defect ("the text says so") without a finding.

## Suppression comments

A suppression comment turns off rules for one prose block: a paragraph, a list
item, a heading, a whole table or a whole code comment.

```markdown
<!-- prose-lint: ignore personified-verb -->
The story tells how the module system grew.
```

```c
// prose-lint: ignore personified-verb, placeholder-noun
// The C standard says what a byte is.
```

The comment applies to the block that contains it. A comment on a line of its
own applies to the next block. `ignore` without rule ids turns off every rule,
and `ignore-file` applies to the whole file.

## Configuration

prose-lint reads the first configuration file it finds in the current
directory or a parent directory: `prose-lint.toml`, `.prose-lint.toml`, or a
`[tool.prose-lint]` table in `pyproject.toml`.

```toml
# Rules to turn off.
disable = ["stale-ending"]

# Glob patterns, relative to the configuration file. A pattern without a
# slash matches a file or directory name at any depth.
exclude = ["vendor", "docs/generated/**"]

# Map more file extensions or file names to a language.
[languages]
".rs" = "c"
".js" = "c"

[rules.placeholder-noun]
severity = "warn"
extra-nouns = ["widget"]

[rules.personified-verb]
extra-agents = ["oracle"]
extra-verbs = ["suggest"]
```

Every rule accepts `severity`. `personified-verb` also accepts `extra-agents`
and `extra-verbs`, and `placeholder-noun` accepts `extra-nouns` and
`extra-vague-verbs`. prose-lint
rejects unknown keys, rule ids and languages with exit status 2.

## Development

The `justfile` holds the project's commands:

```bash
just test
```

`just test` runs the test suite. `just golden` rewrites the expected outputs
in `tests/fixtures` after an intended change; review their diff before
committing. `just prose` runs prose-lint on this repository. `just lock`
updates `uv.lock` and `requirements.lock` together.

Each rule is a module in `src/prose_lint/rules/` with an `id`, a default
`severity` and a `check` method that receives one parsed sentence.
