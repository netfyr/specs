# netfyr philosophy

Constraints every spec in this repo inherits. A spec that contradicts one of
these has to say so and argue the case; silence means the principle holds.
Cite them by ID (P4, P7) in specs and reviews. IDs are stable: retired
principles keep their number rather than freeing it for reuse.

netfyr replaces the host's network engine: the component that owns rtnetlink
and turns configuration into interface state. NetworkManager and nmstate are
the primary migration targets because that is where the users netfyr is built
for are today. netplan and systemd-networkd hold the same role for other users
and are the same kind of target; P9 decides which of them get a compatibility
surface and how far it goes. netfyr does not sit behind iproute2. iproute2 is a
thin wrapper over the same uapi netfyr owns, it has to keep working in an
initrd with no services running, and the changes it makes reach netfyr as
netlink events already (P8).

Primary target is enterprise host networking: servers and baremetal Kubernetes
nodes (NICs, bonds, bridges, VLANs, SR-IOV). Laptop and desktop use is a
secondary client of the same engine, not a second engine.

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

Checkpoint orchestration is in that list because P6 requires a checkpoint to
survive the loss of connectivity it exists to undo. A remote client must not be responsible for firing the rollback after losing
its connection. A separate host-local watchdog could satisfy P6 too; this
architecture puts orchestration on the apply path so every adapter gets the
same guarantee. A plugin can supply the content of a checkpoint for a
resource type it owns; arming, the rollback timer, and firing it are on the
apply path and stay with the process that owns the netlink socket.

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
state from ongoing events (DHCP, SLAAC/RA, ACD, IPv4 link-local addressing,
VPN, Wi-Fi, SLB bonding, connectivity check, drift monitoring) are state
factories that feed generated state into the engine, which merges it with
static configuration into one desired state. Those factories need a daemon and
are unavailable in one-shot mode; nothing else is.

IPv4 link-local (RFC 3927) is on that list because Linux has no in-kernel
implementation of it: claiming a 169.254/16 address means ARP probing from
userspace. IPv6 link-local addresses are kernel-generated and are not on the
list. The kernel can also process router advertisements on its own, and the RA
factory exists anyway because whether to accept one is a policy decision (P13)
and the addresses and routes that result have to enter the same desired state
as everything else.

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

Ownership is per resource, not per host. netfyr does not require exclusive
control of a machine's networking. An interface nothing declares is not
netfyr's: it is not modified, not torn down at startup, and not taken over by
adoption. Sharing a host with another network tool is a supported
configuration, and this boundary is what makes it one.

## P9: Migration by translation, not emulation

Compatibility surfaces translate schemas rather than reimplement APIs. v1 is an
nmstate-shaped surface so kubernetes-nmstate, RHEL system roles, and KubeVirt
retarget with minimal change. v2 is a scoped NM D-Bus shim covering what desktop
consumers actually use, not the full API.

NetworkManager moving onto netfyr instead of being shimmed is a possible
outcome and a better one than a shim. It is not a netfyr deliverable: netfyr
does not decide NetworkManager's architecture, and planning around a decision
that belongs to another project's maintainers is not a plan. The scope of the
shim is the same either way, because either path has to answer which parts of
the D-Bus API desktop consumers actually call.

## P10: Secrets stay out of core

Core consumes pre-provisioned key material through the credential contract and
never persists it. Observed state carries secret references, never material, so
drift detection, adopt, and the SPEC-007 journal have no material to redact.
Adopt takes the reference. An out-of-band change that introduces key material
netfyr cannot name by reference fails adoption for that resource rather than
persisting the material.

Redaction is absolute: no secret is emitted at any log verbosity. A wrong
secret is still diagnosable, because what identifies it is the reference plus a
keyed fingerprint computed by the credential provider with a randomly generated
per-boot secret key. The key is never logged or persisted, and the fingerprint
is available only to authorized diagnostics. This permits comparisons within
one boot without giving a reader of logs an offline guessing oracle. A public
salt alone is insufficient for a low-entropy secret. Interactive prompting
belongs to a desktop client plugin.

## P11: Logs have two audiences

Info, warn and error are for administrators and describe what happened to the
system. Trace and debug are for developers and must be enough to reconstruct a
run deterministically, including graph evaluation and state merging. Emit
structured fields where the backend supports them so messages correlate with
system state without regex parsing.

## P12: The API evolves additively

A surface a client discovered yesterday keeps working. Change is additive: new
fields, new methods, new event types. Removal is a versioned break with an
announced date, not a release note.

The rule runs one way. Unknown fields in what netfyr produces (a reply, an
event, a plugin manifest) are ignored by the reader, so a new core works with
an old client. An old core may ignore descriptive extensions in a newer
plugin manifest, but must reject a plugin whose required capabilities or
mandatory semantics it cannot honor; it must not silently weaken the declared
surface (P3). Unknown fields
in what a client sends are rejected, because a silently ignored key in a
desired state is a configuration that did not happen and said nothing.

Clients negotiate capabilities, not version numbers. A version number tells a
client what to assume; a capability tells it what is there, which is the same
discovery surface P4 requires for agents. Plugin manifests (P3) and the state
schema evolve under this rule too.

## P13: Mechanism in core, policy in configuration

netfyr is opinionated about its architecture and not about anyone's network.
Where a decision belongs to whoever runs the host (drift response, whether to
accept router advertisements, checkpoint timeout, which state factories run,
MAC policy on a bond), netfyr implements the supported choices and exposes the selection as
configuration.

Defaults exist, because a host has to work before anyone configures it. Every
default is a named setting rather than a constant, and is documented as a
choice. A default that cannot be changed is a policy decision netfyr made on
someone's behalf without telling them.

## Not in scope

Pod and CNI networking. Firewall policy management; netfyr touches nftables only
in its own tables, for features that require it. An HTTP/REST surface. A hard
systemd dependency; systemd is the default platform backend, not a requirement.
Non-Linux platforms.














