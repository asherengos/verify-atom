"""Minimal YAML-subset reader for this service's own config files.

This is deliberately NOT a general YAML parser. It supports exactly the
subset used by ``config.yaml`` and ``cost_model.yaml`` in this project:

* ``#`` comments (full-line and trailing) and blank lines
* nested mappings via 2-space indentation
* scalar values: quoted strings ("..." / '...'), true/false, null/~,
  integers, floats, and bare strings

Anything else (lists, anchors, multi-line scalars, tabs, flow syntax)
raises ``MiniYAMLError``. The project pins its dependencies to
``flask`` + ``waitress`` only, so PyYAML is intentionally avoided; if the
config schema ever outgrows this subset, adopt PyYAML instead of
extending this parser.
"""

from __future__ import annotations


class MiniYAMLError(ValueError):
    """Raised when a config file uses YAML outside the supported subset."""


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment, respecting single/double quotes."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _parse_scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        quote = text[0]
        inner = text[1:-1]
        if quote == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~", ""):
        return None
    for converter in (int, float):
        try:
            return converter(text)
        except ValueError:
            pass
    if text[:1] in "-+[" or text[:1] == "{" or "\t" in text:
        raise MiniYAMLError(f"unsupported YAML construct: {text!r}")
    return text


def loads(text: str) -> dict:
    """Parse the supported YAML subset into nested dicts."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise MiniYAMLError(f"line {lineno}: tabs are not allowed")
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise MiniYAMLError(f"line {lineno}: expected 'key: value'")
        key, _, value = stripped.partition(":")
        key = key.strip()
        if not key or " " in key:
            raise MiniYAMLError(f"line {lineno}: bad key {key!r}")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise MiniYAMLError(f"line {lineno}: bad indentation")
        parent = stack[-1][1]
        if key in parent:
            raise MiniYAMLError(f"line {lineno}: duplicate key {key!r}")
        value = value.strip()
        if value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


def load(path) -> dict:
    """Read a YAML-subset file from disk."""
    with open(path, encoding="utf-8") as handle:
        return loads(handle.read())
