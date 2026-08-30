# Sessionary

A keyboard-first terminal environment for working with concurrent coding-agent sessions across different harnesses.

## Language

**Session**:
One invocation of a harness in a terminal, including the conversation, work it performs, and any subordinate agents it starts.
_Avoid_: Run

**Harness**:
The coding-agent environment through which a session is started and operated, such as Claude Code or Codex.
_Avoid_: Provider, agent

**Harness conversation**:
An independently resumable conversation that a Harness adapter exposes to Sessionary. A Session may be linked to multiple Harness conversations over its lifetime.

**Harness conversation ID**:
A stable, opaque identifier assigned by a Harness adapter to a Harness conversation. It is meaningful only together with the Harness adapter identity.

**Conversation binding**:
The association of one Harness conversation with one Session. A Session may have many conversation bindings, while a Harness conversation may be bound to at most one Session.

**Group**:
A user-defined collection of related Sessions, independent of repository or directory boundaries. A Session may belong to at most one Group or remain ungrouped.
_Avoid_: Mission, workspace, context

**Session name**:
An automatically suggested, user-editable label by which a session is identified in the interface.

**Session runtime**:
The live terminal execution environment in which a Session's Harness process runs.

**Lifecycle status**:
The durable status of a Session: `Active` or `Finished`. An `Active` Session is not intentionally finished and may have a live or missing runtime. A `Finished` Session was intentionally finished.

**Runtime status**:
Whether an `Active` Session's runtime is currently `Present` or `Missing`.

**Harness status**:
The current normalized Harness activity for a present runtime: `Working`, `Idle`, or `Needs input`. `Needs input` includes a Harness waiting for the user or not reliably classifiable as `Working` or `Idle`.

**UI status**:
The current status presented for a Session: `Loading`, `Working`, `Idle`, `Needs input`, `Missing`, or `Finished`. `Loading` means the status inputs required to derive another UI status are not yet available. A `Finished` lifecycle produces `Finished`; an `Active` lifecycle with a `Missing` runtime produces `Missing`; an `Active` lifecycle with a `Present` runtime uses its Harness status.
