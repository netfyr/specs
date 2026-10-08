# Feature Specification: State Model

Implement the core in-memory representation of network device state. This is the foundational crate that every other netfyr crate builds on. Policies, reconciliation, backends, and user interfaces all operate on the same model, but this specification defines only that model. External document formats, schema lookup, validation, and conversion between documents and model values are defined by later specifications.

A `State` is one source's contribution to one device. Multiple sources, such as static user configuration, DHCP, VPN, IPv6 router advertisements, and the kernel, may each produce a `State` for the same device. This layer represents those contributions without combining them. Combining contributions requires resolving their selectors against live devices, so merging belongs to the reconciliation layer rather than the state model.

## User Scenarios & Testing

### User Story 1 - Represent Network State (Priority: P0)

A developer represents desired or actual network state with the same core types: `State`, `Match`, `Value`, `Source`, and `StateMetadata`. A state identifies its target, records one source's configuration contribution, and carries runtime bookkeeping.

**Why this priority**: Every other crate and feature depends on these types.

**Independent Test**: Construct states containing every value variant and verify that their fields, source, priority, match, device type, and metadata behave as specified without using an external data format.

**Acceptance Scenarios**:

1. **Given** a source, **When** `State::new()` creates a state, **Then** the state has that source's default priority, an empty device type, an empty match, no fields, and fresh metadata.
2. **Given** two states with equal model content but different source, priority, and metadata, **When** their content is compared, **Then** they are considered content-equal.
3. **Given** an IP address with a prefix such as `10.0.1.50/24`, **When** it is stored as an IP-network value, **Then** the host bits are preserved.

### User Story 2 - Select Network Devices (Priority: P0)

A developer uses `Match` to identify the live device targeted by a state. Matching is asymmetric and uses AND logic: every selector set in the candidate match must be present and equal in the live device's match, while unset selectors are wildcards.

**Why this priority**: Device selection is the basis for binding desired contributions to actual devices.

**Independent Test**: Compare partial and fully populated matches and verify AND logic, asymmetric behavior, wildcard behavior, and case-insensitive MAC comparison.

**Acceptance Scenarios**:

1. **Given** `{name: eth0}`, **When** it is matched against a fully populated device match whose name is `eth0`, **Then** it matches.
2. **Given** `{name: eth0}`, **When** it is matched against a device match whose name is `eth1`, **Then** it does not match.
3. **Given** `{name: eth0, driver: ixgbe}`, **When** either field differs or is absent in the device match, **Then** it does not match.
4. **Given** a lowercase MAC selector and the same MAC in uppercase in the device match, **When** they are compared, **Then** they match without changing either stored value.
5. **Given** an empty match, **When** it is compared with any device match, **Then** it matches.

### User Story 3 - Keep Contributions Ordered and Separate (Priority: P0)

A developer stores desired or actual configuration as an ordered list of states. Several states may target the same physical device, including through different selectors. The state model retains every contribution in insertion order and does not merge, deduplicate, reject, or resolve them.

**Why this priority**: Correct merging requires live-system knowledge that a pure representation layer does not have. Order is also significant for values such as address lists, where the first address can be the primary source address.

**Independent Test**: Build a list containing multiple contributions to one device and nested ordered values, then verify that all states, fields, map entries, and list elements retain their positions.

**Acceptance Scenarios**:

1. **Given** two states with the same selector, **When** both are appended to a configuration, **Then** both remain present in insertion order.
2. **Given** one state matching by name and another matching by MAC, **When** both may refer to the same live device, **Then** the model does not attempt to resolve or merge them.
3. **Given** an ordered address list, **When** it is stored and read from the model, **Then** element order is unchanged.
4. **Given** two maps with the same entries in different insertion orders, **When** they are compared as `Value::Map`, **Then** they are not equal.

### Edge Cases

- A selector set in the candidate match but absent in the live device's match is a mismatch.
- MAC matching is ASCII case-insensitive; all other match fields are case-sensitive.
- Virtual and physical devices use the same model. Creation and deletion intent is not inferred from an ordinary match.
- Multiple contributions targeting one device are expected and are not an error.
- The model assigns no meaning to the spelling of a `String`; interpreting text according to a field definition is outside this specification.

## Requirements

### Functional Requirements

- **FR-001**: The project MUST add `crates/netfyr-state` as a library crate and workspace member. At this stage the crate MUST be a pure in-memory representation layer: it MUST NOT parse or emit external configuration documents, load field schemas, infer a value type from string contents, query the live system, or merge contributions.

- **FR-002**: `State` MUST contain:
  - `device_type`: the technology type of the target device, such as `"ethernet"`. It is typically empty for a desired-state contribution without a type constraint and populated for actual state.
  - `match_spec`: a `Match` identifying the target device.
  - `fields`: an insertion-ordered map of field names to `Value`s.
  - `source`: the `Source` that produced this contribution.
  - `priority`: an `i32` conflict-resolution weight. Higher values win when a later layer merges contributions.
  - `metadata`: runtime-only `StateMetadata`.

- **FR-003**: `State::new(source)` MUST use the source's default priority and create an empty device type, empty match, empty field map, and fresh metadata.

- **FR-004**: `Value` MUST be a closed enum with these variants:
  - `String`
  - `U64`
  - `I64`
  - `Bool`
  - `IpAddr`, supporting IPv4 and IPv6
  - `IpNetwork`, supporting an IPv4 or IPv6 address plus a prefix length
  - `List(Vec<Value>)`
  - `Map`, containing an insertion-ordered map from `String` to `Value`

  The model has no floating-point or null variant. `IpNetwork` MUST retain the address exactly as supplied, including host bits; for example, `10.0.1.50/24` MUST NOT be normalized to `10.0.1.0/24`.

- **FR-005**: `Value::List` element order and `Value::Map` insertion order MUST be significant and preserved. Equality for maps MUST compare entries positionally, including in nested maps.

- **FR-006**: `Match` MUST have optional fields `name`, `type`, `driver`, `pci_path`, and `mac`.

- **FR-007**: `Match::matches(other)` MUST be asymmetric. Every field set in `self` MUST be set in `other` and equal; fields unset in `self` match anything. Conditions MUST be combined with AND logic. MAC addresses MUST compare case-insensitively without normalizing their stored spelling. Other fields MUST compare case-sensitively.

- **FR-008**: `Match` MUST report whether it is empty. An empty match MUST match every other match.

- **FR-009**: `Source` MUST identify what produced a state. Implementations SHOULD use these default priorities:

  | Source | Default priority |
  |--------|-----------------:|
  | `Static { policy }` | 100 |
  | `Vpn { policy }` | 75 |
  | `Dhcp { policy }` | 50 |
  | `Ra { policy }` | 25 |
  | `Kernel` | 0 |

  `policy` identifies the originating policy for policy-backed sources and MUST be available from those variants; `Kernel` has no policy identifier. A producer MAY override the default on an individual state. Regardless of the exact numbers chosen, the default precedence MUST be `Static > Vpn > Dhcp > Ra > Kernel`.

- **FR-010**: `StateMetadata` MUST contain a UUIDv7 `id` and a `created_at` timestamp. Every newly created state MUST receive fresh metadata.

- **FR-011**: The model MUST provide content comparison for states. Content comparison MUST include `device_type`, structural `match_spec` equality, field keys, field values, and field order. It MUST exclude `source`, `priority`, and `metadata`, which describe runtime origin rather than configuration content. Structural match equality is spelling-sensitive, so two differently cased MAC values can match under FR-007 without making their containing states content-equal.

- **FR-012**: Desired and actual configuration MUST be represented as an ordered `Vec<State>`. This collection MUST NOT key, merge, deduplicate, or reject contributions. Resolving matches against live devices, priority conflict resolution, list union, and per-field provenance belong to the reconciliation layer.

- **FR-013**: Virtual devices such as bonds, bridges, and VLANs MUST be representable with the same `State`, `Match`, and `device_type` model as physical interfaces. A normal match MUST NOT by itself imply that a missing virtual device should be created; explicit lifecycle intent is future work.

### Key Entities

- **Device**: A network object managed by netfyr. It is not a type defined by this crate; it is the implicit target obtained by resolving a `Match` against the live system.
- **State**: One source's contribution to one device.
- **Value**: A closed, recursively nestable configuration value with ordered collection variants and semantic IP variants.
- **Match**: An asymmetric, partial selector for a live device.
- **Source**: The origin of a contribution and the basis for its default priority.
- **StateMetadata**: A fresh runtime identity and creation timestamp for a state object.

## Success Criteria

- **SC-001**: `cargo build` and `cargo test` succeed with `netfyr-state` as a workspace member.
- **SC-002**: Every `Value` variant can be constructed and compared according to the model contract, including order-sensitive nested maps and host-bit-preserving IP networks.
- **SC-003**: Match tests cover partial matching, AND behavior, asymmetry, empty matches, missing fields, and case-insensitive MAC comparison.
- **SC-004**: Source defaults preserve the precedence in FR-009, use the recommended values unless there is a documented reason not to, and remain overridable per state.
- **SC-005**: New states receive distinct UUIDv7 metadata and a creation timestamp.
- **SC-006**: State content comparison is order-sensitive and ignores source, priority, and metadata.
- **SC-007**: An ordered list retains every contribution in insertion order, including contributions that may target the same device.
- **SC-008**: The state-model implementation contains no external document codec, field schema, or string-content type inference.

## Assumptions

- Depends on SPEC-000 (project setup).
- Crate: `crates/netfyr-state` (library), added to the workspace.
- Schema validation and external document representation are defined by SPEC-002.
- Reconciliation and interaction with live devices are defined by later specifications.
