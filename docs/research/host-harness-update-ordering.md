# Host and Harness update-ordering contracts

Research date: 2026-08-30

## Question

Using the selected Rust foundation and only stable first-party interfaces, how
can Terminal Host, Claude Code adapter, and Codex adapter each linearize,
deduplicate, and reject stale status-bearing Command results and Events before
presenting their common interface to Coordinator?

This note also checks whether official ordering metadata or ordered streams
exist, when an implementation must reread current state, how initial status and
source restart reset prior observations, and whether correctness requires
narrowing an adapter capability.

## Conclusion

There is no sound universal revision mechanism that Sessionary can require from
all three sources. The common contract should require the **result**, not a
particular implementation:

> For each Session, a Terminal Host or Harness adapter must present Coordinator
> with a linearized sequence containing both status-bearing Command results and
> Events, suppress duplicates it can identify, and prevent messages from an old
> source connection or Session runtime from changing the current status. The
> adapter declares only the Harness status distinctions it can establish from
> stable first-party interfaces.

How a source satisfies that contract is capability-specific:

- tmux control mode provides one ordered transport for correlated Command
  output and asynchronous notifications, but many notifications are merely
  invalidations. Terminal Host should serialize one control connection, reread
  formatted tmux state after invalidations, and rebuild an initial snapshot on
  reconnect.
- Claude Code hooks provide useful lifecycle edges but no documented sequence
  or replay cursor. Synchronous hooks can feed an adapter-owned serializer;
  asynchronous hooks cannot establish strict status order and should not be an
  authoritative status source. `SessionStart` is a stable reset signal, but
  hooks alone do not provide a complete current-activity snapshot.
- The stock Codex TUI's `notify` callback supplies a thread and turn identity at
  turn completion, but no ordered lifecycle stream. It supports a coarse
  `Needs input` capability, with deduplication by turn identity; it cannot by
  itself prove `Working`, reject every stale completion, or reconstruct live
  status after adapter restart.
- Codex app-server does expose a single initialized JSON-RPC connection and
  documented thread/turn/item lifecycle ordering. It can support a richer
  adapter, with request IDs for responses and thread/turn/item IDs for
  deduplication, while a connection restart still requires a fresh snapshot.

Revisions exposed to Coordinator, if useful, must therefore be
**adapter-assigned local revisions**. They describe the order in which that
adapter accepted normalized updates; they are not evidence that an otherwise
unordered external callback was causally newer.

## Terminal Host: tmux control mode

tmux control mode is a documented text protocol on one client connection.
Every Command produces one output block delimited by `%begin` and `%end` or
`%error`; the guard lines contain a unique command number, and tmux does not mix
output from different Commands. The same stream carries asynchronous `%...`
notifications. tmux source explicitly requires notifications not to appear
inside a Command's output block. This gives Terminal Host a concrete
linearization point: one reader parses the control connection and serializes
completed Command blocks and notifications before emitting normalized results
and Events. [tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)
[tmux control-stream implementation](https://github.com/tmux/tmux/blob/master/control.c)

The command number correlates a Command's begin/end markers; it is not a global
state revision. Notifications such as `%sessions-changed` say that something
changed without carrying the new complete session set. Terminal Host must treat
these as invalidations and reread current state with formatted `list-sessions`,
`list-windows`, or `list-panes` output. tmux recommends stable `$session`,
`@window`, and `%pane` IDs instead of names or indexes. Format subscriptions can
deliver changed values but are evaluated at most once per second, so they are
state snapshots rather than a lossless event log.
[tmux control-mode notifications and subscriptions](https://github.com/tmux/tmux/wiki/Control-Mode#notifications)

Initialization and restart should be connection-scoped:

1. Open one control-mode connection to Sessionary's private tmux server.
2. Read an initial formatted snapshot before treating Terminal Host status as
   known.
3. Serialize all Command blocks, notifications, and reconciliation reads on
   that connection.
4. If the connection closes, discard its in-flight parser output, mark the
   source unknown internally, reconnect, and rebuild the snapshot. Any local
   revision counter restarts in a new private connection epoch.

The epoch is an implementation guard against late tasks from an old connection;
it need not become domain vocabulary or durable data.

## Claude Code adapter

Claude Code hooks run at documented lifecycle points. Each payload carries a
`session_id` and `hook_event_name`; `SessionStart` additionally distinguishes
`startup`, `resume`, `clear`, and `compact`. These fields identify the
conversation and lifecycle edge, but the documented payload has no sequence,
revision, replay cursor, or event timestamp that establishes causal order.
[Claude Code hooks reference](https://code.claude.com/docs/en/hooks)

Matching hooks for one event run in parallel. Identical hook Commands for that
event are deduplicated, but their completion order is not a status order. Hooks are blocking by default,
but setting `async: true` starts a separate process and lets Claude continue;
each asynchronous firing creates a separate process and Claude provides no
deduplication across multiple firings. An asynchronous hook therefore cannot
be the authoritative input to a strict `Working`/`Idle` ordering contract.
[Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide#how-hooks-work)
[Claude Code asynchronous hooks](https://code.claude.com/docs/en/hooks#run-hooks-in-the-background)

The native adapter can remain correct within a narrower contract:

- use synchronous hook delivery for status-bearing lifecycle edges and funnel
  every hook callback plus status-bearing Command result through one
  adapter-owned per-Session serializer;
- deduplicate only identities the adapter can prove locally (for example, the
  same callback delivery recorded before acknowledgement), rather than inventing
  causal order from arrival timestamps;
- on `SessionStart`, clear the previous runtime's Harness status; then remain
  conservative until later lifecycle evidence establishes a status;
- use the status-line integration for the current telemetry it actually
  exposes. Claude Code reruns it on session start/resume, assistant messages,
  compaction, permission-mode changes, and periodic refreshes, but it exposes no
  activity revision or replay cursor. The documented transcript file is written
  asynchronously and can lag in-memory state, so it is not a real-time ordering
  authority.
  [Claude Code status line](https://code.claude.com/docs/en/statusline)

If an adapter uses asynchronous hooks, it must downgrade them to hints (for
example, trigger a current-state read where one exists) or narrow its declared
status capability. Arrival order alone cannot reject a delayed old callback.

## Codex native-TUI adapter

The stable external callback for a stock Codex TUI is the configured `notify`
program. Its official implementation invokes the program for an
`agent-turn-complete` event and includes `thread-id` and `turn-id`, along with
the working directory, input messages, and last assistant message. Those IDs
allow a native adapter to deduplicate repeated delivery of the same completed
turn. The interface does not document a turn-start callback, a sequence number,
replay, acknowledgement, or a current live-status query.
[Codex notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)

Consequences:

- `notify` can reliably move the identified current turn to coarse `Needs
  input` when the callback is accepted.
- A manager-owned Command that submits input may tentatively establish
  `Working`, but input entered directly in the native TUI is not exposed by this
  callback.
- A `turn-id` distinguishes turns but is not documented as monotonic. Without a
  known current turn identity, arrival order cannot prove that a delayed
  completion belongs after a newly submitted turn.
- After adapter restart, there is no supported native-TUI snapshot that can
  reconstruct `Working` versus `Needs input`. The adapter must report the
  unclassifiable case as `Needs input`, consistent with the glossary, until a
  supported signal establishes more.

Strict `Working`/`Idle` ordering is therefore infeasible for a stock-TUI Codex
adapter using only this interface. The capability must remain coarse, or the
product must choose app-server instead.

## Codex app-server adapter

Codex app-server is a richer first-party boundary. A client must send one
`initialize` request and then `initialized` on each transport connection before
other methods. Requests and responses are correlated by JSON-RPC IDs, while the
same connection streams server notifications. The protocol documents the
causal lifecycle `turn/started` through `turn/completed`, and for each item,
`item/started` through zero or more deltas to `item/completed`.
[Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

An app-server adapter can therefore:

- use one reader/dispatcher for the connection and serialize status-bearing
  Command responses and notifications per thread;
- correlate responses by JSON-RPC request ID and deduplicate lifecycle messages
  by thread, turn, and item IDs;
- derive `Working` from `turn/started` and `Needs input`/failure detail from the
  terminal turn event or explicit approval/user-input request;
- on disconnect, reject all output from tasks attached to that old connection,
  initialize a new connection, and use `thread/list`, `thread/read`, or
  `thread/resume` to re-establish current state before publishing it.

The protocol does not document a universal monotonically increasing event
revision. Thread/turn/item identity and documented lifecycle order are the
available correctness tools. Ephemeral realtime notifications are explicitly
not returned by `thread/read`, `thread/resume`, or `thread/fork`, so an adapter
that exposes realtime-derived status must reset it across reconnect rather than
pretend it was replayed.

## Common-interface requirements

The interface to Coordinator should specify these invariants without exposing
source mechanics:

1. **One owner per source status.** Terminal Host alone emits `Runtime status`;
   one selected Harness adapter alone emits `Harness status`.
2. **Commands and Events share the same source order.** If either carries a
   status, the source linearizes both before Coordinator sees them.
3. **Local stale rejection.** The source rejects output from superseded
   connections and Session runtimes. It may attach an opaque, local revision to
   normalized updates, but Coordinator must not interpret it across sources.
4. **Capability honesty.** A source emits only distinctions its stable
   interface can establish. The glossary's `Needs input` deliberately covers a
   Harness that cannot be classified reliably as `Working` or `Idle`.
5. **Initialization before certainty.** Until a source has supplied its initial
   current status for the active runtime, its field is absent in Coordinator
   memory and the derived `UI status` is `Loading` where that field is needed.
6. **Restart resets live knowledge.** Reconnection starts a new private source
   epoch, discards old in-flight output, and rebuilds current status from the
   strongest supported snapshot. This is implementation state, not SQLite data.
7. **No wall-clock arbitration.** Receipt timestamps are useful for diagnostics
   but do not prove causal order and must not select a winner.

The exact serializer—an actor, a short lock, or a single reader task—is an
implementation decision for each source. A future implementation ticket should
require deterministic tests that pause Command completion and Event delivery,
reverse their arrival order, restart a source with old tasks still pending, and
verify that only the adapter's linearized current update reaches Coordinator.

## Primary sources

- [tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)
- [tmux control-stream implementation](https://github.com/tmux/tmux/blob/master/control.c)
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
- [Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide)
- [Claude Code status line](https://code.claude.com/docs/en/statusline)
- [Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Codex native notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)
