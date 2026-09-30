# Feature Specification: Reconciliation

Bind policy contributions to discovered devices, merge their fields by priority, and plan the changes needed to reach the effective desired state. SPEC-001 defines contributions and selectors; SPEC-003 produces those contributions. Several policies may configure one device. Reconciliation must retain their nonconflicting fields instead of choosing one whole policy and dropping the others.

The decision function takes explicit configuration, observed state, and merge options. It performs no I/O. The caller loads policies, queries the backend, invokes the planner, and passes the resulting operations to SPEC-004. This split also allows deterministic tests without a live kernel.

This specification covers static configuration and the merging of supplied contributions. Starting state factories, handling lease expiry, continuous drift handling, persisted ownership, checkpointing, and reverting a previously applied policy are separate deliverables. A provider declaration alone is not a produced contribution. Advanced selectors such as carrier or visible SSIDs require their own event and discovery contracts; they are not added here.

## User Scenarios & Testing

### User Story 1 - Bind Policies to Discovered Devices (Priority: P0)

An administrator selects interfaces through SPEC-001's `Match` predicate. Reconciliation applies that existing predicate to an explicit inventory; it does not redefine matching. Name selection is P0, with the other existing selector fields following SPEC-001's priorities.

**Independent Test**: Supply a fixed inventory and named contributions without invoking the backend.

**Acceptance Scenarios**:

1. **Given** a policy for eth0 and observed devices eth0 and eth1, **When** planning runs, **Then** only eth0 receives desired fields and no operation targets eth1.
2. **Given** a policy matching driver ixgbe, **When** eth0 uses ixgbe and eth1 uses another driver, **Then** only eth0 receives that contribution.
3. **Given** a policy selected by MAC and one selected by name that both identify eth0, **When** planning runs, **Then** they contribute to the same device.
4. **Given** a selector with no matching device, **When** planning runs, **Then** it produces no operation for that selector and reports the unmatched policy; it does not invent a device.

### User Story 2 - Merge Contributions Without Losing Fields (Priority: P0)

An administrator supplies a broad MTU policy and a more specific address policy. Both contribute. Priority decides a conflicting field; selector specificity and stable policy identity break equal-priority ties. Current observed values provide the baseline for fields no contribution mentions.

**Independent Test**: Merge several sources into one device and inspect effective fields and their provenance.

**Acceptance Scenarios**:

1. **Given** policy A contributes mtu=9000 and policy B contributes an address to eth0, **When** planning runs, **Then** both fields are retained.
2. **Given** A contributes mtu=9000 at priority 100 and B contributes mtu=1500 at priority 200, **When** planning runs, **Then** mtu=1500 wins regardless of selector specificity.
3. **Given** equal-priority conflicting MTUs selected by driver and by name, **When** the default resolution mode is used, **Then** the name-selected contribution wins that field and a structured conflict diagnostic identifies both policies, the field, and the winner.
4. **Given** equal-priority, equally specific policies named `aaa` and `zzz`, **When** their MTUs conflict, **Then** `aaa` wins regardless of input iteration order.
5. **Given** two supplied contributions contain overlapping IPv4 address lists, **When** merged, **Then** the addresses form an ordered union, duplicate CIDRs appear once, and the higher-precedence contribution supplies the complete winning address object, including its lifetimes.

### User Story 3 - Preview Conflicts Before Applying (Priority: P1)

An administrator sees the same resolution and diagnostics during planning and dry run that apply would use. `MergeOptions.conflict_policy` is a named choice: `resolve` is the default and `reject` refuses conflicting values before producing an executable plan. Distinct fields and identical values are not conflicts.

**Independent Test**: Plan conflicting input in both modes and verify that neither invocation performs I/O.

**Acceptance Scenarios**:

1. **Given** two policies setting different MTUs on an existing interface, **When** previewed in resolve mode, **Then** the chosen value and conflict are visible before apply.
2. **Given** the same input in reject mode, **When** planned, **Then** planning fails with diagnostics and no executable operations.
3. **Given** a rename or driver change makes two previously distinct selectors bind to one device, **When** replanned, **Then** the configured conflict policy still applies deterministically and the new binding is reported. The engine does not claim that a name-only selector survives a rename.

### User Story 4 - Plan Only Requested Changes (Priority: P0)

A developer compares effective desired fields with observed fields. A scalar change is an assignment. An omitted field is untouched. An explicit address list defines the managed address field after merging active contributions; it is not a request to remove the interface.

**Independent Test**: Compare fixed desired and observed inputs, including unrelated devices and omitted fields.

**Acceptance Scenarios**:

1. **Given** eth0 has addresses but no policy targets it, **When** planning runs, **Then** no operation targets eth0.
2. **Given** only mtu is desired and carrier differs, **When** planning runs, **Then** carrier produces no operation because it is read-only.
3. **Given** desired mtu=1500 and no enabled field, **When** the observed interface is enabled, **Then** enabled remains untouched.
4. **Given** the effective desired address list is empty, **When** planned against a nonempty observed list, **Then** explicit address removals are planned without changing link state.
5. **Given** desired same-prefix addresses are A,B and observed addresses are B,A, **When** planning runs, **Then** the affected address group has an explicit remove-and-add sequence in the plan and preview.
6. **Given** no requested field differs, **When** planning runs, **Then** the executable operation list is empty.

### User Story 5 - Load Administrative Overrides (Priority: P1)

An administrator overrides a vendor policy by placing the same policy name in a higher-precedence directory. Shadowing selects the policy definition before contributions are produced. It is distinct from merging different policy names on one device.

**Independent Test**: Load independently valid tiers and inspect the selected policies before merging.

**Acceptance Scenarios**:

1. **Given** policy `eth0` exists in /usr/lib and /etc, **When** loaded, **Then** only the /etc definition contributes.
2. **Given** differently named policies in /usr/lib and /etc target eth0, **When** loaded, **Then** both contribute under the merge rules.
3. **Given** duplicate policy names within one tier, **When** loaded, **Then** SPEC-003's duplicate-name error is returned before planning.

## Requirements

### Functional Requirements

- **FR-001**: The orchestration workflow MUST load each configured directory tier through SPEC-003, select definitions by policy name, produce contributions, obtain observed device state, bind contributions, merge effective desired fields, and compute a plan. The decision function MUST accept those inputs explicitly and MUST NOT load files, query the kernel, read a clock, or write output streams itself.
- **FR-002**: Binding MUST use SPEC-001's asymmetric `Match` predicate. Every matching contribution MUST be retained for that device. A selector can match multiple devices. An unmatched selector MUST NOT create a device.
- **FR-003**: Field precedence MUST first compare explicit contribution priority, higher first. Equal priorities MUST compare the most specific selector field (`name`, `mac`, `pci_path`, `driver`, `type`, in that order), then policy name in bytewise lexical order, then a stable contribution key. Static contributions use their unique policy name; a future provider must supply its registered location as part of its key. Duplicate keys MUST be rejected. Runtime UUIDs, timestamps, map iteration order, and filesystem discovery timing MUST NOT break ties. Source defaults come from SPEC-001; SPEC-003's static priority override is honored.
- **FR-004**: Maps MUST merge recursively. Scalar conflicts choose the first contribution under FR-003. Distinct leaves from lower-precedence contributions MUST remain. Lists MUST form an ordered union: visit contributions in precedence order, preserve each list's order, and keep the first occurrence of each element. IPv4 addresses use canonical host-address-plus-prefix `ip` as identity and retain the winner's entire address object. Other lists use structural value equality. An empty list contributes no elements; if every contribution to that field is empty, the effective list is empty. Clearing addresses contributed by a provider therefore also requires disabling or removing that provider's contribution.
- **FR-005**: Observed state MUST provide the baseline for fields absent from every desired contribution, regardless of their numeric priority. It MUST NOT be unioned into an explicitly configured list: an effective desired `ipv4.addresses` list owns that field, while an omitted list leaves existing addresses untouched. The plan MUST carry each changed leaf's old and new value and the source of its winning value; list elements MUST retain their winning source. This provenance is output metadata, not policy input.
- **FR-006**: Only explicitly configured fields on bound devices MAY produce operations. Removing a policy file or omitting a field MUST NOT implicitly deconfigure a device. This spec defines no lifecycle `absent` keyword, virtual-device creation/deletion, or restoration of a previous policy's baseline. Those actions need explicit lifecycle and ownership contracts. Unmanaged devices MUST remain untouched.
- **FR-007**: Writability MUST come from SPEC-002's schema registry. Read-only fields, including fields with no writable marker, MUST generate no operations. Invalid desired fields MUST be rejected before an executable plan is returned.
- **FR-008**: A `StateDiff` MUST describe changes on existing devices as field assignments plus ordered execution operations. The initial operations are setting MTU, setting administrative state, and adding, removing, or replacing a specific IPv4 address. Address removal is not entity removal. Shared, format-independent plan types belong in `netfyr-state`; computation belongs in `netfyr-reconcile`. Add/Remove of whole entities is reserved for a later lifecycle spec and MUST NOT be emitted here.
- **FR-009**: The planner MUST decide address ordering; the backend only executes its sequence. Ordinary membership and lifetime changes MUST leave unaffected address groups in place. A reorder, or removal of a primary address that could also remove desired secondaries, MUST explicitly remove and rebuild the affected same-prefix group in desired order, including every still-desired member. The preview MUST expose this transient disruption. Other prefix groups and omitted address fields MUST NOT be rebuilt. Removing and re-adding a whole interface's addresses as an implicit backend shortcut is forbidden.

  Address order controls insertion and IPv4 primary/secondary relationships within a prefix group. It does not override route selection, preferred source, or scope. For idempotence, address-order comparison MUST compare membership and attributes plus relative order within each prefix group; differences caused only by kernel ordering between independent groups MUST NOT produce a repeated reorder. Other ordered lists retain exact order comparison. A destructive address plan requires a complete observation of the affected group; incomplete observations MUST fail planning rather than guess what to remove.
- **FR-010**: The same plan MUST support deterministic text and JSON output. Text MUST group changes by device, use one line per changed field, and include any ordered address rebuild beneath that field. JSON MUST contain `schema_version: 1`, `changes`, `operations`, and `diagnostics`; changes identify device, field path, old value, new value, and winning source. Operations identify the device, kind, arguments, and dependency on earlier operations. Stable ordering MUST make unchanged inputs produce unchanged output. CLI diff commands MUST select this representation with `--json`. The backend consumes the Rust plan, not the rendered JSON.
- **FR-011**: Each tier MUST be loaded atomically under SPEC-003's duplicate and validation rules. The default ordered search path MUST be a named loader setting: `/run/netfyr/policies`, `/etc/netfyr/policies`, `/usr/lib/netfyr/policies`, highest precedence first. Callers MAY supply other ordered roots. Same-name shadowing MUST select the whole higher-tier definition. Distinct policy names MUST coexist, regardless of tier. This read path writes neither /etc nor /var/lib. Future adopt behavior must specify persistence explicitly; /usr/lib is vendor configuration, not mutable runtime state.
- **FR-012**: `MergeOptions.conflict_policy` MUST accept `resolve` and `reject`, defaulting to `resolve`. Conflicting leaf values and duplicate-address attributes MUST return structured diagnostics with the device, field or address identity, competing sources, and selected source. Resolve mode returns the plan; reject mode returns all detected conflicts and no executable plan. The caller MUST present administrator-facing conflicts through its diagnostic/logging interface under philosophy P11. The library MUST NOT write stderr. Invalid input remains an error in either mode.
- **FR-013**: Plans MUST bind targets to the queried namespace and interface identity, not just a reusable interface name. The executor MUST revalidate that identity and the observations needed for destructive operations. A stale target or changed address group MUST fail that operation and require a fresh plan; it MUST NOT silently configure a replacement device. SPEC-004 defines reporting and dependent-operation handling.

### Key Entities

- **Contribution**: One source's fields and priority, as defined by SPEC-001, plus stable origin information supplied by its caller.
- **Effective desired state**: The merged fields for one observed device, with per-field and per-element provenance.
- **StateDiff**: Field changes and an ordered, explicit operation plan for existing devices.
- **MergeOptions**: Caller-selected conflict behavior.
- **Conflict diagnostic**: Structured competing values, sources, target, and resolution.

## Success Criteria

- **SC-001**: Name- and MAC-selected contributions resolving to one device merge together; unrelated devices receive no operations.
- **SC-002**: Same-name tier overrides select one definition, while differently named policies coexist.
- **SC-003**: Priority precedes specificity; equal-priority ties and diagnostics are stable under input permutation.
- **SC-004**: Unmanaged devices, omitted fields, and read-only fields generate no operations.
- **SC-005**: Disjoint fields survive merging; duplicate addresses retain winning attributes and provenance.
- **SC-006**: A fully satisfied plan is empty, including after kernel normalization between address groups.
- **SC-007**: Same-prefix order changes and primary removal expose their complete affected-group operation sequence; unrelated groups are preserved.
- **SC-008**: Reject mode returns conflicts before any operation can execute; resolve mode reports the same resolution during preview and apply.
- **SC-009**: Text and JSON describe the same plan and are deterministic for fixed input.
- **SC-010**: Pure decision tests cover success, invalid input, ties, empty lists, unknown observations, and ownership boundaries under SPEC-008. Kernel behavior is verified by SPEC-004 integration tests.

## Assumptions

- Depends on SPEC-000 (workspace), SPEC-001 (state representation), SPEC-002 (schema and validation), and SPEC-003 (policy production).
- `crates/netfyr-reconcile` depends on `netfyr-state`; the caller supplies the inventory. Reconciliation does not depend on the concrete netlink backend.
- A high-level apply path must supply the checkpoint guarantees required by philosophy P6 before it is presented as safe remote configuration. This pure planner neither arms nor bypasses those checkpoints.
- Continuous state factories and drift handling remain future work under philosophy P5 and P8. This initial one-shot scope does not prohibit them.










































