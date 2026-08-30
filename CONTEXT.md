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
A stable, opaque identifier assigned by a Harness adapter to a Harness conversation. Its representation and mapping to Harness-native identifiers are adapter implementation details; Sessionary interprets it only together with the Harness adapter identity.

**Conversation binding**:
The association of one Harness conversation with one Session. A Session may have many conversation bindings, while a Harness conversation may be bound to at most one Session.

**Group**:
A user-defined collection of related sessions, independent of repository or directory boundaries. A session may belong to at most one group or remain ungrouped.
_Avoid_: Mission, workspace, context

**Session name**:
An automatically suggested, user-editable label by which a session is identified in the interface.

**Finished session**:
An active-list session whose current work has been explicitly marked complete but may be resumed later.

**Archived session**:
A session removed from normal active views because the user no longer expects to return to it.

**Session activity**:
The operational state of a live session: `Working`, `Idle`, or `Needs input`. There is no separate unknown state; when a harness cannot be classified reliably, the session is `Needs input`.

**Needs input**:
An operational state indicating that the harness is waiting for a decision, approval, or instruction, or that Sessionary cannot reliably classify it as `Working` or `Idle`.

**Session lifecycle**:
Whether a session is active or finished. `Active` collectively describes `Working`, `Idle`, and `Needs input`; `Finished` means the live Harness has been stopped. Finish is allowed from `Idle` or `Needs input`, never from `Working`; Resume returns a Finished Session to `Idle` after the Harness starts successfully. Delete is an operation, not a lifecycle state.
