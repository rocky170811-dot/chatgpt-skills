#!/usr/bin/env python3
"""Validate the library without executing any skill or network request."""
from pathlib import Path
import ast
import re
import sys
import yaml

root = Path(__file__).resolve().parents[1]
files = sorted((root / "skills").glob("**/SKILL.md"))
errors = []
if len(files) != 48:
    errors.append(f"Expected 48 skills, got {len(files)}")
groups = {"work": 10, "codex": 8}
for group, expected in groups.items():
    actual = sum(p.relative_to(root / 'skills').parts[0] == group for p in files)
    if actual != expected:
        errors.append(f"Expected {expected} {group} skills, got {actual}")
names = set()
for path in files:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        errors.append(f"{path}: missing frontmatter")
        continue
    try:
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict):
            raise ValueError("frontmatter is not a mapping")
        name = data.get("name")
        desc = data.get("description")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError(f"invalid name: {name}")
        if name in names:
            raise ValueError(f"duplicate name: {name}")
        names.add(name)
        if not isinstance(desc, str) or not desc.strip():
            raise ValueError("missing description")
        if not parts[2].strip():
            raise ValueError("empty skill body")
    except Exception as exc:
        errors.append(f"{path}: {exc}")
template = root / "templates" / "bot_template.py"
try:
    source = template.read_text(encoding="utf-8")
    ast.parse(source, filename=str(template))
    if "return True  # не блокируем человека" in source:
        errors.append("bot template: subscription check fails open")
    if "WELCOME.format(name=escape(name))" not in source:
        errors.append("bot template: HTML user name not escaped")
except Exception as exc:
    errors.append(f"bot template: {exc}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(f"PASS: {len(files)} skills; names unique; YAML parsed; bot AST valid")
