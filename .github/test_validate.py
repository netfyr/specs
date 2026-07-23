#!/usr/bin/env python3
"""Self-check for validate.py: run `python3 .github/test_validate.py`."""
from validate import CRITIC, SPEC_PATH, validate_roles

for good in ("specs/003-foo/spec.md", "specs/cat/003-foo/spec.md"):
    assert SPEC_PATH.match(good), f"should accept {good}"
for bad in ("specs/03-foo/spec.md", "specs/003-foo/design.md",
            "specs/a/b/003-foo/spec.md", "specs/0034-foo/spec.md"):
    assert not SPEC_PATH.match(bad), f"should reject {bad}"

assert CRITIC.search("text {++add++}"), "should flag CriticMarkup"
assert not CRITIC.search("plain {json}"), "should ignore plain braces"

assert validate_roles({"approvers": ["a", "b"], "approvals-required": 0}), "zero approvals must fail"
assert not validate_roles({"approvers": ["a", "b"]}), "default (1) must pass"
assert not validate_roles({"approvers": ["a", "b"], "approvals-required": 2}), "2 of 2 must pass"
assert validate_roles({"approvers": ["a"], "approvals-required": 2}), "over-count must fail"
assert validate_roles({"approvers": []}), "empty approvers must fail"

print("ok")
