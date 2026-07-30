# Feature Specification: Schema Validation

Implement JSON Schema-based validation for network entity state, including field definitions, writability tracking, and entity type inference. Without schema validation, typos in field names (e.g., `mtt` instead of `mtu`) or attempts to set read-only hardware properties would only surface as confusing backend errors or silent no-ops. Validating early -- before any system changes -- gives clear, actionable error messages. The schema also serves as the authoritative definition of the data model for each entity type.

## User Scenarios & Testing

### User Story 1 - Validate State Against Schema (Priority: P0)

A user writes a YAML policy and the system validates it against the schema before applying any changes. Unknown fields (typos like `mtt` instead of `mtu`) and out-of-range values (e.g., MTU of 99999) are rejected with clear error messages. All validation errors are collected and reported together, not just the first one.

**Why this priority**: Early validation prevents confusing backend errors and silent no-ops. This is the first line of defense against user mistakes.

**Independent Test**: Create State values with unknown fields and out-of-range values, run validation, and verify that specific error types are returned.

**Acceptance Scenarios**:

1. **Given** a State with field "mtt"=1500, **When** `validate_writable()` is called, **Then** an UnknownField error is returned (field not in schema).
2. **Given** a State with mtu=99999, **When** `validate()` is called, **Then** an OutOfRange error is returned (max 65535).
3. **Given** a State with field "mtt"=1500 and "foobar"="baz", **When** `validate_writable()` is called, **Then** errors for both "mtt" and "foobar" are returned.

### User Story 2 - Enforce Read-Only Field Constraints (Priority: P0)

A user queries the system and sees fields like `mac`, `carrier`, and `driver` in the output. These are read-only kernel properties that appear in query results but cannot be set in policies. The schema distinguishes writable fields from read-only ones: `validate()` accepts read-only fields (for query results), while `validate_writable()` rejects them (for policy input).

**Why this priority**: Without the writable/read-only distinction, users might try to set hardware properties in a policy and get confusing errors from the backend.

**Independent Test**: Create a State with a read-only field (e.g., `mac`), verify that `validate()` passes but `validate_writable()` returns a ReadOnlyField error.

**Acceptance Scenarios**:

1. **Given** a State with field "mac"="aa:bb:cc:dd:ee:ff", **When** `validate()` is called, **Then** it passes; **When** `validate_writable()` is called, **Then** a ReadOnlyField error is returned.

### User Story 3 - Validate by Fragment (Priority: P1)

A user writes a policy that sets IPv4 addresses on an interface without specifying the device type. The schema validates only the fragments whose top-level keys are present in the state: `base.json` always applies, `ipv4.json` applies when `ipv4` is present, `ethernet.json` applies when `ethernet` is present. This means a policy can set IPv4 addresses on any interface without knowing its type.

**Why this priority**: Fragment-based validation enables flexible policies that work across device types.

**Independent Test**: Create a State with an `ipv4` sub-object but no `ethernet` sub-object, run `validate_writable()`, and verify that only base and ipv4 fragments are validated.

**Acceptance Scenarios**:

1. **Given** a State with an "ipv4" sub-object but no "ethernet" sub-object, **When** `validate_writable()` is called, **Then** the base and ipv4 fragments are validated but the ethernet fragment is not applied.

### Edge Cases

- What happens when multiple schema fragments conflict (e.g., `ethernet` + `bond` on the same interface)? Fragment compatibility validation will be defined by a later spec when the first conflicting fragments are introduced. For now, each present fragment is validated independently.
- How does the system prevent schema/backend drift? Pinned field-set tests ensure each fragment's field set and writable/read-only partitioning match hardcoded lists (see SC-005).

## Requirements

### Functional Requirements

- **FR-001**: Schemas MUST be JSON Schema files embedded as source JSON at compile time, so the binary is self-contained with no external file dependencies.
- **FR-002**: Schemas MUST use the custom extension property `x-netfyr-writable` (bool, default false) to indicate whether a field can be set in policies.
- **FR-003**: `SchemaRegistry` MUST provide:
  - `validate(state)` -- applies matching fragments, accepts read-only fields (for query results).
  - `validate_writable(state)` -- applies matching fragments, rejects read-only fields (for policy input).
  - `field_info(fragment, field)` -- returns metadata including `writable`.
  - All validation errors MUST be collected, not just the first.
- **FR-004**: Schemas MUST be organized as independent fragments. Validation applies each fragment whose top-level key is present in the state:
  - `base.json` always applies.
  - `ipv4.json` applies when `ipv4` is present.
  - `ethernet.json` applies when `ethernet` is present.
- **FR-005**: `base.json` schema fragment -- always validated, common to all network devices:

  | Field | Type | Writable | Notes |
  |-------|------|----------|-------|
  | `type` | string | read-only | Technology type (e.g., "ethernet") |
  | `name` | string | read-only | Interface name |
  | `mac` | string | read-only | Hardware MAC |
  | `carrier` | boolean | read-only | Link has carrier |
  | `driver` | string | read-only | Kernel driver |
  | `enabled` | boolean | yes | Admin up/down |
  | `mtu` | integer | yes | Min 68, max 65535 |

- **FR-006**: `ipv4.json` schema fragment -- validated when `ipv4` sub-object is present:

  | Field | Type | Writable | Notes |
  |-------|------|----------|-------|
  | `ipv4.addresses` | array of objects | yes | Each entry: `ip` (CIDR string, required), `valid_lft` (seconds), `preferred_lft` (seconds) |

- **FR-007**: `ethernet.json` schema fragment -- validated when `ethernet` sub-object is present:

  | Field | Type | Writable | Notes |
  |-------|------|----------|-------|
  | `ethernet.speed` | integer | read-only | Link speed in Mbps |
  | `ethernet.duplex` | string | read-only | "full", "half", or "unknown" |
  | `ethernet.autoneg` | boolean | read-only | Auto-negotiation enabled |

- **FR-008**: The schema MUST be the single source of truth for the data model. Every field defined in a schema fragment must be handled by the backend -- a schema change that adds or removes a field without a corresponding backend update must be detected and prevented.

### Key Entities

- **SchemaRegistry**: Validates State values against embedded JSON Schema fragments. Supports both read-only-permissive and writable-only validation modes.
- **Schema Fragment**: An independent JSON Schema file (e.g., `base.json`, `ipv4.json`, `ethernet.json`) that validates a subset of state fields. Applied when its top-level key is present in the state.

## Success Criteria

- **SC-001**: Unknown fields are rejected by `validate_writable()` with an UnknownField error.
- **SC-002**: Read-only fields pass `validate()` but fail `validate_writable()` with a ReadOnlyField error.
- **SC-003**: Out-of-range values (e.g., mtu > 65535) are rejected with an OutOfRange error.
- **SC-004**: Fragment-based validation only applies fragments whose top-level keys are present in the state.
- **SC-005**: Pinned field-set tests verify that each fragment's field set and writable/read-only partitioning match hardcoded expected lists, preventing drift.
- **SC-006**: All validation errors are collected and returned together.

## Assumptions

- Depends on SPEC-000 (project setup) and SPEC-001 (State, StateSet, Value types).
- The schema validation module is added to `netfyr-state` (not a separate crate), because schemas define the structure of `State` values.
- IPv4 is defined here. IPv6 support will be added by a later spec.
- Fragment compatibility validation (e.g., rejecting `ethernet` + `bond` together) will be defined by a later spec when the first conflicting fragments are introduced.
