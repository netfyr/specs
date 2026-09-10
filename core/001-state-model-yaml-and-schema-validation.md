# Feature Specification: State Model and YAML. 

Implement the core data model for network device state and the YAML serialization format. This is the foundational crate that every other crate depends on. All layers of netfyr (policies, reconciliation, backend, CLI) operate on the same state representation. The data model must support ordered collections and multiple configuration sources per device .

A `State` is the basic unit of configuration: one source's contribution to one device. Multiple sources (static user configuration, and dynamic providers such as DHCP, VPN, or IPv6 router advertisements) may each produce a `State` for the same device. This layer only **represents** those contributions; it deliberately does not combine them. Combining a device's contributions into one effective state requires knowing which contributions refer to the same physical device (a `name`-based contribution and a `mac`-based one may be the same interface), and that can only be determined against the live system. Merging is therefore the reconciliation layer's job; the state is a pure representation with no dependency on the live state.

## User Scenarios & Testing

### User Story 1 - Define Core Network State Types (Priority: P0)

This spec defines the foundational types every other crate builds on: `State`, `Match`, `Value`, and `Source`. A device (a network object managed by netfyr — typically a network interface such as an ethernet port, a wifi adapter, or a virtual device such as a bond or bridge) is not itself a type defined here: it exists only implicitly, as whatever a `Match` resolves to on the live system. What this crate defines instead is the shape of a *contribution* to a device: a `State` carries a device type (`device_type`) , a selector (`match_spec`) identifying the target, and the configuration fields being contributed. The same `State` type is used in two contexts: as desired state (a contribution from a user policy or a dynamic provider, with a partial match and empty device type) and as actual state (from the kernel, with a fully populated match and device type set). Because several sources may contribute to one device, a `State` also carries the source it came from and a priority, used later by the reconciliation layer to resolve conflicts when a device's contributions are merged.

**Why this priority**: Every other crate and feature depends on these core types. Nothing can be built without them.

**Independent Test**: Create `State` values with various field combinations, serialize and deserialize them, and verify all fields and metadata are preserved.

**Acceptance Scenarios**:

1. **Given** a State with match, fields, and metadata, **When** serialized and deserialized, **Then** all fields and metadata preserved. 

### User Story 2 - Match Network Devices by Selector (Priority: P0)

A developer creates `Match` values to identify which system device a state targets. Matching uses AND logic: every field set in the match must match the corresponding field in the other match; unset fields match anything; this allows partial matches (e.g., just `driver: ixgbe`).

**Why this priority**: Match logic is the foundation of policy-to-device binding. The reconciliation engine cannot function without it. Selecting by `name` is the only P0 *selector*; matching by other criteria (`driver`, `pci_path`, `mac`) is 
  supported but not on the P0 path 

**Independent Test**: Create Match values with various field combinations and verify AND logic, partial matching, and case-insensitive MAC comparison.

**Acceptance Scenarios**:

1. (P0) **Given** a match with name="eth0", **When** compared against a device with name="eth0", type="ethernet", driver="ixgbe", **Then** it matches.
2. (P0) **Given** a match with name="eth0", **When** compared against a device with name="eth1", type="ethernet", driver="ixgbe", **Then** it does not match.
3. (P1) **Given** a match with name="eth0" and type="ethernet", **When** compared against a device with name="eth0", type="ethernet", driver="ixgbe", **Then** it matches.
4. (P1) **Given** a match with name="eth0" and type="ethernet", **When** compared against a device with name="eth1", type="ethernet", **Then** it does not match.

### User Story 3 - Serialize and Parse YAML Configuration (Priority: P0)

A user uses YAML to represent and exchange network configuration. The two YAML formats differ only in whether they carry a `match:` section: the query output format (what `netfyr query` prints) places the device's fields at the top level with no `match:` section, since netfyr already knows which device it queried; the policy format (what a user writes for `netfyr apply`) adds a `match:` section identifying the target device, alongside the same fields. In both formats the fields are structured the same way: base properties at the top level, protocol- and technology-specific properties grouped into sub-objects such as `ipv4` and `ethernet` (see FR-011). Multiple devices are expressed within a single YAML document as a top-level sequence (list) of these mappings, one entry per device. Both formats must round-trip correctly, preserving list element order  (the Linux kernel uses the first address on an interface as the primary source address for outgoing connections).

**Why this priority**: YAML is the primary user-facing configuration format. Both apply and query workflows depend on correct serialization.

**Independent Test**: Parse YAML in both formats, verify match extraction, value deserialization heuristic, and round-trip fidelity.

**Acceptance Scenarios**:

1. **Given** YAML with a `match:` sub-mapping and config fields, **When** parsed, **Then** match fields are extracted and remaining keys become state fields.
2. **Given** query output YAML containing name="eth0" and mtu=9000, **When** passed to `netfyr apply` without a `match:` section, **Then** a match is auto-generated with name="eth0" and read-only fields are dropped with a per-key warning; the exit code is not affected by the warnings.
3. **Given** query output YAML containing mac="aa:bb:cc:dd:ee:ff", **When** passed to `netfyr apply --match-by mac`, **Then** a match is auto-generated with mac="aa:bb:cc:dd:ee:ff".
4. **Given** YAML value "10.0.1.0/24", **When** deserialized, **Then** it becomes `Value::IpNetwork`, not `Value::String`.
5. **Given** a single YAML document containing a top-level list of two device mappings, **When** parsed, **Then** two States are produced, one per list entry, in list order.
6. **Given** YAML with addresses `[{ip: "10.0.1.2/24"}, {ip: "10.0.1.1/24"}]`, **When** parsed and re-serialized, **Then** the order is preserved.

### Edge Cases

- What happens when a YAML value could be parsed as multiple types? The value deserialization heuristic resolves ambiguity in a fixed order (see FR-012).
- What happens when two loaded entries (list elements) target the same device? Both are kept as separate contributions (the intended multi-source case, not an error). Resolving them against a real device and merging is the reconciliation layer's job.


## Requirements

### Functional Requirements

- **FR-001**: `State` MUST contain the following fields:

  - `device_type`: the technology type of the device (e.g., `"ethernet"`), serialized as the top-level `type` field (FR-011). It is empty for desired-state contributions from policies (a policy identifies its target through `match_spec`, and may constrain type there rather than setting it) and populated for actual state queried from the kernel. When not set explicitly it MAY be implied by a technology sub-object such as `ethernet` (FR-011). The backend routes diff operations to the correct implementation by device type.
  - `match_spec`: a `Match` identifying which device this state targets.
  - `fields`: an ordered map of field names to `Value`s. Must use an ordered map (e.g., `IndexMap`) so that serialized output is deterministic, making configs reproducible and diffs meaningful.
  - `source`: a `Source` indicating which source produced this contribution (see FR-003).
  - `priority`: an `i32` used to resolve conflicts when several contributions set the same field. Higher value wins. Its default is derived from the source kind (see FR-003) and can be overridden by the policy or provider that produced the state.
  - `metadata`: a `StateMetadata`.

- **FR-002**: `Value` MUST be an enum with variants: `String`, `U64`, `I64`, `Bool`, `IpAddr` (both v4/v6), `IpNetwork` (both v4/v6 CIDR), `List(Vec<Value>)`, `Map` (ordered map of String to Value).

- **FR-003**: `Source` MUST identify what produced a `State`, with variants:
  - `Static { policy }`: the static fields of a user policy; `policy` identifies which policy. Default priority 100.
  - `Dhcp { policy }`: a DHCP provider declared by a policy. Default priority 50.
  - `Ra { policy }`: an IPv6 router-advertisement (SLAAC) provider declared by a policy. Default priority 25.
  - `Vpn { policy }`: a VPN provider declared by a policy. Default priority 75.
  - `Kernel`: read from the running kernel.

  `Source` is per-`State` because each `State` is exactly one source's contribution to one device. The invariant to preserve is the default precedence `Static > Vpn > Dhcp > Ra`: static user configuration wins over dynamic sources unless the user overrides a priority. The exact default numbers are a recommendation; the ordering is not. A device is configured by the *merge* of all its contributions (performed by the reconciliation layer), and attribution of individual fields to their winning source lives on the merged state produced there, not on `State`. 



- **FR-005**: `Match` MUST have optional fields: `name`, `type`, `driver`, `pci_path`, `mac` (case-insensitive comparison). Matching MUST use AND logic: every field set in self must match the other; unset fields match anything. This asymmetry allows a partial match (from a policy) to match a fully-populated match (from the kernel).

- **FR-006**: Virtual devices (bonds, bridges, VLANs) MUST be representable with the same `State`, `Match`, and `device_type` model as physical interfaces, differing only in their `device_type` and technology sub-object. A `Match` can select an *existing* device or can express the intent to *create* one; declaring that a virtual device should be created requires an explicit declaration, kept distinct from a match that would merely configure the device when it is present. Creating and deleting virtual devices is future work; this spec covers only how their state is represented.

- **FR-007**: Desired and actual configuration MUST be represented as an *ordered list of `State`s* (`Vec<State>`). The list MUST NOT merge, deduplicate, or reject contributions: several `State`s may target the same physical device (through the same or different match forms). The data model itself MUST NOT combine them into an effective per-device state, because doing so requires resolving each contribution's `Match` against the live system to know which contributions target the same device (a contribution matching `{name: eth0}` and one matching `{mac: 00:01:02:03:04:05}` may be the same interface, but only a layer that can query the kernel can determine that). Merge (priority resolution, list union, per-field provenance) is therefore defined by the reconciliation layer, which queries actual devices first, not here; keeping merge out of this crate is what lets `netfyr-state` remain a pure representation with no dependency on system state. Actual (kernel) state is the same kind of list, populated with one `Kernel` contribution per discovered device. 

- **FR-008**: The system MUST support two YAML formats:
  - **Query output format** (what `netfyr query` produces): properties grouped by domain, no `match:` section.
    ```yaml
    name: eth0
    type: ethernet
    mac: "aa:bb:cc:dd:ee:ff"
    driver: ixgbe
    carrier: true
    enabled: true
    mtu: 9000
    ipv4:
      addresses:
        - ip: 10.0.1.50/24
    ethernet:
      speed: 1000
    ```
    
  - **Policy format** (what the user writes for `netfyr apply`): `match:` section identifies the target, remaining keys become state fields.
    ```yaml
    match:
      name: eth0
    mtu: 9000
    ipv4:
      addresses:
        - ip: 10.0.1.50/24
    ```
    
  - **Multi-device form** (either format): a single document MAY carry a top-level sequence of the mappings above, one list entry per device. Each entry is parsed exactly as it would be as a standalone single-device document, producing one `State` per entry in list order. A document whose top level is a mapping (the single-device examples above) remains valid and produces exactly one `State`.
    ```yaml
    # query output, multiple devices
    - name: eth0
      type: ethernet
      mtu: 9000
      ipv4:
        addresses:
          - ip: 10.0.1.50/24
    - name: eth1
      type: ethernet
      mtu: 1500
    ```
    ```yaml
    # policy, multiple devices
    - match:
        name: eth0
      mtu: 9000
    - match:
        name: eth1
      mtu: 1500
    ```
 
- **FR-009**: The `kind` key, if present, MUST distinguish bare states (`kind: state` or absent) from policy wrappers (`kind: policy`); the policy format is defined in its own spec.

- **FR-010**: The query-edit-apply workflow MUST be supported: when `netfyr apply` receives YAML without a `match:` section (e.g., piped from `netfyr query`), it auto-generates a `Match` using a configurable strategy. The default strategy uses the interface name. Read-only fields are dropped rather than rejected, since a policy could never have set them; dropping (not erroring) is what keeps the query-edit-apply pipe usable unattended. This MUST NOT be silent: `netfyr apply` emits a warning per dropped top-level key (naming the key and, for known read-only fields, that it isn't settable by policy) so a user can tell an intentional-but-ineffective edit apart from a typo'd field name, without the exit code or workflow being affected. The matching strategy can be overridden from the command line (e.g., `--match-by mac`). This enables: `netfyr query eth0 > eth0.yaml`, edit a field, `netfyr apply eth0.yaml`.

- **FR-011**: Properties MUST be grouped into sub-objects by domain:
  - Base-level properties (common to all device types) sit at the top level: `name`, `type`, `mac`, `carrier`, `driver`, `enabled`, `mtu`.
  - Protocol-specific properties are nested: `ipv4` groups IPv4 addressing.
  - An IP address MUST be modelled as an object, not a bare string: `{ ip: <CIDR>, valid_lft?: <seconds>, preferred_lft?: <seconds> }`. This is a substantive choice rather than a cosmetic one: dynamic sources such as DHCP produce addresses with lifetimes, and the reconciliation layer's merge deduplicates addresses by their `ip` while preserving the winning contribution's lifetime attributes.
  - Technology-specific sub-objects: `ethernet` (carries hardware properties like speed), `wifi`.
  - The presence of a technology sub-object implies the device type when it is not explicitly set (e.g., `ethernet` key implies type `"ethernet"`).
  - The exact set of fields, their types, and which are writable vs read-only are defined by the schema validation spec.

- **FR-012**: Value deserialization heuristic (order matters, because a CIDR string like "10.0.1.0/24" must parse as a network, not lose the prefix length):
  1. YAML boolean -> `Bool`
  2. Non-negative integer -> `U64`
  3. Negative integer -> `I64`
  4. String -> try `IpNetwork` first, then `IpAddr`, then `String`

- **FR-013**: `Source`, `priority`, and per-field provenance MUST NOT be serialized in the state YAML. Source and per-field provenance are runtime metadata, not user-facing configuration. A bare state deserialized from YAML gets `Source::Static` with the default static priority; a policy may override the priority (see the policy spec). Per-field provenance is produced by the reconciliation layer's merge, surfaced through query/API output, and never accepted as input.

- **FR-014**: Metadata MUST NOT be preserved through YAML round-trip; fresh `StateMetadata` is created on deserialization.

- **FR-015**: A single YAML document whose top level is a sequence MUST produce one `State` per element, in list order; a document whose top level is a mapping MUST produce exactly one `State`. This top-level list is the sole way to express multiple devices in one input: multi-document YAML (`---` separator) is NOT part of the format, and encountering a `---` document separator MUST be reported as an error rather than silently splitting the input.

- **FR-016**: List element order MUST be preserved through the entire pipeline (parsing, serialization, reconciliation, kernel application). This matters because the Linux kernel uses the first address on an interface as the primary/source address for outgoing connections.

- **FR-017**: Ordered maps MUST be used for `State.fields` and `Value::Map`. Insertion order must be preserved so that serialized output is deterministic.

### Key Entities

- **Device**: A network object managed by netfyr (e.g., a physical interface such as an ethernet port, or a virtual device such as a bond or bridge). Not a type defined by this crate: it is identified implicitly by matching a `Match` against the live system, and is the implicit target of one or more `State` contributions.
- **State**: One source's contribution to one device. Contains device_type, match_spec, fields, source, priority, and metadata.
- **Value**: Enum representing configuration values with variants for String, U64, I64, Bool, IpAddr, IpNetwork, List, and Map.
- **Source**: What produced a `State`: `Static`, `Dhcp`, `Ra`, `Vpn` (dynamic/user sources, each carrying the originating policy), or `Kernel` for system-queried state (no policy). Determines the default priority.
- **StateMetadata**: Contains `id` (UUIDv7) and `created_at`.

- **Match**: Identifies which system device a state targets. Optional fields (name, type, driver, pci_path, mac) with AND logic and asymmetric matching.

## Success Criteria

- **SC-001**: A State's YAML-representable content (`match_spec`, `device_type`, `fields`) round-trips through serialization exactly, including element order. Runtime-only fields are not preserved: a deserialized state gets `Source::Static` with the default static priority (FR-013) and fresh StateMetadata (FR-014).
- **SC-002**: Match AND logic correctly matches partial matches against fully populated matches, and rejects mismatches.
- **SC-003**: Configuration is represented as an ordered list of States; distinct contributions are stored separately, with no keying or deduplication.
- **SC-004**: The list of States preserves every appended contribution in insertion order, merging or dropping none, even when two contributions target the same device through different match forms.
- **SC-005**: Both YAML formats (query output and policy) parse and serialize correctly.
- **SC-006**: Value deserialization heuristic correctly prioritizes IpNetwork over IpAddr over String.
- **SC-007**: List element order is preserved through parse-serialize round-trips.

## Assumptions

- Depends on SPEC-000 (project setup).
- Crate: `crates/netfyr-state` (library), added to the workspace.
















