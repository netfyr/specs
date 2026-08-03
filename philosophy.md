# netfyr design philosophy

Constraints every spec in this repo inherits. A spec that contradicts one of
these has to say so and argue the case; silence means the principle holds.
Cite them by ID (P4, P7) in specs and reviews. IDs are stable: retired
principles keep their number rather than freeing it for reuse.

netfyr replaces nmstate and NetworkManager with a single engine that owns both
the imperative netlink layer and the declarative reconciler. Primary target is
enterprise host networking: servers and baremetal Kubernetes nodes (NICs, bonds,
bridges, VLANs, SR-IOV). Laptop and desktop use is a secondary client of the
same engine, not a second engine.

## P1: One engine, not a layer on a daemon

The split between a declarative layer and the daemon beneath it is the problem,
not the architecture. netfyr owns rtnetlink, observed state, and reconciliation
in one process boundary, so plan and apply see the same truth.

## P2: Small core

Core carries only what is cross-cutting: netlink transport and event socket,
observed-state reader, state model, diff/plan, dependency graph and ordering,
reconciler, checkpoint orchestration, plugin host, secret contract. Ordering
rules span types (bridge before ports, bond before ports, IP before route), so
they cannot live in a per-type plugin. Everything technology-specific or
backend-specific is a plugin.

## P3: Declaration before execution

A plugin declares itself in a static manifest that is read without running it:
identity, versions, config schema, resource types it owns, required
capabilities, metrics. The declared surface is the enforced surface. Plugins
depend on capabilities, not on named plugins, and the same declaration drives
both package dependencies and runtime resolution.

## P4: The API is the product

The neutral boundary is the in-process Rust API. Every wire protocol is an
adapter projecting that API onto a socket, so core stays uncoupled from any IPC
type system. One serialized apply path, authorization enforced at the core
boundary, adapters only authenticate. The CLI holds no privilege another client
cannot have.

The idiom is method-oriented request/reply plus one typed event stream, chosen
as the lowest common denominator a richer transport can be synthesized from. A
bespoke client protocol would just be a worse Varlink. Machine and agent clients
should be able to discover the surface from the API itself rather than from
out-of-band documentation.

## P5: Daemonless by default

A running process is a per-feature cost, not a baseline. Features that produce
state from ongoing events (DHCP, SLAAC/RA, ACD, IPv4 link-local, VPN, Wi-Fi, SLB
bonding, connectivity check, drift monitoring) are state factories that feed
generated state into the engine, which merges it with static configuration into
one desired state. Those factories need a daemon and are unavailable in one-shot
mode; nothing else is.

## P6: Never strand the host

Applying network configuration can remove the path used to fix it. Checkpoint
and rollback are host-local, armed before the change, and must survive the loss
of connectivity they exist to undo.

## P7: The host is the boundary

netfyr is a host-local agent. No consensus, no leader election, no clustered
control plane. Fleet orchestration and cross-host coordination live above it.

## P8: Ownership is explicit, drift is a policy

Out-of-band changes are detected via netlink events, not assumed away. What
happens next is configuration: revert (re-apply the declared state), audit (log
only), or adopt (take the change as the new desired state).

## P9: Migration by translation, not emulation

Compatibility surfaces translate schemas rather than reimplement APIs. v1 is an
nmstate-shaped surface so kubernetes-nmstate, RHEL system roles, and KubeVirt
retarget with minimal change. v2 is a scoped NM D-Bus shim covering what desktop
consumers actually use, not the full API.

## P10: Secrets stay out of core

Core consumes pre-provisioned key material through the credential contract and
never persists it. Redaction is absolute: no secret is emitted at any log
verbosity. Interactive prompting belongs to a desktop client plugin.

## P11: Logs have two audiences

Info, warn and error are for administrators and describe what happened to the
system. Trace and debug are for developers and must be enough to reconstruct a
run deterministically, including graph evaluation and state merging. Emit
structured fields where the backend supports them so messages correlate with
system state without regex parsing.

## Not in scope

Pod and CNI networking. Firewall policy management; netfyr touches nftables only
in its own tables, for features that require it. An HTTP/REST surface. A hard
systemd dependency; systemd is the default platform backend, not a requirement.
Non-Linux platforms.
