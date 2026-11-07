#!/usr/bin/env python3
"""Self-check for validate.py: run `python3 .github/test_validate.py`."""
import unittest

from validate import CRITIC, SPEC_PATH, validate_codeowners, validate_roles

for good in ("003-foo.md", "cat/003-foo.md"):
    assert SPEC_PATH.match(good), f"should accept {good}"
for bad in ("03-foo.md", "0034-foo.md", "003-.md",
            "a/b/003-foo.md", "specs/003-foo/spec.md"):
    assert not SPEC_PATH.match(bad), f"should reject {bad}"

assert CRITIC.search("text {++add++}"), "should flag CriticMarkup"
assert not CRITIC.search("plain {json}"), "should ignore plain braces"

REVIEWERS = [{"id": "110632", "login": "ann"}, {"id": "22047071", "login": "bob"}]


class ReviewPolicyTests(unittest.TestCase):
    def test_numeric_reviewers_and_authors(self):
        roles = {"approvers": REVIEWERS, "authors": [{"id": "197720", "login": "tyll"}]}
        self.assertEqual(validate_roles(roles), [])
        self.assertEqual(validate_roles({"approvers": REVIEWERS, "approvals-required": 2}), [])
        self.assertEqual(validate_roles({"approvers": [{"id": "1" * 20, "login": "a" * 39}]}), [])

    def test_quorum_requires_distinct_reviewers(self):
        for required in (0, 3, True, 1.0, "1"):
            with self.subTest(required=required):
                self.assertTrue(validate_roles({"approvers": REVIEWERS, "approvals-required": required}))
        self.assertTrue(validate_roles({"approvers": []}))
        self.assertTrue(validate_roles({
            "approvers": REVIEWERS + [{"id": "110632", "login": "renamed"}], "approvals-required": 3,
        }))

    def test_invalid_identities(self):
        for entry in ("ann", "110632", 110632, None, [], {},
                      {"id": "110632"}, {"login": "ann"},
                      {"id": 110632, "login": "ann"},
                      {"id": "0", "login": "ann"},
                      {"id": "01", "login": "ann"},
                      {"id": "١١٠٦٣٢", "login": "ann"},
                      {"id": "110632\n", "login": "ann"},
                      {"id": "1" * 21, "login": "ann"},
                      {"id": "110632", "login": "a" * 40},
                      {"id": "110632", "login": "ann bob"},
                      {"id": "110632", "login": "@ann"},
                      {"id": "110632", "login": "ann\n"}):
            for field in ("approvers", "authors"):
                with self.subTest(field=field, entry=entry):
                    roles = {"approvers": REVIEWERS, field: [entry]}
                    self.assertTrue(validate_roles(roles))
                    if field == "approvers":
                        self.assertEqual(validate_codeowners(roles, "* @ann @bob\n"), [])

    def test_duplicate_ids_and_labels(self):
        for duplicate in ({"id": "110632", "login": "renamed"},
                          {"id": "197720", "login": "ANN"}):
            for field in ("approvers", "authors"):
                with self.subTest(field=field, duplicate=duplicate):
                    roles = {"approvers": REVIEWERS, field: REVIEWERS + [duplicate]}
                    self.assertTrue(validate_roles(roles))

    def test_identities_agree_across_rosters(self):
        self.assertEqual(validate_roles({"approvers": REVIEWERS, "authors": REVIEWERS}), [])
        self.assertEqual(validate_roles({"approvers": REVIEWERS, "authors": [{"id": "110632", "login": "ANN"}]}), [])
        for author in ({"id": "197720", "login": "ANN"}, {"id": "110632", "login": "renamed"}):
            with self.subTest(author=author):
                self.assertTrue(validate_roles({"approvers": REVIEWERS, "authors": [author]}))

    def test_invalid_policy_shape(self):
        for roles in (None, [], "ann", 1):
            with self.subTest(roles=roles):
                self.assertTrue(validate_roles(roles))
                self.assertEqual(validate_codeowners(roles, "* @ann\n"), [])
        for field in ("approvers", "authors"):
            for value in (None, {}, "ann"):
                with self.subTest(field=field, value=value):
                    self.assertTrue(validate_roles({"approvers": REVIEWERS, field: value}))

    def test_codeowners_uses_display_logins(self):
        roles = {"approvers": REVIEWERS}
        for text in ("* @ann @bob\n", "* @bob @ann\n"):
            with self.subTest(text=text):
                self.assertEqual(validate_codeowners(roles, text), [])
        for text in ("* @ann\n", "# no rule\n", "* @110632 @22047071\n", "* @ann @bob @other\n"):
            with self.subTest(text=text):
                self.assertTrue(validate_codeowners(roles, text))


if __name__ == "__main__":
    unittest.main()
