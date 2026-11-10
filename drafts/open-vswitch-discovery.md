---
title: SPEC-012 — Open vSwitch Discovery
tags: [spec, draft]
owner: qinqon
namespace: netfyr/specs
area: plugins
depends-on: [10, 11, 15, 16, 17, 18, 22]
---

# Feature Specification: Open vSwitch Discovery

Report the Open vSwitch (OVS) bridges, ports, and interfaces held in the host's OVSDB as observed state. Discovery is read-only: netfyr reads the database, never writes to it, and gains no ownership of what it reports. Each bridge, port, and interface is reported with its relationships, its OVSDB identity, and selected metadata, with secret values withheld.

Creating and deleting bridges, attaching and detaching ports, VLAN and bond settings, tunnel configuration, OpenFlow, QoS, mirrors, and controllers are separate deliverables. They need the lifecycle and relationship contracts that SPEC-005 FR-006 and FR-008 reserve. So are change subscription, drift handling for OVS devices (philosophy P8), and joining OVS interfaces with kernel links. This spec defines what an OVS observation contains and how it fails. It defines no calling interface: how a query reaches discovery belongs to the engine, which is specified separately. nmstate-shaped output is a translation over this representation (P9) and is also a separate spec.

OVS is technology-specific, so under philosophy P2 it belongs in a plugin, not in core. The plugin host and manifest contract (P3) are not specified yet; this spec fixes the behavior and leaves packaging to them. Discovery is a one-shot read that needs no netfyr daemon (P5), only a running `ovsdb-server`.

## User Scenarios & Testing

### User Story 1 - See the OVS Topology (Priority: P0)

An administrator queries a host and sees each OVS bridge, the ports on it, and the interfaces in each port. Every port names its bridge and every interface names its port and bridge. The result describes what OVSDB holds. It does not say what netfyr manages.

**Why this priority**: Topology is the reason to look at OVS at all, and every later OVS feature plans against it.

**Independent Test**: Start a private `ovsdb-server`, populate it with `ovs-vsctl --no-wait`, and compare netfyr's observation with `ovs-vsctl list` on the same database.

**Acceptance Scenarios**:

1. **Given** a bridge `br0` with ports `br0` and `eth1`, **When** OVS devices are queried, **Then** the result has one `ovs_bridge` named `br0` with `ports` `[br0, eth1]`, two `ovs_port` devices whose `bridge` is `br0`, and two `ovs_interface` devices that each name their `port` and `bridge`.
2. **Given** a port `bond0` with interfaces `eth2` and `eth3`, **When** queried, **Then** `bond0` has `interfaces` `[eth2, eth3]` and both interfaces have `port` `bond0`.
3. **Given** `eth1` was added without an interface type and `br0` is the bridge's local interface, **When** queried, **Then** `ovs_interface.type` is `system` for `eth1` and `internal` for `br0`.
4. **Given** that topology, **When** the selector is `{type: ovs_bridge}`, **Then** only the bridge is returned. **When** it is `{name: br0}`, **Then** the OVS devices returned are the bridge, the port, and the interface named `br0`, each with its own type.
5. **Given** an initialized database with no bridges, **When** queried, **Then** no OVS device is returned and the discovery status is `available`.
6. **Given** unchanged database content, **When** queried twice, **Then** the two observations are identical, including the order of devices, list elements, and map entries.

### User Story 2 - Tell Missing OVS from Broken OVS (Priority: P0)

Most hosts do not run OVS. Some run it and it is down. An administrator can tell apart "no OVS on this host", "OVS has no bridges", and "OVS could not be read". A failed read is never shown as an empty topology and does not discard what the kernel reported.

**Why this priority**: An empty result that might mean a failure cannot be acted on, and a failure that hides kernel state makes every host without a readable OVS look broken.

**Independent Test**: Query with nothing at the endpoint path, a socket with no listener, a socket the caller may not open, and a listener that never replies; inspect the status and the remaining observations each time.

**Acceptance Scenarios**:

1. **Given** nothing exists at the endpoint path and mode `auto`, **When** queried, **Then** the status is `absent`, no OVS device is returned, nothing is logged above debug level, and observations from SPEC-004's backend are returned as usual.
2. **Given** nothing exists at the endpoint path and mode `required`, **When** queried, **Then** the status is `failed` and names the endpoint.
3. **Given** a socket the caller may not open, **When** queried, **Then** the status is `failed` with a permission error, and observations from SPEC-004's backend are still returned.
4. **Given** a socket with no listener, or a server that does not offer the `Open_vSwitch` database, **When** queried, **Then** the status is `failed` and tells a refused connection from an unsupported database, naming what is missing.
5. **Given** a listener that accepts the connection and never replies, **When** queried, **Then** the status is `failed` with an exceeded deadline, no later than the configured deadline.
6. **Given** a `failed` status, **When** the selector is `{type: ovs_bridge}`, **Then** the query reports the failure. It does not return an empty result or NotFound.
7. **Given** mode `disabled`, **When** queried, **Then** no connection is attempted and the status is `disabled`.

### User Story 3 - Read Metadata Without Reading Secrets (Priority: P1)

An administrator reads `external_ids`, `other_config`, and interface `options` to see who created a port or where a tunnel points. An IPsec pre-shared key stored in `options:psk` never appears, in output or in logs. The administrator can still see that one is set.

**Why this priority**: The topology is useful without metadata. Once metadata is reported, withholding secrets is not optional (philosophy P10).

**Independent Test**: Store a known marker string as `options:psk`, query, and search every output, diagnostic, and log produced at the highest verbosity for the marker.

**Acceptance Scenarios**:

1. **Given** interface `gre0` with `options:remote_ip=192.0.2.10` and `options:psk` set, **When** queried, **Then** `options` contains `remote_ip` only, `redacted.options` is `[psk]`, and the stored PSK appears in no output, diagnostic, or log at any verbosity.
2. **Given** `external_ids` values `0123`, `true`, and `192.0.2.1`, **When** queried, **Then** each is reported as that string, not as a number, a boolean, or an address.
3. **Given** the redaction setting names `external_ids:token` on `ovs_port`, **When** a port carries that key, **Then** its value is withheld and `redacted.external_ids` is `[token]`.
4. **Given** an interface with `options:key=5`, **When** queried, **Then** `key` is reported with value `5`: it is a tunnel identifier and is not classified.
5. **Given** a device with no metadata, **When** queried, **Then** its maps are present and empty and it has no `redacted` field.

### User Story 4 - Leave OVS and Plans Untouched (Priority: P0)

Discovery changes nothing. The database is the same after a query as before it, and turning discovery on does not change what apply does.

**Why this priority**: netfyr shares hosts with the tools that own these bridges (philosophy P8). A read that could write, or that changed a plan, would break that boundary.

**Independent Test**: Dump the database, query repeatedly, dump again, and compare. Plan the same policies with discovery enabled, disabled, and failed, and compare the plans.

**Acceptance Scenarios**:

1. **Given** a populated database, **When** it is queried any number of times, **Then** `ovsdb-client dump` output is identical before and after.
2. **Given** a policy matching `{name: eth1}` that sets MTU, and `eth1` exists both as a kernel link and as an OVS port and interface, **When** planned with discovery enabled, disabled, and failed, **Then** the three plans are identical and no operation targets an OVS device.
3. **Given** a policy whose selector has `type: ovs_bridge`, **When** planned, **Then** it produces no operation and is reported as unmatched, with a diagnostic stating that the type is observation-only.
4. **Given** a policy that sets a field under `ovs_bridge`, **When** validated, **Then** `validate_writable()` returns a ReadOnlyField error and nothing is changed.

### Edge Cases

- A bridge, its local port, and its local interface normally share one name. They are three devices with three types. A selector without `type` returns all of them.
- OVS creates kernel links: the datapath device (`ovs-system`) and each internal interface. SPEC-004's backend reports those with their kernel link kind, `openvswitch`, and base fields, unchanged by this spec. They are not OVS devices. A matching name is not proof that an OVS interface and a kernel link are the same device: the database may serve an OVS instance in another network namespace, and a DPDK interface has no kernel link.
- OVSDB holds configuration that `ovs-vswitchd` is asked to realize. An OVS device in an observation says the row exists. It does not say the datapath carries traffic for it. Rows are reported the same way while `ovs-vswitchd` is stopped.
- A bridge owned by a CNI plugin, such as an OVN integration bridge, is reported like any other. Reporting it is not managing pod networking, which stays out of scope under the philosophy.

## Requirements

### Functional Requirements

- **FR-001**: OVS discovery MUST only read. It MUST NOT issue an OVSDB operation that changes the database (`insert`, `update`, `mutate`, `delete`), take an OVSDB lock, start, stop, or signal Open vSwitch services, or change a datapath or a kernel link. No input, including query output passed back to apply (SPEC-001 FR-010), may cause a write to OVSDB under this spec.

- **FR-002**: Each `Bridge` row referenced by the `Open_vSwitch` root row, each `Port` row those bridges reference, and each `Interface` row those ports reference MUST be reported as one `State` with `device_type` `ovs_bridge`, `ovs_port`, or `ovs_interface` and the row's `name`. OVSDB keeps `name` unique per table, so `(type, name)` identifies one device in one database; one name under two types is two devices. An OVS device carries the base fields `name` and `type` only: `mac`, `mtu`, `enabled`, `carrier`, and `driver` describe kernel links and stay with SPEC-004.

- **FR-003**: Each device type has one schema fragment under SPEC-002, keyed by a sub-object named after the type, which implies the type (SPEC-001 FR-011). Every field is read-only.

  | Field | Type | Content |
  |-------|------|---------|
  | `ovs_bridge.uuid` | string | Row identity (FR-005) |
  | `ovs_bridge.datapath_type` | string | `datapath_type` (FR-006) |
  | `ovs_bridge.ports` | array of strings | Names of the bridge's ports (FR-004) |
  | `ovs_bridge.external_ids` | map of strings | `external_ids` |
  | `ovs_bridge.other_config` | map of strings | `other_config` |
  | `ovs_bridge.redacted` | map of arrays of strings | Withheld keys by column (FR-014) |
  | `ovs_port.uuid` | string | Row identity (FR-005) |
  | `ovs_port.bridge` | string | Name of the port's bridge (FR-004) |
  | `ovs_port.interfaces` | array of strings | Names of the port's interfaces (FR-004) |
  | `ovs_port.external_ids` | map of strings | `external_ids` |
  | `ovs_port.other_config` | map of strings | `other_config` |
  | `ovs_port.redacted` | map of arrays of strings | Withheld keys by column (FR-014) |
  | `ovs_interface.uuid` | string | Row identity (FR-005) |
  | `ovs_interface.bridge` | string | Name of the port's bridge (FR-004) |
  | `ovs_interface.port` | string | Name of the interface's port (FR-004) |
  | `ovs_interface.type` | string | `type` (FR-006) |
  | `ovs_interface.options` | map of strings | `options` |
  | `ovs_interface.external_ids` | map of strings | `external_ids` |
  | `ovs_interface.other_config` | map of strings | `other_config` |
  | `ovs_interface.redacted` | map of arrays of strings | Withheld keys by column (FR-014) |

  Every field is present for every device of its type, except `redacted` and a parent field omitted under FR-004; an empty column is an empty map. A map of strings has free-form string keys and string values. These are the first such fields in the schema: the fragments MUST declare them that way and validation MUST reject a non-string value. SPEC-002's pinned field-set tests (FR-008, SC-005) cover the fragments.

  Example for a bridge `br0` with a tunnel port `gre0`. The port and interface named `br0` are left out for brevity:

  ```yaml
  - name: br0
    type: ovs_bridge
    ovs_bridge:
      uuid: 3d2f6c1e-8a53-4c0e-9c4e-0f6d3b1a7e21
      datapath_type: system
      ports:
        - br0
        - gre0
      external_ids: {}
      other_config: {}
  - name: gre0
    type: ovs_port
    ovs_port:
      uuid: 9b7e4a2c-51d8-4f3b-a6c0-2e8d7f1b4a65
      bridge: br0
      interfaces:
        - gre0
      external_ids: {}
      other_config: {}
  - name: gre0
    type: ovs_interface
    ovs_interface:
      uuid: 7d0c2e56-3c1f-4b7a-9a52-1f0e6b2d9c03
      bridge: br0
      port: gre0
      type: gre
      options:
        remote_ip: "192.0.2.10"
      external_ids: {}
      other_config: {}
      redacted:
        options:
          - psk
  ```

- **FR-004**: `ports` and `interfaces` MUST list the names of the rows the parent references. `bridge` and `port` MUST name the parent that references the device; an interface's `bridge` is its port's bridge. Both directions come from one snapshot (FR-009) and MUST agree. OVSDB does not prevent a port from being referenced by several bridges, or an interface by several ports. In that case the parents' lists are reported as stored, each affected device omits every parent field that has no single value, and a diagnostic names the rows. Discovery MUST NOT pick a parent.

- **FR-005**: `uuid` MUST be the row's `_uuid` in lowercase hyphenated text. It identifies the row while the row exists: a device deleted and created again under the same name has a different `uuid`. This spec only reports it; a later lifecycle spec can bind plans to it as SPEC-005 FR-013 does for interfaces.

- **FR-006**: Values MUST be reported as stored, with two declared equivalences: an empty `Interface.type` is `system`, which Open vSwitch documents as its synonym, and an empty `Bridge.datapath_type` is `system`, the datapath Open vSwitch uses for it. Other type strings are reported unchanged, including ones this spec does not name. Map keys and values MUST be strings exactly as stored. OVSDB sets and maps are unordered while `Value::List` and `Value::Map` are ordered (SPEC-001), so discovery MUST apply a canonical order that carries no meaning: devices by type (`ovs_bridge`, `ovs_port`, `ovs_interface`) then name, list elements and map keys bytewise. Unchanged database content MUST produce an identical observation.

- **FR-007**: Selection among OVS devices MUST use SPEC-001's `Match`. An observed OVS device has `name` and `type` set and `mac`, `driver`, and `pci_path` unset, so a selector that sets one of those three never matches an OVS device. A selector without `type` matches devices of every type. This spec adds no selector field.

- **FR-008**: OVS devices are observed state and MUST carry the state model's observed-state source, `Source::Kernel` today. They MUST NOT be in the inventory supplied to SPEC-005's planner, so no policy binds to them and no operation targets them. Planning and apply MUST NOT depend on OVS discovery; its status MUST NOT fail or alter them. A policy whose selector names an OVS device type MUST be reported as unmatched, with a diagnostic stating that the type is observation-only. SPEC-002's `validate_writable()` rejects a policy that sets a field of these fragments.

- **FR-009**: Discovery MUST read the `Open_vSwitch` database from exactly one OVSDB endpoint, a local Unix socket named by a setting (FR-011), with no fallback to another. It MUST use the OVSDB management protocol ([RFC 7047](https://www.rfc-editor.org/rfc/rfc7047)) and MUST NOT run `ovs-vsctl` or another command-line tool, because separate commands do not read one snapshot. All rows of an observation MUST come from one consistent snapshot, so a relationship never joins rows read at different moments. Discovery MUST work while `ovs-vswitchd` is not running. `tcp:` and `ssl:` endpoints are out of scope: they need credentials (philosophy P10) and can name a database on another host (P7). An endpoint is a filesystem path, not a resource of a network namespace: an observation MUST identify its endpoint and asserts nothing about the network namespace the OVS instance operates in.

- **FR-010**: Discovery MUST depend only on these columns: `Open_vSwitch.bridges`; `_uuid`, `name`, `ports`, `datapath_type`, `external_ids`, and `other_config` of `Bridge`; `_uuid`, `name`, `interfaces`, `external_ids`, and `other_config` of `Port`; `_uuid`, `name`, `type`, `options`, `external_ids`, and `other_config` of `Interface`. A server without the `Open_vSwitch` database, or a schema lacking one of these tables or columns, is an unsupported database. Other tables and columns MUST be ignored.

- **FR-011**: Discovery MUST be controlled by these named settings (philosophy P13). Where they are stored and how a caller supplies them belongs to the engine and configuration contracts.

  | Setting | Meaning | Default |
  |---------|---------|---------|
  | Endpoint | Path of the OVSDB server's Unix socket | `/run/openvswitch/db.sock` |
  | Mode | `auto`, `required`, or `disabled` (FR-012) | `auto` |
  | Deadline | Upper bound for one observation, from connecting to the last reply | 5 seconds |
  | Redaction additions | Extra `(device type, column, key)` entries whose values are withheld (FR-014) | none |

- **FR-012**: Every observation MUST carry exactly one discovery status:

  | Status | When | OVS devices |
  |--------|------|-------------|
  | `available` | The snapshot was read | Those in the snapshot; none if there are no bridges |
  | `absent` | Mode is `auto` and nothing exists at the endpoint path | None |
  | `disabled` | Mode is `disabled`; no connection is attempted | None |
  | `failed` | Any other outcome, including a missing endpoint in mode `required` | None |

  `absent` is not a failure and MUST NOT be logged above debug level. `failed` MUST identify the endpoint and distinguish permission denied, connection refused or reset, deadline exceeded, unsupported database (FR-010), and undecodable reply.

- **FR-013**: A snapshot is reported whole or not at all: a `failed` observation has no OVS device and MUST NOT be represented as an empty topology. It MUST NOT discard or fail observations from SPEC-004's backend. A query that would return no device while the status is `failed` MUST report the failure instead of NotFound or an empty result, unless its selector cannot match an OVS device (FR-007); SPEC-004 FR-010 sets the same rule for a failed inventory read. The failure has SPEC-004's `PermissionDenied` meaning for a permission error and `QueryFailed` otherwise. The caller MUST present it through its diagnostic interface (philosophy P11); discovery MUST NOT write to output streams.

- **FR-014**: Unclassified keys are reported with their values. A value classified as secret MUST NOT appear in observed state, rendered output, diagnostics, or logs at any verbosity, protocol traces included (philosophy P10). The classification is a set of exact `(device type, column, key)` entries: `(ovs_interface, options, psk)` is built in and the redaction setting (FR-011) adds more. Matching MUST be exact, never by pattern: `key`, `in_key`, and `out_key` in `options` are tunnel identifiers, not secrets. A classified key MUST be removed from its map before observed state is built and its name listed under `redacted.<column>`; `redacted` is present only when a value was withheld. No placeholder value is put in a map: once these maps become writable, a placeholder could be written back over the stored value. The key name is the reference P10 lets observed state carry. P10's fingerprint needs a credential provider that is not specified yet, so none is reported.

- **FR-015**: Decoding the database reply and building observed state from it MUST be a deterministic function of the reply and the settings, with no I/O, clock, or environment input. Undecodable, inconsistent, and reordered replies MUST be testable without a database server (SPEC-008 FR-001).

- **FR-016**: Integration tests MUST run against a real `ovsdb-server` that the fixture starts on a fixture-owned socket and database file inside SPEC-008's disposable environment, populated with `ovs-vsctl --no-wait`. They MUST NOT connect to the environment's default OVSDB socket and MUST NOT need `ovs-vswitchd`, a datapath, or kernel devices. Expected results come from an independent observer, `ovs-vsctl list` or `ovsdb-client dump` (SPEC-008 FR-011). `ovsdb-server`, `ovsdb-tool`, `ovs-vsctl`, `ovsdb-client`, and `vswitch.ovsschema` are declared prerequisites (SPEC-008 FR-004). Cases carry the feature marker `ovs` (SPEC-008 FR-010), and the support matrix names the Open vSwitch versions they run against. Until the engine exposes query, a probe binary drives discovery, as in the SPEC-004 suite.

### Key Entities

- **OVS device**: A bridge, port, or interface configured in OVSDB, reported as one `State` of type `ovs_bridge`, `ovs_port`, or `ovs_interface`. It states configuration, not datapath state.
- **Kernel link**: An interface observed by SPEC-004's backend. A kernel link that OVS created has the kernel link kind `openvswitch`; it is not an OVS device.
- **OVSDB endpoint**: The Unix socket of the `ovsdb-server` that discovery reads.
- **Snapshot**: One consistent read of the columns in FR-010.
- **Discovery status**: `available`, `absent`, `disabled`, or `failed`, carried by every observation.
- **Redaction classification**: The exact `(device type, column, key)` entries whose values are withheld.

## Success Criteria

- **SC-001**: Observed bridges, ports, interfaces, and their relationships agree with `ovs-vsctl` on the same database, for single-interface ports and for bonds.
- **SC-002**: Two observations of unchanged content are identical, and reordering rows, set members, or map entries in a reply does not change the observation.
- **SC-003**: `available` with no bridges, `absent`, `disabled`, and each `failed` reason are distinguishable. No failure yields an empty topology, and a failed read leaves SPEC-004 observations intact.
- **SC-004**: A stored `psk` value and any value classified by the administrator appear in no output, diagnostic, or log. Their key names appear under `redacted`.
- **SC-005**: Map values are reported as the stored strings, including values that look like numbers, booleans, and addresses.
- **SC-006**: `ovsdb-client dump` is identical before and after any number of observations.
- **SC-007**: Plans are identical with discovery enabled, disabled, and failed. No operation targets an OVS device, and `validate_writable()` rejects every field of the three fragments.
- **SC-008**: The suite fails an implementation that reports a classified value, reports a failed read as an empty topology, or sends a modifying operation.
- **SC-009**: Ambiguous parent references, unsupported databases, and undecodable replies have tests for their distinct outcomes.

## Prior Art

- **NetworkManager** models OVS with three connection types, `ovs-bridge`, `ovs-port`, and `ovs-interface`, one per OVSDB table, each child naming its parent. This spec uses the same one-device-per-row shape.
- **nmstate** reports an `ovs-bridge` interface with a nested `port` list carrying per-port VLAN and `link-aggregation` settings, an `ovs-interface` type for internal, patch, and DPDK interfaces, and `ovs-db` for `external_ids` and `other_config`. A system interface attached to a bridge keeps its own type and names the bridge as its controller. That shape can be produced from this one by grouping ports under their bridge, the translation P9 calls for. nmstate also reports bridge options (STP, RSTP, multicast snooping, fail mode), port VLAN and bond settings, interface MTU, and the global `ovs-db` section, which this version does not. Adding them is additive under P12.

## Assumptions

- Depends on SPEC-000 (dependency policy), SPEC-001 and `core/006-state-model` (`State`, `Match`, `Value`, `Source`; only what the two agree on), SPEC-002 (fragments, writability), SPEC-004 (error meanings and the kernel view, which this spec leaves unchanged), SPEC-005 (the planner inventory), and SPEC-008 (test infrastructure).
- The Engine and CLI proposals are in SpecDoc and not merged. The Engine draft injects one namespace-bound backend; composing a second observation source with it and rendering the discovery status is engine work. Nothing here requires a particular signature. User Story 4 scenarios 2 and 3 and FR-013's query rule are acceptance cases for that integration.
- Crate: `crates/netfyr-ovs` (library), depending on `netfyr-state`, separate from `netfyr-backend`. A read-only client needs RFC 7047's `get_schema` and `transact` with `select` over a Unix socket; SPEC-000 FR-004 decides whether that is written in-tree or taken as a dependency.
- The validator implemented for SPEC-002 accepts closed objects and a boolean `additionalProperties` only; FR-003's maps of strings need an object whose additional properties are strings. If the schema-generation proposal lands first, the fragments are declared the way it requires.
- Reading the socket needs the access the operating system grants on it, normally root or the `openvswitch` group. A one-shot query uses the caller's access and adds none. Who may read OVS metadata through a daemon is an authorization decision at the core boundary (philosophy P4), for the engine and API specs.

## Open Questions

Each has a default above. They are listed so review can change them; this section is removed before approval.

1. **Source name.** OVS observations use `Source::Kernel` (FR-008), the model's only observed-state source, though OVSDB is not the kernel. Renaming the variant or adding one is a state-model change.
2. **Type names.** `ovs_bridge`, `ovs_port`, and `ovs_interface` follow the snake_case of schema keys. NetworkManager and nmstate use hyphens.
3. **Redaction default.** Unclassified keys are reported (FR-014), because `external_ids` exists to carry identifiers netfyr cannot enumerate. An allowlist is safer against a secret under an unknown key and hides most of what the column is for.
4. **Namespace association.** SPEC-004 binds observations to a network namespace; an OVSDB endpoint has none (FR-009). How the engine places OVS devices next to a namespace-bound inventory is open.
5. **Realization status.** `Interface.ifindex`, `error`, `ofport`, and `link_state` say whether `ovs-vswitchd` realized a row and which kernel link backs it. They are left out to keep this version to configuration; adding them is additive (P12).
