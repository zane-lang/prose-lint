"""Configuration: ``prose-lint.toml``, ``.prose-lint.toml`` or ``[tool.prose-lint]`` in ``pyproject.toml``.

Example::

    disable = ["stale-ending"]
    exclude = ["vendor/**", "CHANGELOG.md"]

    [languages]
    ".rs" = "c"

    [rules.placeholder-noun]
    severity = "warn"
    extra-nouns = ["widget"]
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .extract import LANGUAGES
from .rules import RULES, SEVERITIES

CONFIG_NAMES = ("prose-lint.toml", ".prose-lint.toml")
TOP_KEYS = {"disable", "exclude", "languages", "rules"}
RULE_KEYS = {
    "personified-verb": {"severity", "extra-verbs", "extra-agents"},
    "placeholder-noun": {"severity", "extra-nouns", "extra-vague-verbs"},
    "self-reference": {"severity"},
    "stale-ending": {"severity"},
}


class ConfigError(Exception):
    pass


@dataclass
class Config:
    root: Path = field(default_factory=Path.cwd)
    source: Path | None = None
    disabled: set[str] = field(default_factory=set)
    exclude: list[str] = field(default_factory=list)
    languages: dict[str, str] = field(default_factory=dict)
    severity: dict[str, str] = field(default_factory=dict)
    options: dict[str, dict[str, Any]] = field(default_factory=dict)

    def is_excluded(self, path: Path) -> bool:
        try:
            rel = path.resolve().relative_to(self.root.resolve())
        except ValueError:
            return False
        parts = rel.parts
        for pattern in self.exclude:
            rx = _glob_regex(pattern)
            anchored = "/" in pattern.rstrip("/")
            for k in range(1, len(parts) + 1):
                target = "/".join(parts[:k]) if anchored else parts[k - 1]
                if rx.fullmatch(target):
                    return True
        return False


def _glob_regex(pattern: str) -> re.Pattern[str]:
    p = pattern.strip("/")
    out = []
    i = 0
    while i < len(p):
        if p.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif p.startswith("**", i):
            out.append(".*")
            i += 2
        elif p[i] == "*":
            out.append("[^/]*")
            i += 1
        elif p[i] == "?":
            out.append("[^/]")
            i += 1
        elif p[i] == "[" and "]" in p[i + 2 :]:
            # A character class: [abc], [a-z], [!abc].
            close = p.index("]", i + 2)
            body = p[i + 1 : close]
            neg = body.startswith(("!", "^"))
            body = body[1:] if neg else body
            out.append("[" + ("^" if neg else "") + body.replace("\\", "\\\\") + "]")
            i = close + 1
        else:
            out.append(re.escape(p[i]))
            i += 1
    return re.compile("".join(out))


def find_config(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        for name in CONFIG_NAMES:
            if (d / name).is_file():
                return d / name
        pp = d / "pyproject.toml"
        if pp.is_file():
            try:
                data = tomllib.loads(pp.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                continue
            tool = data.get("tool", {})
            if isinstance(tool, dict) and "prose-lint" in tool:
                return pp
    return None


def load_config(path: Path | None) -> Config:
    if path is None:
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"{path}: {e}") from e
    if path.name == "pyproject.toml":
        tool = data.get("tool", {})
        if not isinstance(tool, dict):
            raise ConfigError(f"{path}: 'tool' must be a table")
        data = tool.get("prose-lint", {})
        if not isinstance(data, dict):
            raise ConfigError(f"{path}: 'tool.prose-lint' must be a table")
    return parse_config(data, path)


def parse_config(data: dict[str, Any], path: Path) -> Config:
    cfg = Config(root=path.parent, source=path)
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key {sorted(unknown)[0]!r}")
    cfg.disabled = set(_str_list(data.get("disable", []), path, "disable"))
    for rid in cfg.disabled:
        _check_rule(rid, path)
    cfg.exclude = _str_list(data.get("exclude", []), path, "exclude")
    langs = data.get("languages", {})
    if not isinstance(langs, dict):
        raise ConfigError(f"{path}: 'languages' must be a table")
    for key, lang in langs.items():
        if lang not in LANGUAGES:
            raise ConfigError(f"{path}: languages.{key}: unknown language {lang!r}; known: {', '.join(LANGUAGES)}")
        cfg.languages[key] = lang
    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        raise ConfigError(f"{path}: 'rules' must be a table")
    for rid, opts in rules.items():
        _check_rule(rid, path)
        if not isinstance(opts, dict):
            raise ConfigError(f"{path}: rules.{rid} must be a table")
        bad = set(opts) - RULE_KEYS[rid]
        if bad:
            raise ConfigError(f"{path}: rules.{rid}: unknown key {sorted(bad)[0]!r}")
        if "severity" in opts:
            if opts["severity"] not in SEVERITIES:
                raise ConfigError(f"{path}: rules.{rid}.severity must be one of {', '.join(SEVERITIES)}")
            cfg.severity[rid] = opts["severity"]
        cfg.options[rid] = {
            k: _str_list(v, path, f"rules.{rid}.{k}") for k, v in opts.items() if k != "severity"
        }
    return cfg


def _check_rule(rid: str, path: Path) -> None:
    if rid not in RULES:
        raise ConfigError(f"{path}: unknown rule {rid!r}; known: {', '.join(sorted(RULES))}")


def _str_list(value: Any, path: Path, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{path}: {key!r} must be a list of strings")
    return list(value)
