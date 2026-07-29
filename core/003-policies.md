# Feature Specification: Policies

Implement the policy data model and state production. Policies are the user-facing unit of configuration -- they wrap desired state with metadata (name, match) so the system can identify what entity to target. Each entity must be configured by exactly one policy; duplicate targeting is rejected at load time to keep the model unambiguous. The reconciliation engine (SPEC-2xx) then merges desired state against current system state. The bare-state shorthand makes the common case trivial: a user drops a YAML file describing an interface and it just works.


## User Scenarios & Testing

### User Story 1 - Define and Load Explicit Policies (Priority: P0)

A user writes a YAML policy with `kind: policy` to declare desired configuration for a network entity. The policy contains a name, a match identifying the target, and state fields describing what should be configured. Processing a policy produces a `StateSet` with provenance tracking.

**Why this priority**: Policies are the primary input to the reconciliation engine. Without them, the system has no desired state to apply.

**Independent Test**: Create a policy with inline state fields, produce state, and verify the resulting StateSet has correct fields and provenance.

**Acceptance Scenarios**:

1. **Given** a policy with inline state setting mtu=1500, **When** state is produced, **Then** the StateSet contains one state with mtu=1500 and the state has `Provenance::User` with the policy name.
2. **Given** a policy with no state fields, **When** state production is called, **Then** an error is returned.
3. **Given** policy A targets eth0 with mtu=9000 and policy B targets eth1 with enabled=true, **When** `produce_all()` is called, **Then** the result has two states, one for eth0 and one for eth1.
4. **Given** policy A targets eth0 with mtu=1500 and policy B also targets eth0 with mtu=9000, **When** `produce_all()` is called, **Then** a DuplicateEntity error is returned.

### User Story 2 - Auto-Wrap Bare State YAML as Policies (Priority: P1)

A user drops a YAML file describing an interface without using the full `kind: policy` syntax. When a YAML document has no `kind:` field (or `kind: state`), it is auto-wrapped into a policy. The policy name is derived from the filename. This makes the common case trivial -- a user drops a YAML file and it just works without needing to learn the full policy syntax.

**Why this priority**: The bare-state shorthand is the primary onboarding experience. Most users will start with simple YAML files before learning the policy syntax.

**Independent Test**: Load a bare-state YAML file and verify it produces a correctly named policy with the expected match and fields.

**Acceptance Scenarios**:

1. **Given** a file "eth0.yaml" containing YAML with match and fields but no kind, **When** loaded via `load_policy_file`, **Then** a policy named "eth0" is produced.
2. **Given** a file "switches.yaml" with 2 YAML documents, **When** loaded via `load_policy_file`, **Then** policies named "switches-1" and "switches-2" are produced.

### User Story 3 - Load Policies from Directories (Priority: P1)

An administrator organizes policies in a directory tree. The system loads all `.yaml`/`.yml` files recursively, skipping hidden files (dot-prefix). Duplicate policy names across files are rejected to prevent ambiguity about which policy is active.

**Why this priority**: Directory-based loading is essential for the standard three-tier configuration system (`/usr/lib`, `/etc`, `/run`).

**Independent Test**: Create a directory with multiple YAML files (including hidden files and subdirectories), load via `load_policy_dir`, and verify correct files are loaded and duplicates are rejected.

**Acceptance Scenarios**:

1. **Given** a directory with "eth0.yaml" and "subdir/eth0.yaml", **When** loaded via `load_policy_dir`, **Then** an error is returned about duplicate policy name "eth0".
2. **Given** a directory with ".backup.yaml" and "eth0.yaml", **When** loaded via `load_policy_dir`, **Then** only "eth0.yaml" is loaded.

### Edge Cases

- What happens with mixed files (bare + explicit policy documents in the same file)? Each document is handled per its `kind` -- both are valid in the same file.
- What happens with unknown `kind` values? They produce errors.
- How are policy names derived from files with multiple YAML documents? Single-document files get no suffix; multi-document files get a numeric suffix (`"filename-1"`, `"filename-2"`).

## Requirements

### Functional Requirements

- **FR-001**: A policy MUST have three parts:
  - `name` -- unique identifier (e.g., `"eth0-config"`).
  - `match_spec` -- a `Match` (from SPEC-001) identifying the target entity.
  - `state` -- inline configuration fields (an ordered map of field names to values).

- **FR-002**: State production from a policy MUST:
  1. Copy the policy's inline state fields into a `State`.
  2. Set `provenance` to `Provenance::User` with the policy name.
  3. Set the `Match` from the policy's `match_spec`.
  4. Wrap in a `StateSet` and return.
  An error MUST be returned if the policy has no state fields.

- **FR-003**: `PolicySet` MUST be a keyed collection of policies. `produce_all()` processes every policy and collects the results into a `StateSet`. If two policies target the same entity (same match key), it MUST return a `DuplicateEntity` error.

- **FR-004**: A YAML document with `kind: policy` MUST be parsed as a policy:
  ```yaml
  kind: policy
  name: my-eth0
  match:
    name: eth0
  state:
    mtu: 9000
    ipv4:
      addresses:
        - ip: 10.0.1.50/24
  ```
  The `match` section builds the `Match` struct. The `state` section contains the configuration fields to apply.  
  An optional `metadata` map MAY be present. It holds free-form key-value pairs (e.g., labels, timestamps, `managed-by` tags) that the engine preserves but does not interpret. This allows third-party tools to annotate policies without a schema change.
- **FR-005**: When a YAML document has no `kind:` field (or `kind: state`), it MUST be auto-wrapped into a policy:
  ```yaml
  # eth0.yaml -- auto-wrapped into a policy named "eth0"
  match:
    name: eth0
  mtu: 9000
  ipv4:
    addresses:
      - ip: 10.0.1.50/24
  ```
  - Policy name derived from the filename stem (e.g., `eth0.yaml` -> `"eth0"`).
  - Multi-document files get a numeric suffix (`"filename-1"`, `"filename-2"`). Single-document files get no suffix.
  - Mixed files (bare + explicit policy documents) are valid; each handled per its `kind`.
  - Unknown `kind` values produce errors.

- **FR-006**: `load_policy_file(path)` MUST read YAML, auto-wrap bare states, and return `Vec<Policy>`.

- **FR-007**: `load_policy_dir(path)` MUST load all `.yaml`/`.yml` from a directory (recursive), reject duplicate policy names across files, and skip hidden files (dot-prefix), since editors and version control often create dotfiles that should not be treated as policies.

### Key Entities

- **Policy**: A named unit of desired configuration. Contains a unique name, a match spec identifying the target entity, and inline state fields.
- **PolicySet**: A keyed collection of policies. Produces a combined `StateSet` via `produce_all()`, rejecting duplicate entity targets.

## Success Criteria

- **SC-001**: A policy with inline state fields produces a StateSet with correct fields and `Provenance::User`.
- **SC-002**: Policies with no state fields produce an error.
- **SC-003**: `PolicySet.produce_all()` combines disjoint policies and rejects duplicate entity targets.
- **SC-004**: Bare-state YAML files are auto-wrapped into correctly named policies.
- **SC-005**: Directory loading skips hidden files and rejects duplicate policy names.

## Prior Art

- **NetworkManager profiles** (keyfiles in `/etc/NetworkManager/system-connections/`): One file per connection profile, keyed by a UUID. Profiles bind to interfaces via `interface-name`, `mac` or `match.*` properties. Multiple profiles can target the same interface; activation is manual or auto-connect priority based. Netfyr differs by enforcing one policy per entity at load time and using a declarative match instead of UUID identity.
- **systemd-networkd** (`.network` / `.link` files): Match-based like netfyr -- a `[Match]` section selects interfaces by name, MAC, driver, etc. Multiple files can match the same interface; the first match wins (by filename sort order). Netfyr rejects overlapping matches rather than relying on file ordering, making conflicts explicit.
- **Netplan** (YAML under `/etc/netplan/`): Declarative YAML keyed by interface name, rendered to a backend (NetworkManager or networkd). Closest in spirit to netfyr's bare-state shorthand. Netplan merges across files by key; netfyr treats duplicate policy names as errors. Netplan is backend-agnostic glue; netfyr owns the full stack from YAML to netlink.

The key netfyr distinctions are: match-based targeting (not UUID or fixed name keys), strict one-policy-per-entity enforcement (no implicit merge or priority ordering), and the bare-state shorthand that makes the common single-interface case as simple as dropping a YAML file. The one-file-per-policy, one-policy-per-entity constraint deliberately simplifies the model: there is no merge ordering to reason about, no priority tiebreaking, and no hidden interaction between files. This also makes the system straightforward to drive via an API -- creating, updating, or deleting a policy is a single-object operation with no side effects on other policies.


## Assumptions

- Depends on SPEC-000 (project setup) and SPEC-001 (State, StateSet, YAML parsing, Match, Provenance).
- Crate: `crates/netfyr-policy` (library), depends on `netfyr-state`.
- Later specs will introduce factory trigger fields (e.g., `ipv4.dhcp: true`) that activate dynamic state providers. The policy model and YAML format do not change; only the processing pipeline is extended to recognize trigger fields and route them to factory instances.


