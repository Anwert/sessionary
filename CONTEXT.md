# Sessionary

A keyboard-first terminal environment for working with concurrent coding-agent sessions across different harnesses.

## Language

**Session**:
One invocation of a harness in a terminal, including the conversation, work it performs, and any subordinate agents it starts.
_Avoid_: Run

**Harness**:
The coding-agent environment through which a session is started and operated, such as Claude Code or Codex.
_Avoid_: Provider, agent

**Group**:
A user-defined collection of related sessions, independent of repository or directory boundaries. A session may belong to at most one group or remain ungrouped.
_Avoid_: Mission, workspace, context

**Section**:
A named subdivision within a group that organizes the sessions displayed there. Initially, sections are formed automatically from session state; user-defined rules and nested sections are not yet specified.
_Avoid_: Subgroup

**Session name**:
An automatically suggested, user-editable label by which a session is identified in the interface.

**Finished session**:
An active-list session whose current work has been explicitly marked complete but may be resumed later.

**Archived session**:
A session removed from normal active views because the user no longer expects to return to it.

**Session state**:
The session's current lifecycle or attention state: working, needs input, finished, or archived.
