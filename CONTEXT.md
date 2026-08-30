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

**Group**:
A user-defined collection of related sessions, independent of repository or directory boundaries. A session may belong to at most one group or remain ungrouped.
_Avoid_: Mission, workspace, context

**Board**:
The ordered overview of Lanes through which Sessions are scanned, selected, created, and reorganized.
_Avoid_: Layout, workspace

**Lane**:
A Board representation of either a Group or a system-defined collection of Sessions. A Lane participates uniformly in Board ordering and navigation without implying Group membership.
_Avoid_: Group block

**Ungrouped**:
The absence of Group membership for a Session, presented on the board through a system-defined Lane.

**Session name**:
An automatically suggested, user-editable label by which a session is identified in the interface.

## Session states

**Working**:
The Session state in which its Harness is performing a turn.

**Needs input**:
The Session state in which its Harness is waiting for a decision, approval, or instruction from the user.
_Avoid_: Waiting

**Idle**:
The Session state in which its Harness is live but is neither performing a turn nor requiring the user's attention.

**Finished**:
The Session state in which its work is explicitly complete and its live Harness has stopped, while its identity is retained for later resumption.

**Active session**:
A collective term for a Working, Needs input, or Idle Session. Active is not a separate Session state.

## Group states

**Active**:
The Group state in which it is available for ongoing work.

**Finished**:
The Group state in which it has been explicitly completed after all of its Sessions are Finished. Its Sessions remain individually resumable.
