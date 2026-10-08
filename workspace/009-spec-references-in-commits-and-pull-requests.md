# Feature Specification: Spec References in Commits and Pull Requests

Every change to a netfyr repository must name the spec it implements, in a form a machine can check. Work is assigned spec by spec, but once a branch is merged nothing connects the resulting commits back to the spec they came from, so answering "what did this spec actually ship" means reading diffs and guessing. This spec defines the reference format, where it appears, how a spec is marked complete so the board can close it, and the enforcement that keeps all of it correct at commit time rather than at review time.

## User Scenarios & Testing

### User Story 1 - Reference a Spec from a Commit (Priority: P0)

A developer implementing a spec writes a commit message ending with a `Spec:` trailer naming that spec's path in the specs repo. The commit-msg hook accepts it. A developer who forgets the trailer, or writes a reference that is not a spec path, has the commit rejected with a message saying what the trailer should look like.

**Why this priority**: Without a reference on the commit itself, nothing else in this spec has anything to check.

**Independent Test**: Commit with a valid trailer, with no trailer, and with a malformed trailer; verify the first is accepted and the other two are rejected with a non-zero exit and a message on stderr.

**Acceptance Scenarios**:

1. **Given** a commit message ending in `Spec: core/002-schema-validation`, **When** the developer commits, **Then** the commit is accepted.
2. **Given** a commit message with no `Spec:` trailer, **When** the developer commits, **Then** the commit is rejected and the failure names the expected trailer format.
3. **Given** a commit message with two `Spec:` trailers, **When** the developer commits, **Then** the commit is rejected: a commit implements exactly one spec.
4. **Given** a merge, revert, or `fixup!` commit, **When** the developer commits, **Then** no trailer is required.

### User Story 2 - Reject a Dangling Reference (Priority: P1)

A developer references a spec that does not exist, because of a typo or because the spec was never merged. CI resolves every reference against the specs repository and fails the pull request, naming the reference that could not be found.

**Why this priority**: A well-formed reference to a spec that does not exist is worse than no reference. It reads as tracked work while pointing at nothing.

**Independent Test**: Open a pull request whose commits reference a nonexistent spec path; verify CI fails and names the path.

**Acceptance Scenarios**:

1. **Given** a commit referencing `core/404-ghost`, **When** CI runs the check, **Then** the job fails and reports that `core/404-ghost.md` does not exist in the specs repository.

### User Story 3 - One Spec per Pull Request (Priority: P1)

A reviewer opens a pull request and reads it against exactly one spec. CI verifies that every commit in the branch references the same spec and that the pull request description names that same spec, so a branch cannot quietly mix two deliverables.

**Why this priority**: "One spec per pull request" is already the convention; unenforced, it is violated by accident whenever a developer fixes something adjacent while in the area.

**Independent Test**: Open a pull request whose commits reference two different specs; verify CI fails and names both.

**Acceptance Scenarios**:

1. **Given** a branch whose commits all reference `core/003-policies`, **When** CI runs the check, **Then** it passes.
2. **Given** a branch with one commit referencing `core/003-policies` and one referencing `core/002-schema-validation`, **When** CI runs the check, **Then** the job fails and reports both references.
3. **Given** a branch whose commits reference `core/003-policies` and a pull request description referencing `core/002-schema-validation`, **When** CI runs the check, **Then** the job fails.

### User Story 4 - Close the Loop on the Board (Priority: P2)

A developer finishes the last piece of a spec and adds an `implements netfyr/specs#N` trailer to that commit. When it merges to the default branch, the spec board detects it, marks the spec implemented, and drops the card. Nobody moves the card by hand, and a spec whose work has landed never sits in review columns looking unfinished.

**Why this priority**: The `Spec:` trailer records which spec a commit came from; it does not say when a spec is done. Without the closing trailer the board keeps every approved spec open forever, and its status stops meaning anything.

**Independent Test**: Merge a commit carrying `implements netfyr/specs#N` to the default branch and verify the board marks spec N implemented.

**Acceptance Scenarios**:

1. **Given** a commit carrying `implements netfyr/specs#N`, **When** it merges to the default branch, **Then** the board marks spec N implemented.
2. **Given** a commit carrying `implements #N` in an implementation repository other than the spec repository, **When** CI runs the check, **Then** the job fails: a bare number resolves against the wrong repository.
3. **Given** a commit whose `implements` trailer names a different spec from its `Spec:` trailer, **When** CI runs the check, **Then** the job fails.

### Edge Cases

- A commit whose trailer sits above a later paragraph is rejected: only the final paragraph of a message is a trailer block, and a reference buried mid-message is not reliably machine-readable.
- A pull request with no commits, or a commit range that resolves to nothing, fails rather than passing vacuously. A check that examined nothing must not report success.
- Revert commits are exempt. The reverted commit was checked when it landed, and a revert that had to restate the original reference would attribute the removal to the spec that added it.
- `fixup!` and `squash!` commits are exempt: they are absorbed into a commit that carries its own reference before the branch merges.
- Documentation, CI, and tooling changes are not exempt. Every change belongs to some spec; repo-wide work belongs to the `meta/` spec that introduced the thing being changed. A `meta/` spec is referenced like any other one; the exemptions are FR-004's and nothing else.
- A change touching several areas is still one spec. FR-005 constrains the spec a pull request implements, not the directories it edits: a refactor spanning `core/` and a driver references the spec that requires the refactor, or the `meta/` spec when the work is repo-wide.
- Only the commit that completes a spec carries `implements`, and it is the last commit that references a spec; earlier commits carry only `Spec:`. More than one closing trailer per spec is harmless to the board but means two commits each claim to have finished the work.
- A branch that merges somewhere other than the default branch does not close the loop, because that is where the board looks. Work parked on a long-lived branch keeps its card open, which is the correct reading.
- Squash merges keep the trailer as long as the squashed message retains it. A merge strategy that rewrites messages breaks both trailers, not just this one.

## Requirements

### Functional Requirements

- **FR-001**: Every non-exempt commit MUST carry exactly one `Spec:` trailer in the final paragraph of its message.
- **FR-002**: The trailer value MUST be the spec's path in [netfyr/specs](https://github.com/netfyr/specs) with the `.md` extension removed, matching `([a-z0-9][a-z0-9-]*/)?[0-9]{3}-[a-z0-9-]+` for a feature spec: an optional lowercase area directory, a three-digit number, and a lowercase slug. Example: `Spec: core/002-schema-validation`. A root-level top-level spec instead uses its published lowercase slug, such as `philosophy`; CI MUST verify that it resolves to a published top-level spec.
- **FR-003**: URLs, bare spec numbers, unverified feature slugs, and paths carrying the `.md` extension MUST be rejected. Top-level slugs are allowed only as defined by FR-002. One canonical form keeps references greppable and comparable without normalization.
- **FR-004**: Merge commits, revert commits, and `fixup!`/`squash!`/`amend!` commits MUST be exempt from FR-001.
- **FR-005**: Every non-exempt commit in a pull request MUST reference the same spec, and the pull request description MUST end with that same trailer. A pull request containing only exempt commits MUST still name its governing spec in its description. Pull request titles follow the repository's subject-line conventions; only descriptions, not titles, carry trailer blocks.
- **FR-006**: Referenced specs MUST exist. CI MUST resolve each reference against the specs repository and fail on a reference that does not resolve. The local hook MAY check format only, so that committing works offline.
- **FR-007**: Enforcement MUST run locally as a `commit-msg` hook installed by the repository's hook setup script, so a bad reference is caught before the branch exists.
- **FR-008**: Enforcement MUST run in CI on every pull request, on open, reopen, synchronize, and edit. The description is editable after opening, so checking only at open time leaves it unenforced.
- **FR-009**: A check that examined no commits MUST fail rather than pass. Silent vacuous success is the same failure mode the no-skip test policy exists to prevent (see `meta/000-project-setup`).
- **FR-010**: The checker MUST print the accepted reference on stdout and diagnostics on stderr, so that callers can compare the reference a branch implements against the one its pull request claims.
- **FR-011**: `CHANGELOG.md` entries MUST name the spec they came from in parentheses, in the same path form as the trailer.
- **FR-012**: There MUST be no exemption keyword (`Spec: none` or equivalent). An escape hatch on a tracking rule is used by default once the branch is inconvenient.
- **FR-013**: The commit that completes a feature spec MUST additionally carry an `implements netfyr/specs#N` trailer, where N is the spec's reference number (the number of the pull request the board opened for it). This is what the board scans for, and it is the only thing that moves a feature spec from approved to implemented. Top-level specs end at approved and MUST NOT carry an `implements` closer.
- **FR-014**: The `implements` trailer MUST name the spec repository explicitly. A bare `implements #N` resolves against the repository being scanned, which outside netfyr/specs is the wrong repository and silently references an unrelated issue or pull request.
- **FR-015**: Where both trailers are present, they MUST denote the same spec. CI MUST resolve the referenced pull request and fail if the spec file it added is not the one the `Spec:` trailer names. The two are written from different sources -- a path a developer types and a number from the board -- so nothing but a check keeps them in agreement.
- **FR-016**: `implements` MUST NOT be required on every commit. It marks completion, not provenance; requiring it everywhere would make every commit claim to finish the spec and the board would close a spec on its first commit.
- **FR-017**: CI MUST fail a pull request in which more than one commit carries an `implements` trailer. A pull request carrying none is valid: a branch that advances a spec without finishing it has nothing to close.
- **FR-018**: The commit carrying `implements` MUST be the last commit of the pull request that has to reference a spec. Work following the commit that declares the spec finished contradicts the declaration, and the board acts on the trailer regardless of what comes after it. Exempt commits (FR-004) after the closer do not count as work: a revert or a `fixup!` is not new implementation. A branch that needs a further change after its closer moves the trailer to the new last commit. A trailing exemption for trivial changes would need a definition of trivial that CI can evaluate, so there is none.

### Key Entities

- **Spec reference**: The path of a spec in netfyr/specs without the extension, in the canonical form defined by FR-002.
- **Spec trailer**: A `Spec: <reference>` line in the final paragraph of a commit message or pull request description. Present on every commit; records provenance.
- **Implements trailer**: An `implements netfyr/specs#N` line naming the spec's reference number. Present on the single commit that completes a spec; records completion and is what the board consumes.
- **Reference checker**: A script with two modes: one commit message (for the `commit-msg` hook) and one commit range (for CI), printing the accepted reference on success.

## Success Criteria

- **SC-001**: A commit with no `Spec:` trailer, or a malformed one, is rejected locally with a non-zero exit and a message on stderr.
- **SC-002**: A pull request whose commits reference more than one spec fails CI.
- **SC-003**: A pull request referencing a spec that does not exist in netfyr/specs fails CI.
- **SC-004**: A pull request whose description names a different spec from its commits fails CI.
- **SC-005**: Given a spec reference, `git log --grep` returns every commit implementing that spec across the repository's history.
- **SC-006**: Merging a commit that carries `implements netfyr/specs#N` to the default branch moves spec N to implemented on the board without anyone touching the card.
- **SC-007**: A commit whose `implements` trailer and `Spec:` trailer name different specs, or whose `implements` trailer omits the repository, fails CI.
- **SC-008**: A pull request whose commits carry two `implements` trailers fails CI and names the commits; one or none passes.
- **SC-009**: A pull request in which a spec-referencing commit follows the `implements` commit fails CI, naming both; the same branch with only a `fixup!` after it passes.

## Assumptions

- Specs live in netfyr/specs at `NNN-slug.md` or `area/NNN-slug.md` and are readable without authentication, so CI can resolve a reference with an unauthenticated fetch. Resolving a pull request number to the spec file it added (FR-015) needs the GitHub API, and on a public repository an unauthenticated call is enough.
- A spec's reference number is the number of the pull request the board opened for it, and it does not change. It is unrelated to the `NNN` in the filename: `meta/000-project-setup` arrived as pull request 10.
- Specs are not renamed or renumbered after merge. A rename breaks existing references; if it becomes necessary, the old path stays as a stub.
- Pull requests are merged with their commits intact or squashed into a message that retains the trailer.
- Depends on `meta/000-project-setup` for the hook setup script and the shell integration test conventions.










