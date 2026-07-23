# Feature Specification: Project Setup

Set up the Rust workspace scaffolding, project metadata, and integration test infrastructure. This spec creates no library or binary crates -- those are added by subsequent specs as needed. It establishes the project foundation so that build system, testing conventions, and project metadata are in place before any feature work begins.

## User Scenarios & Testing

### User Story 1 - Set Up Rust Workspace (Priority: P0)

A developer clones the repository and runs `cargo build`. The workspace compiles with no errors. The repository contains essential project files (README, LICENSE, CHANGELOG, CONTRIBUTING) so that contributors and packagers know how to participate and what terms apply.

**Why this priority**: This is the foundation that every other spec builds on. Nothing can be developed until the workspace exists.

**Independent Test**: Clone the repository and run `cargo build`; verify it succeeds.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** the developer runs `cargo build`, **Then** the build succeeds.

### User Story 2 - Run Integration Tests with Tag Filtering (Priority: P1)

A developer runs the test runner to discover and execute all shell-based integration tests in `tests/`. The test runner supports filtering by tags so developers can run only the tests relevant to their current work without needing to know spec numbers or internal organization. OR filtering (`TAGS=ipv4,schema`) runs tests matching any listed tag; AND filtering (`TAGS=ipv4+routing`) runs tests matching all listed tags.

**Why this priority**: Tag filtering is critical for developer productivity as the test suite grows. Without it, developers must run the full suite or manually invoke individual scripts.

**Independent Test**: Create sample test scripts with tag declarations and run the test runner with various `TAGS=` arguments.

**Acceptance Scenarios**:

1. **Given** the test runner is invoked, **When** it starts, **Then** `cargo build` runs first and all `tests/*.sh` scripts are discovered and executed.
2. **Given** tests tagged "ipv4" and tests tagged "schema", **When** the test runner is invoked with `TAGS=ipv4,schema`, **Then** both ipv4 and schema tests are executed but tests with neither tag are skipped.
3. **Given** a test tagged "ipv4 routing" and a test tagged only "ipv4", **When** the test runner is invoked with `TAGS=ipv4+routing`, **Then** only the test tagged with both is executed.

### User Story 3 - Enforce No-Skip Test Policy (Priority: P1)

A CI operator runs the test suite. If a test cannot run because a prerequisite is missing (binary not built, `unshare` not available, required tool not installed), the test fails explicitly -- it prints "FAIL: ..." to stderr and exits with code 1. Tests never exit 0 when a prerequisite is missing, ensuring problems are caught immediately rather than silently ignored in CI.

**Why this priority**: Silent skips mask real problems. An explicit failure ensures that missing prerequisites are caught immediately in CI.

**Independent Test**: Run a test script with a missing prerequisite and verify it exits with code 1 and prints a failure message to stderr.

**Acceptance Scenarios**:

1. **Given** a test script with a missing prerequisite, **When** the test script is executed, **Then** it prints a failure message to stderr and exits with code 1.

### Edge Cases

- What happens when a test has no tag declaration? It should still be discovered and executed when no tag filter is active; it is excluded when a tag filter is specified.
- How does the system handle non-test shell files in the tests directory? They should be placed in a subdirectory or sourced by test scripts rather than being executable tests themselves. The `*.sh` glob pattern in `tests/` discovers test scripts.

## Requirements

### Functional Requirements

- **FR-001**: The project MUST use a Rust workspace with `resolver = "2"` (default for Rust 2024 edition; provides correct feature resolution in workspaces -- the v1 resolver can unify features across build targets in unexpected ways).
- **FR-002**: The workspace MUST start with an empty `members` list. Crates live under `crates/`; each subsequent spec adds its crate(s) to the workspace.
- **FR-003**: The repository MUST include:
  - `README.md` -- what netfyr does (declarative Linux network configuration tool using netlink) and how to build and test.
  - `LICENSE` -- reuse terms must be clear from the start for contributors and packagers.
  - `CHANGELOG.md` -- tracks user-visible changes across releases, giving downstream users and packagers a way to assess upgrade impact.
  - `CONTRIBUTING.md` -- covering: how work is organized (each spec is an independent deliverable assigned to a developer; read your spec's dependencies first), development workflow (`cargo build`, `cargo test`, test runner with tag filtering), code conventions (Rust 2024 edition, `cargo fmt`, `cargo clippy`, dependency policy), integration test conventions (shell scripts, tag declaration, no-skip policy), and submitting changes (PR expectations: what the change does and why, passing CI, one spec per PR).
- **FR-004**: The project MUST follow a strict dependency policy: only add an external dependency when implementing the functionality from scratch would be unreasonable (e.g., `rtnetlink` for netlink, `clap` for CLI, `tokio` for async); prefer the standard library over third-party crates; when choosing between crates with similar functionality, prefer the one with fewer transitive dependencies. This keeps the tool lean -- faster builds, smaller binaries, fewer supply-chain risks, easier auditing.
- **FR-005**: Unit tests MUST use standard Rust `#[cfg(test)]` modules within each source file. They are run via `cargo test` and cover internal logic: parsing, validation, data structure invariants, and pure functions. Unit tests should not depend on external tools, network namespaces, or built binaries.
- **FR-006**: The boundary between unit and integration tests: unit tests (`cargo test`) verify internal correctness of library code; shell integration tests (`tests/*.sh`) verify CLI behavior, system interaction, and end-to-end workflows. When in doubt, prefer a unit test -- they are faster, more deterministic, and easier to debug.
- **FR-007**: Integration tests MUST be shell scripts in `tests/`, not Rust integration tests. Shell scripts exercise the CLI the same way a user would, and anyone can read or modify them without knowing Rust. This spec establishes the conventions; concrete test helper functions (for network namespace setup, veth pair creation, etc.) will be introduced by the spec that first needs them.
- **FR-008**: Test scripts MUST use descriptive names like `set-mtu.sh` or `yaml-roundtrip.sh`.
- **FR-009**: Each test script MUST declare its tags in a comment near the top:
  ```bash
  #!/bin/bash
  # tags: ipv4 routing backend
  ```
  Tags are free-form (no central registry) and describe what the test exercises (e.g., `ipv4`, `routing`, `schema`, `build`, `query`, `apply`).
- **FR-010**: The test runner MUST support tag filtering:
  - OR (match any): `run-tests TAGS=ipv4,routing` -- runs tests tagged with `ipv4` or `routing`.
  - AND (match all): `run-tests TAGS=ipv4+routing` -- runs tests tagged with both `ipv4` and `routing`.
- **FR-011**: Test scripts MUST be able to locate built binaries reliably, both when run from the project root during development and from CI with custom build directories.
- **FR-012**: Tests MUST follow the no-skip policy: if a prerequisite is missing, fail explicitly. Never `exit 0` on a missing prerequisite. Example:
  ```bash
  command -v unshare >/dev/null || { echo "FAIL: unshare not available" >&2; exit 1; }
  ```
- **FR-013**: The test runner MUST be a script that discovers and executes `tests/*.sh`, supporting `TAGS=` filtering. It MUST run `cargo build` first to ensure binaries exist.
- **FR-014**: The repository MUST include a setup script that installs git hooks: a pre-commit hook running `cargo fmt --check` (fast formatting check on every commit) and a pre-push hook running `cargo clippy` (slower lint check before pushing).

### Key Entities

- **Workspace**: Root `Cargo.toml` with empty `members` list, `resolver = "2"`. Crates added by subsequent specs under `crates/`.
- **Test Runner**: Script that discovers `tests/*.sh`, runs `cargo build` first, supports `TAGS=` filtering with OR and AND modes.
- **Test Script**: Shell script in `tests/` with a tag declaration comment near the top.

## Success Criteria

- **SC-001**: `cargo build` succeeds on a fresh clone.
- **SC-002**: The test runner discovers and executes all `tests/*.sh` scripts.
- **SC-003**: Tag-based filtering correctly handles both OR (`TAGS=a,b`) and AND (`TAGS=a+b`) modes.
- **SC-004**: A test with a missing prerequisite exits with code 1 and prints a failure message to stderr.

## Assumptions

- Rust 2024 edition  is used throughout.
- No library or binary crates exist yet; they are added by subsequent specs.
- This spec has no dependencies on other specs.

