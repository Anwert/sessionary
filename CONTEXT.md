# Sessionary

A keyboard-first terminal environment for working with concurrent coding-agent sessions across different harnesses.

## Language

**Session**:
One invocation of a harness in a terminal, including the conversation, work it performs, and any subordinate agents it starts.
_Avoid_: Run

**Harness**:
The coding-agent environment through which a session is started and operated, such as Claude Code or Codex.
_Avoid_: Provider, agent

**Turn**:
A span of Harness work initiated by a user instruction and ending when the Harness completes or fails its response. A Turn may pause while the Harness needs a decision, approval, or further instruction from the user.

**Harness conversation**:
An independently resumable conversation that a Harness adapter exposes to Sessionary. A Session may be linked to multiple Harness conversations over its lifetime.

**Harness conversation ID**:
A stable, opaque identifier assigned by a Harness adapter to a Harness conversation. It is meaningful only together with the Harness adapter identity.

**Conversation binding**:
The association of one Harness conversation with one Session. A Session may have many conversation bindings, while a Harness conversation may be bound to at most one Session.

**Group**:
A user-defined collection of related Sessions, independent of repository or directory boundaries. A Session may belong to at most one Group or remain ungrouped.
_Avoid_: Mission, workspace, context

**Board**:
The ordered overview through which Sessions are scanned, selected, created, and reorganized.
_Avoid_: Layout, workspace

**Lane**:
The Board representation of either a Group or a system-defined collection of Sessions. Lanes provide uniform ordering and navigation without implying Group membership.

**Ungrouped**:
The absence of Group membership for a Session, presented on the Board through the system-defined Lane pinned at the top.
_Avoid_: Standalone

**Session name**:
An automatically suggested, user-editable label by which a session is identified in the interface.

**Session state**:
The single, mutually exclusive state of a Session: `Working`, `Idle`, `Needs input`, `Missing`, or `Finished`. `Needs input` includes a Harness waiting for the user or not reliably classifiable as `Working` or `Idle`; `Missing` means an expected live runtime disappeared; `Active` collectively describes `Working`, `Idle`, and `Needs input` rather than being another state.

**Group state**:
The single, mutually exclusive state of a Group: `Active` or `Finished`. A Group may be `Finished` only after all of its Sessions are `Finished`; its Sessions remain individually resumable.
