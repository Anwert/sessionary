# Harness conversation identity transitions

Research date: 2026-08-30

## Question

Using only official interfaces and first-party behavior, how do Claude Code and
Codex identify independently resumable Harness conversations across resume,
compaction, context clearing, forks, and process restarts? Which relationships
and provenance can a Sessionary adapter rely on without forcing both Harnesses
into one transition model?

## Conclusion

For both Harnesses, the independently resumable object has one durable native
identifier: Claude Code's `session_id` and Codex's `thread.id`. Resume after a
process exit preserves that identifier; compaction preserves it; clear/new and
fork create a new identifier. Process identity, app-server connection identity,
and Codex `thread.sessionId` are not Harness conversation identity.

Sessionary should therefore keep every Harness conversation ID as an opaque key
scoped by adapter identity and add a new Conversation binding whenever the
adapter observes a new independently resumable conversation. It should not
encode a universal transition enum or derive Session identity from any Harness
ID. Transition evidence belongs in adapter-specific observations:

- Claude Code can reliably label `resume`, `clear`, and `compact` from official
  hooks, but its supported hook payloads do not supply the prior/new pair needed
  to reconstruct every lineage edge. A transition can be observed without
  inventing ancestry.
- Codex app-server exposes explicit fork provenance (`forkedFromId`) and separate
  subagent provenance (`parentThreadId`). Preserve those facts as different
  relationships. Its `sessionId` describes a live session tree and is not a
  durable conversation locator.
- A native Codex TUI wrapper has less evidence than an app-server client. It can
  learn the current thread ID through supported callbacks/environment, but
  Sessionary must not infer lineage by timestamps, rollout paths, or adjacency.

## Transition matrix

| Operation | Claude Code | Codex | Stable Sessionary interpretation |
|---|---|---|---|
| Fresh start | New `session_id` | New `thread.id` | New Harness conversation |
| Resume, including after process restart | Same `session_id`; new process appends to the existing conversation | Same `thread.id`; `thread/resume` reopens it and later turns append | Same Harness conversation; runtime identity may change |
| Manual or automatic compaction | Same `session_id`; history in the active context is replaced by a summary | Same `thread.id`; compaction emits items on that `threadId` | Same Harness conversation; record an observation, not a binding change |
| Clear/new context | `/clear` saves the old conversation and starts a new one with a new `session_id` | `/new` and `/clear` start a fresh thread, leaving the prior one resumable | New Harness conversation; no ancestry unless the Harness exposes it |
| Fork/branch | New `session_id`; original remains independently resumable | New `thread.id`; `forkedFromId` points to the source when known | New Harness conversation; record source only when explicitly supplied |

Claude's resume/fork identity semantics are stated directly in its architecture
documentation: resume reopens the same ID, while fork copies history into a new
ID. Its session-management documentation separately says `/clear` preserves the
old conversation for resume and starts a fresh conversation; `/compact` changes
the context within the current conversation. [Claude Code: How Claude Code
works](https://code.claude.com/docs/en/how-claude-code-works#resume-or-fork-sessions)
and [Claude Code: Manage sessions](https://code.claude.com/docs/en/sessions)

Codex defines a Thread as the conversation primitive. `thread/resume` takes an
existing thread ID, while `thread/fork` creates a new thread ID from stored
history. Manual compaction runs on, and reports progress against, the same
`threadId`. [OpenAI Codex: app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#core-primitives)

## Claude Code findings

### Identity and process lifetime

`session_id` is the resume locator. A resumed interactive or non-interactive
process uses the same ID and appends to the existing transcript. The transcript
is stored under a filename containing that ID, but the documented ID and resume
command—not the file path—are the adapter contract. Retention settings,
non-persistent sessions, and missing transcript data can make a once-observed ID
unresumable, so an ID is a locator rather than a guarantee of availability.
[Claude Code: Resume a session](https://code.claude.com/docs/en/sessions#resume-a-session)
and [Claude Code: Export and locate session data](https://code.claude.com/docs/en/sessions#export-and-locate-session-data)

Exiting and launching `claude --resume <session-id>` changes the OS process and
terminal runtime but not the Harness conversation ID. Resuming the same ID in
two processes is explicitly allowed and causes both processes to append to one
transcript. Consequently, process-to-conversation is not one-to-one and process
replacement must not create a Conversation binding.
[Claude Code: Manage sessions](https://code.claude.com/docs/en/sessions)

### Compaction is not an identity transition

Manual and automatic compaction summarize active context inside the current
conversation. `SessionStart` hooks run with `source: "compact"`, and the common
payload still contains `session_id`; `PreCompact` and `PostCompact` distinguish
manual from automatic compaction. This is reliable evidence that context was
rewritten, not that a new resumable conversation was created.
[Claude Code: Hooks reference](https://code.claude.com/docs/en/hooks#sessionstart)
and [Claude Code: Hooks guide](https://code.claude.com/docs/en/hooks-guide)

### Clear creates a new conversation

`/clear` (also `/reset` and `/new`) saves the previous conversation and starts a
new empty one. Claude's hooks make the boundary observable: the old session gets
a `SessionEnd` reason of `clear`, and the new session gets `SessionStart` with
`source: "clear"` and its own `session_id`. Naming may move or be retained
according to the command form, so names are not identifiers.
[Claude Code: Commands](https://code.claude.com/docs/en/commands)
and [Claude Code: Hooks reference](https://code.claude.com/docs/en/hooks)

The hook events do not document a `previous_session_id` or equivalent field.
An adapter that sees both events in one managed process may record that it
observed a clear boundary, but it should not claim a durable lineage edge from
the new conversation to the old one. Event loss or a process failure between
the two hooks must leave the relationship unknown rather than guessed.

### Fork creates a new conversation, but ancestry is not a hook contract

`/branch` and `--fork-session` copy history into a new `session_id`, preserving
the original as a separately resumable session. `/branch` prints both IDs for a
human and the picker groups forks under their root. These are first-party
behaviors, but the documented status-line and common hook payloads expose the
current `session_id`, not a structured `forked_from_session_id`. Because
Sessionary forbids screen scraping, it can safely detect the new current ID but
cannot promise machine-readable Claude fork ancestry from the native TUI.
[Claude Code: Branch a session](https://code.claude.com/docs/en/sessions#branch-a-session)
and [Claude Code: CLI reference](https://code.claude.com/docs/en/cli-reference)

## Codex findings

### `thread.id` is the durable conversation identifier

The app-server protocol calls a Thread “a conversation between a user and the
Codex agent.” `thread/start` creates one, `thread/resume` reopens one by ID, and
`thread/read` inspects stored state without resuming. A client reconnect or a
Codex process restart therefore does not imply a new thread; resuming the stored
ID preserves Harness conversation identity while replacing runtime/connection
identity. [OpenAI Codex: app-server lifecycle](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#lifecycle-overview)

Codex-generated IDs are documented as UUIDv7, but Sessionary should still store
them as opaque strings. Their format is not needed for equality, resume, or
uniqueness within the adapter namespace.
[OpenAI Codex: Thread schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ThreadListResponse.json)

### Compaction preserves the thread

`thread/compact/start` targets a thread ID and reports a `contextCompaction`
item through normal item notifications on the same `threadId`. There is no new
thread response or transition. Both manual compaction and any automatic
compaction observed in that event stream are changes to effective model context
inside the same Harness conversation.
[OpenAI Codex: Trigger thread compaction](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#example-trigger-thread-compaction)

### Clear/new creates a fresh thread

The official TUI declares `/new` as “start a new chat” and `/clear` as “clear
the terminal and start a new chat.” The first-party event implementation routes
both through fresh-session startup, while clear additionally marks its start
source as `Clear`; the previous thread remains resumable. A native wrapper may
observe the new thread ID, but there is no documented clear-parent field.
[OpenAI Codex: slash commands source](https://github.com/openai/codex/blob/main/codex-rs/tui/src/slash_command.rs)
and [OpenAI Codex: TUI session lifecycle source](https://github.com/openai/codex/blob/main/codex-rs/tui/src/app/event_dispatch.rs)

### Fork provenance is explicit in app-server

`thread/fork` creates a distinct thread ID and copies stored history, optionally
only through a specified turn. The returned Thread supplies `forkedFromId` when
the source is known. This is the supported provenance edge Sessionary can retain.
It must not be conflated with `parentThreadId`, which is reserved for subagents.
[OpenAI Codex: Fork a thread](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#fork-a-thread)
and [OpenAI Codex: Thread schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ThreadListResponse.json)

The same Thread also has `sessionId`, described as shared by threads in a live
session tree. App-server states that roots use their own ID, stored unloaded
threads report their own ID because resume makes one the root of a new live
tree, and a fork response likewise returns the fork as its new tree root. This
field is runtime grouping, not a durable ancestry or resume locator; persisting
it as Harness conversation identity would make identity change with loading
topology. `thread.id` remains the binding key.
[OpenAI Codex: Resume and fork semantics](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#resume-a-thread)

### Native TUI evidence is intentionally narrower

For a native TUI wrapper, Codex's supported `notify` callback includes the
current thread ID after completed turns, and current Codex versions expose
`CODEX_THREAD_ID` to child processes. These can identify the current
conversation, but neither is an external transition ledger. The app-server
Thread object is the supported source for `forkedFromId`; rollout filenames,
JSONL adjacency, timestamps, and internal SQLite rows must not be used to infer
relationships. [OpenAI Codex: notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)
and [OpenAI Codex: thread-ID environment implementation](https://github.com/openai/codex/blob/main/codex-rs/core/src/exec_env.rs)

## Stable adapter behavior

The shared contract should be deliberately small:

```text
HarnessConversationKey = { adapter_id, opaque_conversation_id }

ConversationObservation =
  | current(key, observed_at, evidence)
  | resumability(key, resumable | unavailable | unknown, observed_at)
  | transition(kind, from?, to, evidence)
  | relationship(kind, source, target, evidence)
```

Only equality of `{adapter_id, opaque_conversation_id}` is universal. Suggested
observation and relationship kinds are an extensible, adapter-owned vocabulary,
not an exhaustive cross-Harness state machine. In particular:

- `resume` and `compact` observations do not create a Conversation binding when
  the ID is unchanged;
- a newly observed ID during clear/new or fork creates a new binding to the
  existing Session, consistent with the many-to-one Sessionary model;
- `forked-from` is recorded for Codex when app-server supplies it, but remains
  absent/unknown for Claude unless a future official structured field appears;
- Codex `subagent-parent` stays separate from `forked-from` and does not by
  itself make the subagent thread an imported top-level Harness conversation;
- missing transition evidence never prevents binding a newly observed current
  ID, and never licenses inferring a relationship;
- every observation records its source capability and adapter/version so a
  future Harness change can be reconciled without rewriting durable identity.

This avoids making the richer Codex app-server graph the minimum interface, or
flattening Claude's useful lifecycle hooks into an inaccurate common model.

## Limits and version sensitivity

- Claude session availability depends on local persistence and retention; a
  stable ID can cease to be resumable.
- Claude's documented human-facing branch confirmation and picker grouping are
  not acceptable parser targets under Sessionary's no-screen-scraping rule.
- Codex app-server schemas are versioned with the installed binary. Sessionary
  should capability-detect fields and generate/use the matching schema rather
  than assume every supported Codex version exposes today's full Thread shape.
  [OpenAI Codex: Message schema](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#message-schema)
- No evidence found supports treating model context, transcript/rollout path,
  process ID, terminal pane ID, display name, or current working directory as a
  substitute for either Harness's conversation ID.

## Primary sources

- [Claude Code: Manage sessions](https://code.claude.com/docs/en/sessions)
- [Claude Code: How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Claude Code: Commands](https://code.claude.com/docs/en/commands)
- [Claude Code: Hooks reference](https://code.claude.com/docs/en/hooks)
- [Claude Code: CLI reference](https://code.claude.com/docs/en/cli-reference)
- [OpenAI Codex: app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [OpenAI Codex: Thread schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ThreadListResponse.json)
- [OpenAI Codex: TUI slash commands](https://github.com/openai/codex/blob/main/codex-rs/tui/src/slash_command.rs)
- [OpenAI Codex: TUI lifecycle dispatch](https://github.com/openai/codex/blob/main/codex-rs/tui/src/app/event_dispatch.rs)
- [OpenAI Codex: notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)
