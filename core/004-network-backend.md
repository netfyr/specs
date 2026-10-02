# Feature Specification: Network Backend

Query Linux interface state and execute the explicit operation plans defined by SPEC-005 through an asynchronous `NetworkBackend` boundary. Linux I/O belongs here; policy binding, priority merging, and address reorder decisions belong to reconciliation. The initial backend configures physical Ethernet interfaces and veth devices. It reports other interfaces without claiming to manage them.

## User Scenarios & Testing

### User Story 1 - Query Network Interface State (Priority: P0)

A user queries the interfaces in the backend's network namespace. Supported Ethernet and veth devices include base fields, IPv4 addresses, and available Ethernet attributes. Bridges, bonds, VLANs, loopback, and other unsupported types include base fields only. The result describes observed state, not ownership.

**Independent Test**: Create isolated veth and bridge devices, assign an IPv4 address, and inspect backend output against `ip -j` observations.

**Acceptance Scenarios**:

1. **Given** a namespace with a veth pair, **When** queried, **Then** both endpoints have available base fields, `type: ethernet`, `ipv4.addresses`, and `Source::Kernel`; only supported ethtool attributes appear in `ethernet`.
2. **Given** eth0 and eth1, **When** queried by name eth0, **Then** only eth0 is returned.
3. **Given** a bridge carrying an IPv4 address, **When** queried, **Then** it is identified as a bridge and has base fields but neither `ipv4` nor `ethernet` in this initial backend.
4. **Given** no interface named doesnotexist, **When** queried by that name, **Then** `BackendError::NotFound` is returned.
5. **Given** an unparseable optional attribute, **When** queried, **Then** that field is omitted and a diagnostic identifies the device and attribute; other valid data remains available.
6. **Given** ethtool does not support speed, duplex, or autonegotiation on a device, **When** queried, **Then** unavailable fields are omitted without invented zero or false values and the link query still succeeds.

### User Story 2 - Execute an Explicit Plan (Priority: P0)

A caller passes a validated plan targeting discovered Ethernet devices. The backend executes its operations in order and reports the result of each. It does not broaden a field operation into a link-wide reset.

**Independent Test**: Plan an MTU assignment and an address addition, execute them in an isolated namespace, and verify the resulting kernel state independently.

**Acceptance Scenarios**:

1. **Given** a veth with MTU 1500, **When** a plan sets MTU 9000 and adds `10.0.1.50/24`, **Then** both changes are independently observable in the kernel.
2. **Given** operations on two devices and a failure on the first, **When** executed, **Then** independent operations on the second are attempted, and the report identifies the failed operation and its error.
3. **Given** a specific IPv4 address removal, **When** executed, **Then** that address is removed, the interface still exists, and its administrative state is unchanged unless separately requested.
4. **Given** the exact requested address and lifetime settings already exist, **When** that address is added again, **Then** the operation is skipped as already satisfied. Different attributes are not silently treated as success.
5. **Given** two addresses in the same IPv4 prefix and a plan rebuilding their order, **When** executed, **Then** the first planned address is primary for that prefix and unrelated prefix groups remain intact.
6. **Given** a failed operation with dependent later steps, **When** execution continues, **Then** those dependent steps are skipped with a dependency-failed reason and independent steps remain eligible.

### User Story 3 - Preview Without Changing the System (Priority: P1)

A user previews the same plan apply would execute, including address removals and rebuilds. A dry run validates supported operations and current targets but cannot promise that the kernel will accept a future write.

**Independent Test**: Preview an MTU change and verify both the reported old/new values and unchanged kernel state.

**Acceptance Scenarios**:

1. **Given** MTU 1500 and a planned value of 9000, **When** dry run is requested, **Then** the change is reported while kernel MTU remains 1500.
2. **Given** a deleted target or unsupported device, **When** previewed, **Then** the report identifies the invalid target and performs no writes.
3. **Given** a plan requiring an address-group rebuild, **When** previewed, **Then** every affected removal and addition is visible.

## Requirements

### Functional Requirements

- **FR-001**: `NetworkBackend` MUST be an async, Send+Sync boundary with `query(match)`, `query_all()`, `apply(diff)`, `dry_run(diff)`, and `supported_entities()`. Query selection MUST use SPEC-001's `Match`. One backend instance is bound to a network namespace; sockets MUST be created in that namespace and MUST NOT accidentally query the caller's host namespace.
- **FR-002**: `BackendRegistry` MUST route operations by the discovered entity type and supported operation set. Unsupported types or operations MUST return `UnsupportedEntityType` or `UnsupportedOperation` for that operation. The registry MUST NOT interpret every Ethernet-link-layer device as a manageable physical interface: bridge, bond, VLAN, and other kernel link kinds retain their actual type. Veth is an explicit supported Ethernet case for this implementation.
- **FR-003**: `ApplyReport` MUST contain ordered `succeeded`, `failed`, and `skipped` entries. Every entry MUST identify the original operation index, namespace, interface identity and name, operation kind, and field or address target. A failed entry MUST carry its `BackendError`, diagnostic message, and kernel errno/extack when available. A skipped entry MUST distinguish already-satisfied, read-only, and dependency-failed reasons. `is_success()` MUST be false if any operation failed or was blocked by a failed dependency; a partially changed host MUST never be reported as fully applied.
- **FR-004**: `DryRunReport` MUST expose the plan's field changes, old and desired values, concrete operations, and diagnostics. It MUST include target and capability validation failures. It MUST NOT send mutating netlink requests or count planned operations as successful writes.
- **FR-005**: `BackendError` MUST distinguish `UnsupportedEntityType`, `UnsupportedOperation`, `QueryFailed`, `ApplyFailed`, `NotFound`, `PermissionDenied`, `StaleState`, and `Internal`. Errors MUST retain the target and operation context specified by FR-003. Cancellation and transport failures MUST not be reported as success; unattempted dependent operations are reported as blocked.
- **FR-006**: The `NetlinkBackend` MUST enumerate all interfaces in its namespace. It MUST report available base fields (`name`, `type`, `mac`, `carrier`, `enabled`, `mtu`, and available selector identity). Ethernet and veth devices additionally receive `ipv4.addresses` and available ethtool attributes (`speed`, `duplex`, `autoneg`). Other device types receive base fields only in this version. All observations use `Source::Kernel`, the name used by SPEC-001. The implementation MUST NOT use a host `/sys/class/net` traversal as a substitute for namespace-aware discovery.
- **FR-007**: Apply MUST support only physical Ethernet and veth devices in this version. Querying a device or observing its address does not grant ownership. Bridge, bond, VLAN, loopback, and other unsupported targets MUST be rejected without changing them. Later specifications may add their management semantics.
- **FR-008**: Query matching MUST follow SPEC-001, including AND semantics and case-insensitive MAC comparison. Missing identity attributes do not satisfy a selector that requires them. A name-selected missing interface returns NotFound; a broader selector with no matches returns an empty result.
- **FR-009**: IPv4 address query MUST report assigned `AF_INET` addresses from address notifications/dumps, including secondary, finite-lifetime, and link-local addresses. No address flag reliably establishes that a different userspace manager owns an address, so none may be filtered merely as "kernel-managed." Routes, broadcast attributes, and IPv6 records are not separate IPv4 address entries. Ownership is decided from policy and explicit field management in SPEC-005, not inferred from `IFA_F_PERMANENT` or a guessed static/dynamic distinction. Malformed address data MUST be diagnosed as an incomplete observation, not silently converted to an empty managed list.
- **FR-010**: Unavailable optional ethtool fields MUST be omitted. A driver-reported unknown duplex may use the schema's `unknown` enum, but an unsupported query MUST NOT fabricate a value. Unexpected transport or parsing failures MUST produce structured diagnostics; failure to obtain the link/address inventory required for safe planning MUST return QueryFailed or an explicitly incomplete observation that prevents destructive planning. Optional enrichment failure alone MUST NOT discard otherwise valid link data.
- **FR-011**: Before mutating a target, apply MUST check the plan's namespace and interface identity and the observation preconditions needed by a destructive address sequence. Preconditions for later steps MUST account for successful earlier operations in the same plan. A disappeared or replaced target returns NotFound or StaleState. Unexpected changed membership or attributes in an affected address group require a fresh plan; the backend MUST NOT silently widen the removal set.
- **FR-012**: Apply MUST execute the planner's order, including explicit dependencies. The planner puts requested link-level changes before address operations and supplies any address-group rebuild. The backend MUST NOT independently remove all addresses or infer a reorder from a final list. An unchanged field generates no request.
- **FR-013**: Operations MUST be idempotent where the requested outcome is already satisfied: setting the current MTU or administrative state, adding the same address with the same requested attributes, and removing an already absent address are skipped. An existing address with different requested attributes requires an explicit replacement; treating every EEXIST as satisfied is forbidden.
- **FR-014**: Apply MUST continue with independent operations after a failure and MUST skip operations that depend on the failed step. Results MUST distinguish actual changes from attempts and blocked work. This is a partial-completion contract, not an atomic transaction or automatic rollback guarantee. Checkpoint orchestration belongs to the high-level apply path under philosophy P6.
- **FR-015**: Address removal MUST target only the planned address. Any kernel removal of secondaries when a primary is deleted MUST already be covered by the explicit affected-group plan in SPEC-005, including restoration of still-desired members. Address removal MUST NOT take the link down or delete the interface. Deconfiguration is expressed through explicit field/address operations, including `enabled: false` when requested. Whole-entity Add/Remove operations are unsupported until a lifecycle specification defines them; they MUST NOT be interpreted as an implicit deconfiguration shortcut.
- **FR-016**: Read-only fields reaching the executor defensively MUST be skipped and identified in the report. The normal schema-validated planner emits no such operations. Unknown writable operations MUST fail rather than be silently ignored.
- **FR-017**: Address additions MUST follow the explicit planned sequence. For addresses in the same IPv4 prefix this controls primary/secondary ordering; it is not a guarantee that the first address globally becomes the source for every destination. Route selection, preferred-source settings, and address scope also matter. This distinction follows Linux's [IPv4 address implementation](https://github.com/torvalds/linux/blob/master/net/ipv4/devinet.c). Tests MUST verify the declared same-prefix case and preservation of other groups rather than assert an unconditional global source-address rule.
- **FR-018**: Dry run MUST share operation decoding and nonmutating validation with apply, show all potentially disruptive operations, and leave all kernel state unchanged. A target can change after dry run; apply MUST still perform FR-011's checks.

### Key Entities

- **NetworkBackend**: Namespace-bound query and operation-execution interface.
- **BackendRegistry**: Dispatches operations to the backend that supports the target.
- **NetlinkBackend**: Linux rtnetlink implementation, with optional ethtool enrichment.
- **ApplyReport**: Per-operation outcomes, errors, and explicit skip reasons.
- **DryRunReport**: Planned changes and nonmutating validation results.
- **BackendError**: Typed failure retaining enough context to identify the affected operation.

## Success Criteria

- **SC-001**: Ethernet/veth observations agree with independent kernel queries; unavailable optional attributes are omitted rather than invented.
- **SC-002**: Match filtering uses SPEC-001 semantics and correctly distinguishes missing named targets from empty broad matches.
- **SC-003**: Unsupported virtual devices retain their actual type and have base fields only, consistently with User Story 1 and FR-006.
- **SC-004**: MTU, administrative-state, and IPv4 address operations modify only the requested targets.
- **SC-005**: Partial failure preserves independent progress and reports the failed and blocked operations with context.
- **SC-006**: Removing one address does not implicitly disable or delete its interface.
- **SC-007**: Same-prefix address ordering is realized while unrelated groups remain intact; the backend does not invent reorder operations.
- **SC-008**: Dry run exposes the full plan and leaves the namespace unchanged.
- **SC-009**: Stale targets, incomplete address observations, unsupported operations, and optional ethtool failures have tests for their distinct outcomes.

## Assumptions

- Depends on SPEC-000 (workspace), SPEC-001 (state and selectors), SPEC-002 (schema), and SPEC-005 (shared plan contract).
- `crates/netfyr-backend` depends on `netfyr-state` for shared types. It does not contain policy merge logic.
- Integration tests use SPEC-008's disposable environments and explicit build target. Test setup and teardown use independent operating-system tools.






















