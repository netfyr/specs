#!/usr/bin/env python3
"""Validate a SpecDoc spec repo: roles.yml schema + spec.md layout.

Mirrors the assumptions the spec-board makes so a hand-authored PR can't
break the board. Run locally with `python3 .github/validate.py`.
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_PATH = re.compile(r"^specs/(?:[^/]+/)?\d{3}-[^/]+/spec\.md$")
CRITIC = re.compile(r"\{(\+\+|--|>>|~~|==)")

errors = []


def validate_roles(roles):
    errs = []
    approvers = roles.get("approvers")
    if not isinstance(approvers, list) or not approvers or not all(isinstance(a, str) for a in approvers):
        errs.append("roles.yml: approvers must be a non-empty list of logins")
        approvers = approvers if isinstance(approvers, list) else []
    req = roles.get("approvals-required", 1)
    if not isinstance(req, int) or req < 1 or req > len(approvers):
        errs.append(f"roles.yml: approvals-required must be an int in 1..{len(approvers)}")
    repos = roles.get("implementation-repos", [])
    if not isinstance(repos, list) or not all(re.match(r"^[^/]+/[^/]+$", str(r)) for r in repos):
        errs.append("roles.yml: implementation-repos must be a list of owner/repo")
    return errs


def check_roles():
    path = next((ROOT / p for p in ("roles.yml", ".specs/roles.yml") if (ROOT / p).exists()), None)
    if not path:
        errors.append("roles.yml missing (root or .specs/)")
        return
    try:
        roles = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        errors.append(f"{path.name}: invalid YAML: {e}")
        return
    errors.extend(validate_roles(roles))


def check_specs():
    for spec in ROOT.glob("specs/**/spec.md"):
        rel = spec.relative_to(ROOT).as_posix()
        if not SPEC_PATH.match(rel):
            errors.append(f"{rel}: path must be specs/[category/]NNN-slug/spec.md")
        text = spec.read_text()
        if text.lstrip().startswith("---"):
            errors.append(f"{rel}: leftover frontmatter; merged specs carry none")
        if not re.search(r"^#\s", text, re.M):
            errors.append(f"{rel}: no top-level '# ' heading (abstract source)")
        if CRITIC.search(text):
            errors.append(f"{rel}: unresolved CriticMarkup")


if __name__ == "__main__":
    check_roles()
    check_specs()
    if errors:
        print("\n".join(f"FAIL {e}" for e in errors), file=sys.stderr)
        sys.exit(1)
    print("ok")
