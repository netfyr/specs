#!/usr/bin/env python3
"""Validate a SpecDoc spec repo: roles.yml schema + spec layout.

Mirrors the assumptions the spec-board makes so a hand-authored PR can't
break the board. Run locally with `python3 .github/validate.py`.
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_PATH = re.compile(r"^(?:[^/]+/)?\d{3}-[^/]+\.md$")
CRITIC = re.compile(r"\{(\+\+|--|>>|~~|==)")
ACCOUNT_ID = re.compile(r"[1-9][0-9]{0,19}")
LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")

errors = []


def principal_logins(entries):
    if not isinstance(entries, list):
        return None
    ids, logins = set(), set()
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "login"}:
            return None
        account_id, login = entry["id"], entry["login"]
        if (not isinstance(account_id, str) or not ACCOUNT_ID.fullmatch(account_id)
                or not isinstance(login, str) or not LOGIN.fullmatch(login)
                or account_id in ids or login.lower() in logins):
            return None
        ids.add(account_id)
        logins.add(login.lower())
        result.append(login)
    return result


def validate_roles(roles):
    if not isinstance(roles, dict):
        return ["roles.yml: expected a mapping"]
    errs = []
    approvers = principal_logins(roles.get("approvers"))
    if not approvers:
        errs.append("roles.yml: approvers must be a non-empty list of distinct {id, login} accounts with quoted numeric IDs")
    authors = principal_logins(roles.get("authors", []))
    if authors is None:
        errs.append("roles.yml: authors must be a list of distinct {id, login} accounts with quoted numeric IDs")
    if approvers is not None and authors is not None:
        accounts = {(person["id"], person["login"].lower())
                    for person in roles["approvers"] + roles.get("authors", [])}
        if (len({account_id for account_id, _ in accounts}) != len(accounts)
                or len({login for _, login in accounts}) != len(accounts)):
            errs.append("roles.yml: account IDs and logins must agree across approvers and authors")
    req = roles.get("approvals-required", 1)
    if type(req) is not int or req < 1 or (approvers is not None and req > len(approvers)):
        errs.append("roles.yml: approvals-required must be a positive integer no larger than the approver count")
    repos = roles.get("implementation-repos", [])
    if not isinstance(repos, list) or not all(re.match(r"^[^/]+/[^/]+$", str(r)) for r in repos):
        errs.append("roles.yml: implementation-repos must be a list of owner/repo")
    return errs


def validate_codeowners(roles, text):
    approvers = principal_logins(roles.get("approvers")) if isinstance(roles, dict) else None
    if not approvers:
        return []  # validate_roles already flags a bad approvers list
    owners = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("* "):
            owners = line.split()[1:]
    if set(owners) != {f"@{a}" for a in approvers}:
        return [f"CODEOWNERS: '*' owners must match roles.yml approvers ({sorted(approvers)})"]
    return []


def find_roles():
    return next((ROOT / p for p in ("roles.yml", ".specs/roles.yml") if (ROOT / p).exists()), None)


def check_roles():
    path = find_roles()
    if not path:
        errors.append("roles.yml missing (root or .specs/)")
        return
    try:
        roles = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        errors.append(f"{path.name}: invalid YAML: {e}")
        return
    errors.extend(validate_roles(roles))


def check_codeowners():
    path = find_roles()
    co = ROOT / ".github" / "CODEOWNERS"
    if not path or not co.exists():
        if not co.exists():
            errors.append("CODEOWNERS missing (.github/CODEOWNERS)")
        return
    try:
        roles = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return  # check_roles already flags the YAML error
    errors.extend(validate_codeowners(roles, co.read_text()))


def check_specs():
    for spec in ROOT.glob("**/[0-9]*.md"):
        rel = spec.relative_to(ROOT).as_posix()
        if rel.startswith("."):
            continue
        if not SPEC_PATH.match(rel):
            errors.append(f"{rel}: path must be [area/]NNN-slug.md at the repo apex")
        text = spec.read_text()
        if text.lstrip().startswith("---"):
            errors.append(f"{rel}: leftover frontmatter; merged specs carry none")
        if not re.search(r"^#\s", text, re.M):
            errors.append(f"{rel}: no top-level '# ' heading (abstract source)")
        if CRITIC.search(text):
            errors.append(f"{rel}: unresolved CriticMarkup")


if __name__ == "__main__":
    check_roles()
    check_codeowners()
    check_specs()
    if errors:
        print("\n".join(f"FAIL {e}" for e in errors), file=sys.stderr)
        sys.exit(1)
    print("ok")
