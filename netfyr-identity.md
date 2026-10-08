# netfyr identity

How the project presents itself, wherever it speaks: README, docs, release notes, commit messages, issue replies, social accounts, conference talks. A spec, a page, or a post that contradicts one of these has to say so and argue the case; silence means the principle holds. Cite them by ID (I2, I5) in reviews. IDs are stable: retired principles keep their number rather than freeing it for reuse.

netfyr replaces software that people depend on and that other people maintain. Most of what follows exists so that saying the first part never requires insulting the second.

## I1: The name is netfyr, lowercase

Always lowercase, including at the start of a sentence, in headings, and in titles. Same convention as nmstate and systemd. `Netfyr` and `NetFyr` are misspellings, not stylistic choices, and a docs check may reject them.

The binary, the crate, the Copr project, and the repositories carry the same name. Where a component needs its own name it is `netfyr-<thing>`.

## I2: Describe what it replaces, never rank it

nmstate and NetworkManager are the software netfyr is built to succeed, and both are the work of people who are still shipping it. Explain design differences and the tradeoffs behind them. Do not describe the alternatives as slow, broken, legacy, bloated, or dated, and do not imply their maintainers were wrong to build what they built.

The design argument stands on its own: P1 says the split between a declarative layer and a daemon is the problem. That is a claim about architecture. Making it about the code's quality trades a defensible position for a cheap one.

## I3: State affiliation, never imply it

netfyr is an independent project. It is not a Red Hat product, is not endorsed by Red Hat, and is not a NetworkManager or nmstate successor blessed by their maintainers. Any public surface that could be mistaken for a vendor project says so plainly.

The authors maintain NetworkManager and are employed by Red Hat. Disclose that where it is relevant, in a talk or a comparison post, and never lean on it as authority for netfyr's claims.

## I4: One voice everywhere

Terse and technical, in a release note as much as in a README. State what something does, what it costs, and what it does not do. No superlatives, no launch language, no roadmap framed as achievement. A reader should not be able to tell whether a sentence came from the documentation or from a commit message.

## I5: Vocabulary is fixed

One word per concept, matching the philosophy document and the schema: state, desired state, observed state, plan, apply, reconcile, backend, plugin, state factory, checkpoint, drift. Do not reach for synonyms to avoid repeating a noun; repeating the noun is how a reader knows it is the same thing.

Renaming a concept is a change to that vocabulary, so it is a change to this document and to every spec that used the old word.

## I6: Every claim is falsifiable, and about the present

Public statements describe what the code does today. "No daemon on the query and apply paths" is a claim someone can check, and it stops being sayable the day it stops being true. Mark anything not yet built as planned, in the same sentence.

Numbers carry their method: version, hardware, workload, and how to reproduce. A benchmark without them is marketing, and against a project netfyr competes with it is worse than that.

## I7: Marks are licensed separately from the code

The logo, the wordmark, and the name are not covered by the code's MIT license. Assets live in the repository under an explicit, separate license so a fork knows what it may keep. A fork may take the code; it does not inherit the name.

## I8: The channels list is the channels list

The README names every account, repository, and site that speaks for netfyr. Anything not on that list is not the project, including accounts using the name. Adding a channel means editing that list first.

## Not in scope

Documentation prose conventions and code comment rules; those belong to the implementation repository's `CONTRIBUTING.md`. A visual design system: colors, type, and layout are a design problem, and fixing them here before a designer exists would be inventing constraints nobody can satisfy. Community conduct and moderation, which are governance. Translation and localization policy, until there is a second language.
