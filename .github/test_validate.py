#!/usr/bin/env python3
"""Self-check for validate.py: run `python3 .github/test_validate.py`."""
from validate import CRITIC, SPEC_PATH, validate_codeowners, validate_roles

for good in ("003-foo.md", "cat/003-foo.md"):
    assert SPEC_PATH.match(good), f"should accept {good}"
for bad in ("03-foo.md", "0034-foo.md", "003-.md",
            "a/b/003-foo.md", "specs/003-foo/spec.md"):
    assert not SPEC_PATH.match(bad), f"should reject {bad}"

assert CRITIC.search("text {++add++}"), "should flag CriticMarkup"
assert not CRITIC.search("plain {json}"), "should ignore plain braces"

assert validate_roles({"approvers": ["a", "b"], "approvals-required": 0}), "zero approvals must fail"
assert not validate_roles({"approvers": ["a", "b"]}), "default (1) must pass"
assert not validate_roles({"approvers": ["a", "b"], "approvals-required": 2}), "2 of 2 must pass"
assert validate_roles({"approvers": ["a"], "approvals-required": 2}), "over-count must fail"
assert validate_roles({"approvers": []}), "empty approvers must fail"

R = {"approvers": ["ann", "bob"]}
assert not validate_codeowners(R, "* @ann @bob\n"), "matching owners must pass"
assert not validate_codeowners(R, "* @bob @ann\n"), "owner order must not matter"
assert validate_codeowners(R, "* @ann\n"), "missing owner must fail"
assert validate_codeowners(R, "# no rule\n"), "absent '*' rule must fail"
assert not validate_codeowners({"approvers": "bad"}, "* @x\n"), "defers to roles check on bad approvers"

print("ok")
