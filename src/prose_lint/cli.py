"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, find_config, load_config
from .extract import LANGUAGES, language_for
from .rules import ERROR, RULES

SKIP_DIRS = {"node_modules", "_build", "_opam", "__pycache__", "venv", "site-packages"}

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prose-lint",
        description="Check technical prose in Markdown files and code comments.",
    )
    p.add_argument("paths", nargs="*", default=["."], help="files or directories to check; '-' reads standard input")
    p.add_argument("--json", action="store_true", help="print findings as JSON")
    p.add_argument("--config", type=Path, help="read this configuration file instead of searching for one")
    p.add_argument("--no-config", action="store_true", help="ignore every configuration file")
    p.add_argument("--disable", action="append", default=[], metavar="RULE", help="turn off a rule (repeatable)")
    p.add_argument(
        "--enable", action="append", default=[], metavar="RULE", help="turn on a rule that the configuration disables"
    )
    p.add_argument("--language", choices=LANGUAGES, help="read every file as this language")
    p.add_argument(
        "--stdin-filename", default="<stdin>", metavar="NAME", help="file name to report for '-' and to pick its language"
    )
    p.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    p.add_argument("--version", action="version", version=f"prose-lint {__version__}")
    return p


def iter_files(paths: list[str], cfg, language: str | None, errors: list[str]):
    """Yield ``(display_path, file_path, language)`` for each file to check, in a fixed order.

    A directory that cannot be read adds a message to ``errors``.
    """

    def walk_error(e: OSError) -> None:
        errors.append(f"{_display(Path(e.filename))}: {e.strerror}")

    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for dirpath, dirnames, filenames in os.walk(p, onerror=walk_error):
                dirnames[:] = sorted(
                    d
                    for d in dirnames
                    if not d.startswith(".") and d not in SKIP_DIRS and not cfg.is_excluded(Path(dirpath) / d)
                )
                for name in sorted(filenames):
                    fp = Path(dirpath) / name
                    lang = language or language_for(name, cfg.languages)
                    if lang and not cfg.is_excluded(fp):
                        yield _display(fp), fp, lang
        elif not cfg.is_excluded(p):
            lang = language or language_for(p.name, cfg.languages)
            yield _display(p), p, lang


def _display(p: Path) -> str:
    try:
        return p.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        for rid in sorted(RULES):
            cls = RULES[rid]
            print(f"{rid} ({cls.severity}): {cls.summary}")
        return EXIT_OK

    for rid in args.disable + args.enable:
        if rid not in RULES:
            print(f"prose-lint: unknown rule {rid!r}; known: {', '.join(sorted(RULES))}", file=sys.stderr)
            return EXIT_USAGE

    try:
        if args.no_config:
            cfg = load_config(None)
        else:
            cfg = load_config(args.config or find_config(Path.cwd()))
    except ConfigError as e:
        print(f"prose-lint: {e}", file=sys.stderr)
        return EXIT_USAGE

    # Import late: loading spaCy takes a second, and --help and --list-rules
    # should not wait for it.
    from .lint import lint_text, make_rules

    rules = make_rules(cfg, set(args.disable), set(args.enable))
    findings = []
    files = 0
    status = EXIT_OK
    for raw in args.paths:
        if raw == "-":
            lang = args.language or language_for(args.stdin_filename, cfg.languages) or "markdown"
            findings += lint_text(sys.stdin.read(), lang, args.stdin_filename, rules)
            files += 1
            continue
        if not Path(raw).exists():
            print(f"prose-lint: {raw}: no such file or directory", file=sys.stderr)
            status = EXIT_USAGE
            continue
        walk_errors: list[str] = []
        for display, fp, lang in iter_files([raw], cfg, args.language, walk_errors):
            if lang is None:
                print(f"prose-lint: {display}: unknown file type; pass --language", file=sys.stderr)
                status = EXIT_USAGE
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"prose-lint: {display}: {e.strerror}", file=sys.stderr)
                status = EXIT_USAGE
                continue
            findings += lint_text(text, lang, display, rules)
            files += 1
        for msg in walk_errors:
            print(f"prose-lint: {msg}", file=sys.stderr)
            status = EXIT_USAGE

    findings.sort(key=lambda f: (f.path, f.line, f.column, f.rule, f.message))
    errors = sum(1 for f in findings if f.severity == ERROR)
    warnings = len(findings) - errors

    if args.json:
        out = {
            "findings": [f.as_dict() for f in findings],
            "summary": {"files": files, "errors": errors, "warnings": warnings},
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            suffix = "" if f.severity == ERROR else " (warning)"
            print(f"{f.path}:{f.line}:{f.column}: {f.rule}: {f.message}{suffix}")
        if findings:
            print(
                f"prose-lint: {_plural(errors, 'error')} and {_plural(warnings, 'warning')} in {_plural(files, 'file')}",
                file=sys.stderr,
            )

    if status != EXIT_OK:
        return status
    return EXIT_ERRORS if errors else EXIT_OK


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
