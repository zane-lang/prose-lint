"""Inline cleanup: turn Markdown or doc-comment markup into plain sentences.

Code spans become code tokens, links keep their text, and markup characters
disappear. Every surviving character keeps its source position.
"""

from __future__ import annotations

import re

from ..ptext import PText

# A code span whose content matches this pattern stays in the sentence as
# written (``fixture_pairing.ml``, ``List.map``), so the parser sees a noun.
# Any other code span becomes the stand-in word below.
IDENT_RE = re.compile(r"^[A-Za-z_$@][\w.:/$@#'+-]*(\(\))?$")
CODE_WORD = "CODE"

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
REF_LINK_RE = re.compile(r"\[([^\]^][^\]]*)\]\[[^\]]*\]")
FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]]+\]")
SHORT_REF_RE = re.compile(r"\[([^\]^][^\]]*)\](?![(\[:])")
AUTOLINK_RE = re.compile(r"<(?:https?|mailto|ftp):[^>\s]*>")
URL_RE = re.compile(r"\b(?:https?|ftp)://[^\s<>()\[\]`]+[^\s<>()\[\]`.,;:!?'\"]")
HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
EMPHASIS_RE = re.compile(r"\*\*|\*|~~|(?<![\w\\])__?|__?(?!\w)")
ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
# Text in double quotes is a mention, as in 'the verb "say"', so it becomes a
# code token too.
QUOTE_RE = re.compile(r'"([^"]{1,200}?)"|\u201c([^\u201d]{1,200}?)\u201d')

# Doc-comment tags. The first group drops the tag together with the name it
# documents (``@param count``); the second drops a bare tag (``@return``).
NAMED_TAG_RE = re.compile(
    r"(?<![\w`])[@\\](?:param|tparam|arg|raise|raises|throws|exception|before|since|version)\b\s+\S+"
)
BARE_TAG_RE = re.compile(r"(?<![\w`])[@\\][a-z]+\b")
REST_FIELD_RE = re.compile(
    r"(?<!\S):(?:param|parameter|arg|argument|key|keyword|type|raises?|except|exception"
    r"|var|ivar|cvar|vartype|rtype|returns?|yields?)(?:\s+[^:\n]+)?:(?=\s|$)"
)
REST_ROLE_RE = re.compile(r":[a-z]+(?::[a-z]+)?:`([^`]+)`")

# ocamldoc markup.
OCAML_CODE_BLOCK_RE = re.compile(r"\{\[.*?\]\}|\{v\s.*?\sv\}|\{%.*?%\}", re.S)
OCAML_REF_RE = re.compile(r"\{!(?:[a-z]+:)?([^}]*)\}")
OCAML_LINK_RE = re.compile(r"\{\{:[^}]*\}")
OCAML_STYLE_RE = re.compile(r"\{(?:[a-zA-Z]+|[0-9]+(?::[\w-]+)?|-|\^|_)\s")
OCAML_CODE_RE = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])*)\]")
OCAML_CLOSE_RE = re.compile(r"\}")

MARKDOWN = "markdown"
COMMENT = "comment"
OCAMLDOC = "ocamldoc"
DOCSTRING = "docstring"


def code_token(pt: PText, m: re.Match[str], g: int | str) -> PText | tuple[str, bool]:
    """Turn the code in group ``g`` into a code token for the sentence."""
    inner = pt.group(m, g).strip()
    if IDENT_RE.match(inner.text) and len(inner.text) <= 64:
        inner.code = [True] * len(inner.text)
        return inner
    return (CODE_WORD, True)


def clean_inline(pt: PText, dialect: str = MARKDOWN) -> PText:
    pt = pt.replace(HTML_COMMENT_RE, lambda m: ("", False))
    if dialect == OCAMLDOC:
        pt = pt.replace(OCAML_CODE_BLOCK_RE, lambda m: (CODE_WORD, True))
        cur = pt
        pt = cur.replace(OCAML_REF_RE, lambda m: code_token(cur, m, 1))
        pt = pt.replace(OCAML_LINK_RE, lambda m: ("", False))
        pt = pt.replace(OCAML_STYLE_RE, lambda m: ("", False))
    if dialect != MARKDOWN:
        pt = pt.replace(NAMED_TAG_RE, lambda m: ("", False))
        pt = pt.replace(BARE_TAG_RE, lambda m: ("", False))
    if dialect == DOCSTRING:
        pt = pt.replace(REST_FIELD_RE, lambda m: ("", False))
        cur = pt
        pt = cur.replace(REST_ROLE_RE, lambda m: code_token(cur, m, 1))

    cur = pt
    pt = cur.replace(CODE_SPAN_RE, lambda m: code_token(cur, m, 2))
    if dialect == OCAMLDOC:
        cur = pt
        pt = cur.replace(OCAML_CODE_RE, lambda m: code_token(cur, m, 1))
        pt = pt.replace(OCAML_CLOSE_RE, lambda m: ("", False))
    cur = pt
    pt = cur.replace(
        QUOTE_RE, lambda m: None if _inside_code(cur, m) else code_token(cur, m, 1 if m.group(1) is not None else 2)
    )
    pt = pt.replace(AUTOLINK_RE, lambda m: ("URL", True))
    pt = pt.replace(URL_RE, lambda m: ("URL", True))
    for pattern in (IMAGE_RE, LINK_RE, REF_LINK_RE):
        cur = pt
        pt = cur.replace(pattern, lambda m: cur.group(m, 1))
    pt = pt.replace(FOOTNOTE_REF_RE, lambda m: ("", False))
    cur = pt
    pt = cur.replace(SHORT_REF_RE, lambda m: cur.group(m, 1))
    pt = pt.replace(HTML_TAG_RE, lambda m: ("", False))
    cur = pt
    pt = cur.replace(EMPHASIS_RE, lambda m: None if _inside_code(cur, m) else ("", False))
    cur = pt
    pt = cur.replace(ESCAPE_RE, lambda m: cur.group(m, 1))
    # Newlines become spaces, so the parser does not read a line break as a token.
    pt.text = pt.text.replace("\n", " ").replace("\t", " ")
    return pt


def _inside_code(pt: PText, m: re.Match[str]) -> bool:
    return any(pt.code[m.start() : m.end()])
