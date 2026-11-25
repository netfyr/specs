# Contributing specifications

This repository holds netfyr's core specifications. Sign in with GitHub to
propose a feature or revise an existing note on the
[core SpecDoc board](https://specs.netfyr.io/?ns=netfyr%2Fspecs).
SpecDoc can publish notes owned by a listed author or approver. If you need
access, give a maintainer your GitHub login in a
[repository issue](https://github.com/netfyr/specs/issues). The current
roster and approval quorum are in [roles.yml](roles.yml).

If you open a PR here as an outside contributor, SpecDoc directs you back to
the board. Review spec text in the editor. Once the current text has enough
approvals, all discussion threads are resolved and suggestions are settled,
SpecDoc opens the publication PR. It merges the approved revision after the required
`validate` check passes. Use the merged file as the implementation baseline.
For a correction to a published spec, ask its owner to reopen the note and
submit the revision through the same review. See the
[spec lifecycle](https://specdoc.josie.cloud/spec-lifecycle/).

Send implementation PRs to the core repository using its
[contribution guide](https://github.com/netfyr/netfyr/blob/main/CONTRIBUTING.md).
For terminal or Cockpit features, use the [TUI board](https://specs.netfyr.io/?ns=netfyr%2Ftui)
or [Cockpit board](https://specs.netfyr.io/?ns=netfyr%2Fcockpit). Each publishes
to its own repository. The [development guide](https://netfyr.io/development/)
covers the workflow across projects.
