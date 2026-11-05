#!/usr/bin/env python3
"""Exercise the workflow's actual script without making GitHub API requests."""
import json
from pathlib import Path
import subprocess
import unittest

import yaml


WORKFLOW = Path(__file__).parent / "workflows/close-external-prs.yml"
SCRIPT = yaml.safe_load(WORKFLOW.read_text())["jobs"]["redirect"]["steps"][0]["with"]["script"]
MARKER = "<!-- netfyr-spec-submission-policy -->"
RUNNER = r"""
const fs = require('node:fs');
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [];
const github = {
  rest: {
    pulls: {
      get: async args => {
        calls.push(['get', args]);
        if (fixture.fail === 'get') throw new Error('get failed');
        return { data: fixture.pr };
      },
      update: async args => { calls.push(['close', args]); },
    },
    issues: {
      listComments: () => {},
      createComment: async args => {
        calls.push(['comment', args]);
        if (fixture.fail === 'comment') throw new Error('comment failed');
      },
    },
  },
  paginate: async (method, args) => {
    if (method !== github.rest.issues.listComments) throw new Error('wrong endpoint');
    calls.push(['list', args]);
    if (fixture.fail === 'list') throw new Error('list failed');
    return fixture.comments;
  },
};
const context = {
  repo: { owner: 'netfyr', repo: 'specs' },
  actor: fixture.actor,
  payload: { pull_request: { number: 42, user: { login: 'stale-author' } } },
};
(async () => {
  let error;
  try {
    const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
    await new AsyncFunction('github', 'context', fixture.script)(github, context);
  } catch (e) {
    error = e.message;
  }
  process.stdout.write(JSON.stringify({ calls, error }));
})();
"""


def run_policy(*, association="NONE", login="outsider", user_id=123,
               user_type="User", state="open", comments=(), fail=None,
               actor="outsider", draft=False):
    fixture = {
        "script": SCRIPT,
        "pr": {
            "number": 42, "state": state, "draft": draft,
            "author_association": association,
            "user": {"login": login, "id": user_id, "type": user_type},
        },
        "comments": comments, "fail": fail, "actor": actor,
    }
    result = subprocess.run(["node", "-e", RUNNER], input=json.dumps(fixture),
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class SubmissionPolicy(unittest.TestCase):
    def assert_allowed(self, **kwargs):
        result = run_policy(**kwargs)
        self.assertNotIn("error", result)
        self.assertEqual(result["calls"], [["get", {
            "owner": "netfyr", "repo": "specs", "pull_number": 42,
        }]])

    def assert_closed(self, **kwargs):
        result = run_policy(**kwargs)
        self.assertNotIn("error", result)
        self.assertEqual([call[0] for call in result["calls"]],
                         ["get", "list", "comment", "close"])
        comment = result["calls"][2][1]
        self.assertEqual((comment["owner"], comment["repo"], comment["issue_number"]),
                         ("netfyr", "specs", 42))
        self.assertIn("https://specs.netfyr.io/?ns=netfyr%2Fspecs", comment["body"])
        self.assertIn("proposal or revision", comment["body"])
        self.assertEqual(result["calls"][-1], ["close", {
            "owner": "netfyr", "repo": "specs", "pull_number": 42, "state": "closed",
        }])

    def test_organization_members_and_owners_are_allowed(self):
        for association in ("MEMBER", "OWNER"):
            with self.subTest(association=association):
                self.assert_allowed(association=association)

    def test_only_the_netfyr_bot_identity_is_allowed(self):
        self.assert_allowed(login="netfyr[bot]", user_id=308292487,
                            user_type="Bot", association="CONTRIBUTOR")
        self.assert_closed(login="another[bot]", user_type="Bot", association="MEMBER")
        self.assert_closed(login="netfyr[bot]", user_type="Bot")
        self.assert_closed(user_id=308292487)

    def test_outsiders_including_previous_contributors_and_collaborators_are_closed(self):
        for association in ("NONE", "CONTRIBUTOR", "COLLABORATOR", "FIRST_TIMER",
                            "FIRST_TIME_CONTRIBUTOR", "MANNEQUIN", "UNKNOWN"):
            with self.subTest(association=association):
                self.assert_closed(association=association)

    def test_drafts_and_member_triggered_reruns_do_not_bypass_policy(self):
        self.assert_closed(draft=True, actor="pfeifferj")

    def test_already_closed_pull_requests_are_untouched(self):
        self.assert_allowed(state="closed")

    def test_reopened_pr_does_not_repeat_the_existing_bot_explanation(self):
        comments = [{"user": {"type": "User"}, "body": "discussion"}] * 100
        comments.append({"user": {"type": "Bot", "login": "github-actions[bot]"},
                         "body": MARKER})
        result = run_policy(comments=comments)
        self.assertNotIn("error", result)
        self.assertEqual([call[0] for call in result["calls"]], ["get", "list", "close"])
        self.assertEqual(result["calls"][1][1]["per_page"], 100)

    def test_copying_the_marker_does_not_suppress_the_explanation(self):
        for user in ({"type": "User", "login": "outsider"},
                     {"type": "Bot", "login": "other[bot]"}):
            with self.subTest(user=user):
                self.assert_closed(comments=[{"user": user, "body": MARKER}])

    def test_api_errors_do_not_close_without_an_explanation(self):
        for operation in ("get", "list", "comment"):
            with self.subTest(operation=operation):
                result = run_policy(fail=operation)
                self.assertEqual(result["error"], f"{operation} failed")
                self.assertNotIn("close", [call[0] for call in result["calls"]])


if __name__ == "__main__":
    unittest.main()
