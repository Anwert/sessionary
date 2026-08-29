---
title: Find the keyboard-first multi-harness session manager UX
status: open
labels:
  - wayfinder:map
assignee:
blocked_by: []
---

## Destination

A tested UX concept for a keyboard-only terminal session manager: one navigation shell selected from six cheap alternatives, then refined into an interactive fake-data workflow prototype ready to inform MVP planning.

## Notes

- This effort plans and validates UX; it does not build the production manager or choose its final stack.
- The manager is a personal, keyboard-only shell over native, independently updating harnesses, initially Claude Code and Codex.
- Closing the UI must not terminate live sessions.
- A session is one harness invocation, including its subordinate agents; it has an editable name and may belong to at most one optional Group.
- Groups may span repositories. Repository, branch, and worktree are session metadata rather than the primary hierarchy.
- Sections subdivide Groups. Initially they are generated from Session state; manual rules and nesting remain undecided.
- Session states are Working, Needs input, Finished, and Archived. Finished is explicit and reversible; Archived leaves normal active views.
- Context usage must be visible both in overview and while focused inside a native harness.
- Use `prototype` for concrete UX comparisons and `grilling` plus `domain-modeling` for human decisions.

## Decisions so far

## Not yet specified

- Exact presentation of context usage, account limits, session metadata, and cross-session attention signals inside the selected shell.
- Creation, naming, grouping, finishing, archiving, and restoration flows in the selected shell.
- A frequency-ranked transition map and final keyboard bindings.
- Whether Sections can be manual, rule-based, multiply assigned, or recursively nested.
- Whether a Session may eventually belong to multiple Groups or acquire orthogonal tags.
- Search, “next session needing input,” and other navigation accelerators beyond the keyboard-first core.
- Whether simultaneous multi-session viewing is useful after fast switching has been tested.
- Future orchestration of related agents and sessions.
- Product name.

## Out of scope

- Production-ready Claude Code or Codex integration during the navigation-shell comparison.
- Final language, framework, persistence architecture, and non-macOS support.
- Replacing or reimplementing native harness interfaces.

