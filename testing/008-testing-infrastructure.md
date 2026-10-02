# Feature Specification: Testing Infrastructure

Provide reproducible tests of netfyr's observable behavior against an explicitly selected build and environment. Rust unit tests cover internal contracts, acceptance tests cover specification requirements through public interfaces, and integration tests verify those contracts against Linux. A cheap unit test does not replace an acceptance or real-backend check that the requirement needs.

This spec adopts pytest for new network integration and acceptance tests under `tests/integration/`. It deliberately extends SPEC-000's shell-only integration convention: pytest supplies shared fixtures, parameterization, and per-case reporting for the expanded network matrix. Existing shell tests remain required and run through the same outer runner; conversion must preserve their assertions and history. The build-selection rule below replaces SPEC-000's unconditional build step for package-verification runs. This is the explicit exception permitted by Test Driven Development P9.

## User Scenarios & Testing

### User Story 1 - Test Without Reconfiguring the Host (Priority: P0)

A developer tests network changes in a disposable environment. Fixtures create their own namespace and veth devices using operating-system tools. They never borrow host management interfaces, snapshot the host's real configuration for later reapplication, or depend on netfyr to restore a failed test.

**Independent Test**: Exercise a successful change and an injected failure, then compare the host's interfaces, addresses, routes, and DNS and verify that only fixture-owned resources were created and removed.

**Acceptance Scenarios**:

1. **Given** a disposable test namespace with two veth devices, **When** netfyr changes one device's MTU, **Then** the other device and the host's management network remain unchanged.
2. **Given** a case requires an initially enabled device, **When** its fixture prepares it, **Then** administrative state is set through an independent tool; `enabled` has the meaning defined by SPEC-002 FR-006, distinct from carrier.
3. **Given** netfyr fails or exits during a case, **When** cleanup runs, **Then** the fixture-owned namespace and devices are removed without calling netfyr.
4. **Given** a transition test needs an unusual initial state, **When** it starts, **Then** only that fixture establishes the specified baseline. Ordinary tests do not assume netfyr requires a cleared host to apply valid state.

### User Story 2 - Verify State Independently (Priority: P0)

A test verifies both the public result and the resulting kernel state. Assertions preserve meaningful list order and inspect unrelated state that the operation must not change. They may normalize only equivalences the owning schema or feature spec declares.

**Independent Test**: Apply an MTU change, observe it with `ip -j`, then deliberately inspect a wrong MTU and confirm that the assertion fails with expected and actual values.

**Acceptance Scenarios**:

1. **Given** an MTU-only change, **When** it completes, **Then** the requested MTU is observed independently and unrelated addresses and administrative state remain unchanged.
2. **Given** a same-prefix address ordering requirement, **When** the order is wrong, **Then** the assertion fails rather than sorting both lists into a false pass.
3. **Given** an asynchronous behavior with a declared convergence deadline, **When** the state has not converged, **Then** a bounded condition wait fails with the final observation and elapsed time. A successful command exit alone is insufficient.
4. **Given** a future feature defines removing a contribution or reverting a change, **When** tested, **Then** the assertion follows that feature's remaining-state contract. Removing fixture devices during cleanup does not test a netfyr lifecycle action, and no `absent` state keyword is assumed.

### User Story 3 - Cover Each Requirement at the Appropriate Tier (Priority: P1)

A reviewer can identify which cases cover a feature's normal behavior, boundaries, failure behavior, and preservation rules. Tests carry explicit tiers; missing markers fail collection instead of becoming an implicit lower tier.

**Independent Test**: Map a change to its requirement cases, including an invalid MTU and an unaffected device, and demonstrate that a faulty implementation fails the applicable tier.

**Acceptance Scenarios**:

1. **Given** a change to interface ownership, **When** its required suite runs, **Then** a mutant that updates an unmanaged interface is detected before acceptance.
2. **Given** a changed numeric constraint, **When** reviewed, **Then** the mapping covers the inclusive bounds, values just outside them, and wrong-type input where applicable.
3. **Given** an unmarked or multiply tiered pytest case, **When** collected, **Then** collection fails and names the case.
4. **Given** applicable cases selected for a required job, **When** none execute or a selected case unexpectedly skips, **Then** the job fails rather than presenting incomplete coverage as success.

### User Story 4 - Verify a Selected Build (Priority: P1)

A developer tests a local build; a distribution engineer tests installed packages. The runner supplies the exact executable to every case. No test searches the workspace, guesses a target directory, or falls back to another binary.

**Independent Test**: Run the same cases once against an explicitly built candidate and once against an installed executable; record the identity and hash used by each run.

**Acceptance Scenarios**:

1. **Given** a local-build target and explicit Cargo target directory, **When** invoked, **Then** the runner builds that target and passes its absolute executable path to the tests.
2. **Given** an installed-package target such as `/usr/bin/netfyr`, **When** invoked, **Then** no build occurs and all cases use that exact executable.
3. **Given** a missing or non-executable selected target, **When** invoked, **Then** the runner fails before network setup and does not choose a substitute.

### User Story 5 - Declare Prerequisites and Environment Coverage (Priority: P1)

A test author declares the operating-system tools, capabilities, kernel features, and environment variants a case requires. CI uses those declarations to schedule supported environments and reports missing prerequisites as failures within a required job.

**Independent Test**: Select a namespace case on an environment without its required capability and inspect the explicit preflight failure and test inventory.

**Acceptance Scenarios**:

1. **Given** a selected case requires namespace creation and `ip`, **When** either is unavailable, **Then** preflight names the case and missing prerequisite and the job fails.
2. **Given** a feature supports multiple kernel versions or distribution builds, **When** accepted, **Then** its reviewed environment matrix identifies and runs the relevant real-backend cases on those targets.
3. **Given** an environment is outside the declared support matrix, **When** scheduling occurs, **Then** the exclusion is visible before execution and is not counted as a passing case.

### User Story 6 - Select Relevant Cases Without Weakening Gates (Priority: P1)

A developer selects by feature and tier using documented pytest-compatible markers. CI records the selected and executed identities so an accidental filter cannot turn a required suite green.

**Independent Test**: Select an apply case by feature and tier, then verify that a broken apply implementation fails that selected test and that the required full gate still includes its other mapped cases.

## Requirements

### Functional Requirements

- **FR-001**: Internal unit tests MUST use Rust `#[cfg(test)]` and `cargo test`; pure tests MUST run without privileged setup or network tools. Public-interface acceptance tests MUST assert the owning specification's outcomes. Real-backend integration tests MUST independently observe Linux state and supported environment behavior. New Python cases live under `tests/integration/`; existing SPEC-000 shell checks remain in the required inventory.
- **FR-002**: Fixtures MUST create uniquely named, disposable namespaces and virtual devices and record ownership of those resources. They MUST NOT move or modify existing host management interfaces. Setup and cleanup MUST use independent operating-system tools, not netfyr. Cleanup MUST run on normal failure and interruption; after an uncatchable termination, the outer runner MUST remove only resources recorded as belonging to that run. The environment must be discarded if trustworthy cleanup cannot be established.
- **FR-003**: Each case MUST start with the fixture state its preconditions require and MUST not inherit mutations from an earlier case. Reusing infrastructure is allowed only when isolation is demonstrated. Physical-device tests require an explicitly allocated disposable VM or host and belong to the declared environment matrix; they MUST NOT silently substitute the user's host NICs.
- **FR-004**: Required prerequisites MUST be declared with each test or its inherited fixture metadata: executable tools, network privileges, kernel capabilities, and applicable environments. The runner MUST preflight selected cases and fail with case IDs and missing prerequisites. An explicit scheduling exclusion outside the support matrix is different from a selected test skipping; the latter MUST fail a required job.
- **FR-005**: Every pytest case MUST declare exactly one of `tier1` or `tier2`. `tier1` covers fast, representative critical paths: query, validation rejection, ordinary apply, idempotence, and preservation of unmanaged state where those features exist. `tier2` covers the remaining required boundaries, combinations, failure paths, and supported-environment cases. Tiering is execution scheduling, not a weaker correctness standard. Collection MUST fail for missing or conflicting tier markers. Rust and legacy shell suites retain their native metadata but MUST have explicit runner inventory entries and gate assignments.
- **FR-006**: `slow` is an additional scheduling marker for a case whose required setup, exercise, and teardown is expected to exceed 30 seconds on the documented CI reference worker. It MUST include an expected runtime and reason, and MUST be `tier2`. Timings exceeding this threshold are reviewed rather than automatically relabeled. `--runslow` includes slow cases; omitting it deliberately deselects them and records their identities, rather than reporting them as passed or silently skipped. A gate requiring a slow case MUST schedule it before acceptance; a nightly job alone does not satisfy that gate.
- **FR-007**: The runner MUST require an explicit target mode. `build` names the source revision, build profile, target directory, and resulting executable; `installed` names an absolute executable path and MUST NOT invoke Cargo. It MUST pass the resolved absolute path through a single fixture/runner contract, such as `--netfyr-binary`, and every test MUST use that value. Missing targets are errors. Reports MUST record the executable hash, version, source/package identity when available, and environment versions.
- **FR-008**: Every new or changed functional requirement and acceptance case MUST map to test identities or an explicitly named manual review with retained evidence. Normal behavior, invalid inputs, relevant equivalence classes, numeric boundaries, and preservation/failure invariants MUST be covered. Each P0 story MUST have a representative tier1 check and its complete applicable boundary/failure coverage in the required gate. Lower-priority stories still require their full acceptance coverage before they are claimed implemented. There is no universal line-coverage percentage: measured coverage is supporting evidence, and uncovered changed logic must be reviewed and justified. Contract coverage is mandatory.
- **FR-009**: Tier1 MUST run on each pull request. Before merge, all cases mapped to changed behavior, the relevant tier2/slow cases, and the existing regression gates MUST pass on the final candidate. The support matrix MUST specify which environment cases are required before merge and which are periodic. A feature MUST NOT claim environment coverage based on an unrun required case. Required selection of zero tests, unexpected skips, or failed result parsing MUST fail the job.
- **FR-010**: Markers MUST have documented meanings and be registered under strict pytest marker checking. Scheduling markers (`tier1`, `tier2`, `slow`), feature markers (`query`, `apply`, `schema`, `ipv4`, and additions reviewed with the feature), and prerequisite metadata are distinct axes. Use pytest's existing `-m` AND/OR expressions rather than implementing another expression language. Target selection is runner input, not guessed independently by test files. Required CI filters and their inventories are reviewed configuration.
- **FR-011**: Assertion helpers MUST compare only the fields and equivalences allowed by the owning contract. They MUST preserve order when it is meaningful and MUST NOT erase unexpected state, lifetimes, errors, or read-only data merely to make comparisons pass. Subset matching checks every specified leaf; preservation checks separately cover the relevant unmodified state. `ip -j` or another independent kernel observer MUST verify kernel-facing changes, in addition to netfyr's own output.
- **FR-012**: Asynchronous assertions MUST poll a condition with an explicit monotonic deadline and bounded interval, failing with expected state, last observation, and elapsed time. The default helper deadline is 10 seconds with a 100 ms interval; a feature's declared timeout overrides it explicitly. Fixed sleeps MUST NOT substitute for readiness. Expiry and asynchronous factory tests are added when the feature defines those semantics; this harness does not invent them.
- **FR-013**: Privileged candidate execution MUST run in a disposable VM or another boundary that also isolates the host filesystem, credentials, and authoritative acceptance harness, as required by Test Driven Development P6. A network namespace alone isolates network state, not arbitrary privileged code. Within that boundary, per-test network namespaces provide fixture isolation. Fast pure tests remain available without privileged setup.
- **FR-014**: Reports MUST identify the candidate, harness and suite revisions, selected and executed cases, tier and environment, results, explicit exclusions, commands, and relevant diagnostics. They MUST retain the first failure when investigating flakiness and MUST NOT turn a retry into evidence that the original run passed. Emit JUnit for CI and retain replay material for deterministic or generated cases. Independent test authorship, challenge cases, and arbitration follow Test Driven Development; this runner must preserve their evidence and cannot waive their assertions.

### Key Entities

- **Test target**: The explicitly selected source build or installed executable.
- **Environment fixture**: Disposable resources created and cleaned independently of netfyr.
- **Requirement mapping**: Stable requirement/acceptance IDs linked to test cases or named manual evidence.
- **Test inventory**: Case identities, tier, prerequisites, features, support matrix, and gate membership.
- **Runner**: Selects the target, checks prerequisites, runs required native suites, and records complete results.

## Success Criteria

- **SC-001**: Successful, failed, and interrupted network tests leave host management state unchanged and do not rely on netfyr for cleanup.
- **SC-002**: Wrong MTU, wrong same-prefix address order, and changes to an unmanaged device are detected by the relevant assertions.
- **SC-003**: Missing or conflicting pytest tiers fail collection; every required suite has an explicit inventory and gate assignment.
- **SC-004**: Slow-case inclusion and exclusions are visible, and required slow cases cannot be omitted from acceptance.
- **SC-005**: Missing tools, privileges, kernel features, and selected executables fail explicitly before misleading pass results can be produced.
- **SC-006**: Feature and tier selection remains compatible with pytest, and zero or unexpectedly skipped required cases fail the gate.
- **SC-007**: The same acceptance suite can test an explicit local build and installed package without rebuilding or substituting the latter.
- **SC-008**: Every changed requirement has reviewed normal, boundary, failure, and preservation coverage where applicable, tied to the final candidate.

## Assumptions

- Depends on SPEC-000 for the workspace and existing test runner. This specification explicitly revises the shell-only rule and unconditional-build behavior for the cases described above.
- Feature specs define the commands and API behavior to test; the harness does not require an absent `netfyr show` command or invent lifecycle states.
- Namespace setup requires the declared namespace and network administration capabilities in the disposable execution environment; missing privileges are a preflight failure.
- The Test Driven Development document governs independent acceptance evidence and oracle review. This spec implements test infrastructure and coverage scheduling without replacing that policy.






















