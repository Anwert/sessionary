# Claude Code and Codex observability

Research date: 2026-08-30

## Question

Which supported or realistically observable signals do current Claude Code and Codex expose for context usage, token consumption, rate limits, working versus waiting state, session identity, resume, and lifecycle hooks, while leaving each harness otherwise native and unmodified?

## Executive conclusion

The two harnesses do not expose equivalent integration surfaces.

- **Claude Code can remain its native interactive TUI while supplying nearly everything the manager needs.** Its supported status-line command receives structured, live session JSON containing session identity and name, transcript path, model, workspace/worktree/repository metadata, current context-window token counts and capacity, estimated session cost, and subscription rate-limit windows. Its hooks add reliable signals for prompt submission, permission requests, assistant turn completion, failures, compaction, session start/end, and subagent lifecycle.
- **Codex exposes similarly rich data through `codex app-server`, not through an external observer of the stock TUI.** App-server is a supported JSON-RPC control plane with thread discovery/resume, turn and approval lifecycle, accumulated token usage and model context size, and ChatGPT rate-limit snapshots. Building on it means Sessionary becomes a Codex client, so it no longer leaves the native Codex TUI in charge of presentation.
- **A stock Codex TUI can still be wrapped, but its supported external signal is currently much narrower.** The `notify` command reports completed agent turns with thread/turn identity and messages. PTY process state can distinguish a live process from a dead one, but it cannot reliably distinguish “working” from “waiting for input” without parsing terminal output. Reading rollout JSONL or screen-scraping can expose more, but those are implementation details rather than stable integration contracts.

The practical design is therefore capability-based: use supported adapters where available, show unavailable/estimated fields honestly, and never make exact cross-harness parity a requirement. A first native-wrapper implementation can be rich for Claude and coarse for Codex; a later Codex app-server adapter can raise fidelity if replacing the stock TUI becomes acceptable.

## Capability matrix

| Signal | Claude Code, native interactive UI | Codex, native TUI wrapper | Codex app-server |
|---|---|---|---|
| Session identity | Supported: `session_id` in status-line and hook payloads | Supported at turn completion through `notify` as `thread-id` | Supported: thread IDs, list/search/loaded-list APIs |
| Human-readable name | Supported: custom `--name`/`/rename` or generated title in `session_name` | No supported external live-name feed found | Thread preview/title metadata is listable; manager-owned naming remains safest |
| Resume | Supported by ID or name with `--resume`; `--continue` resumes the latest relevant session | CLI supports resuming stored sessions; an external manager must retain/discover the thread identity | Supported `thread/resume`, with persisted usage replay when available |
| Working | Infer reliably between prompt submission and `Stop`/`StopFailure`; tool hooks can refine activity | Only coarse inference from process/PTY; no supported turn-start notification to an external wrapper found | Reliable `turn/started` and item lifecycle events |
| Waiting / needs input | `Stop` means Claude finished responding; `PermissionRequest` identifies permission prompts immediately; notifications cover delayed idle/input prompts | `notify` reliably identifies agent-turn completion; approval or arbitrary input waiting is not comprehensively exposed externally | Reliable turn completion plus explicit server requests for approvals and user input |
| Context used / capacity | Supported structured fields for input/cache/output counts, context size, used and remaining percentages | Displayed inside Codex, but no supported external stock-TUI feed found | Supported accumulated and latest usage plus model context window |
| Session token consumption | Supported structured context counts and estimated session cost; `/usage` gives detailed per-model totals | No supported external stock-TUI feed found | Supported accumulated token counters; no authoritative cumulative USD cost field documented |
| Account rate limits | Supported for Pro/Max in status-line JSON: five-hour and seven-day usage/reset fields | Visible in Codex UI, but no supported external stock-TUI feed found | Supported ChatGPT `account/rateLimits/read` and change notifications |
| Lifecycle hooks | Broad supported hook surface | Supported `notify` is a turn-complete callback; newer Codex hook facilities should be treated as version/capability dependent | Full structured thread, turn, item, approval, and input request events |

## Claude Code findings

### Status-line JSON is the primary passive telemetry surface

Claude Code runs a configured local status-line command with JSON on stdin. The command is refreshed on session start/resume, new assistant messages, compaction, permission-mode changes, timers, and rate-limit reset boundaries. This does not replace or reimplement the native Claude UI; the manager could install a tiny adapter that copies the payload to its own local state and prints the user's desired status line. [Anthropic: Customize your status line](https://code.claude.com/docs/en/statusline)

The documented payload includes:

- `session_id`, `session_name`, `transcript_path`, Claude Code version, model and current working directory;
- project directory, added directories, repository identity, Git worktree metadata and active worktree branch;
- `context_window.total_input_tokens`, `total_output_tokens`, `context_window_size`, `used_percentage`, `remaining_percentage`, plus cache-read/write breakdown from the latest response;
- estimated `cost.total_cost_usd`, durations, and changed-line totals;
- for Claude.ai Pro/Max accounts, `rate_limits.five_hour` and `rate_limits.seven_day` percentages and reset timestamps.

Important semantics: context usage represents the most recent API response, and the documented used percentage is input-only (including cache reads/writes), not cumulative lifetime consumption. The cost is a local estimate, not an invoice. Rate-limit fields can be absent before the first response, after their window expires, or for authentication modes that do not expose them. [Anthropic: status-line fields and context semantics](https://code.claude.com/docs/en/statusline#available-data)

Claude's `/usage` view separately presents detailed current-session tokens by model, activity and subscription plan usage. Anthropic says OpenTelemetry is the supported option for near-real-time per-user token and cost export across deployments, but that is organization-oriented telemetry rather than the simplest per-session desktop integration. [Anthropic: Manage costs effectively](https://code.claude.com/docs/en/costs)

### Hooks make activity state observable without screen parsing

Hook payloads share `session_id`, transcript path, current directory and event name. Relevant events include:

- `UserPromptSubmit`: the user handed work to Claude;
- `Stop`: the main agent finished responding and control returned to the user;
- `StopFailure`: the turn stopped because of an API/auth/rate-limit/other failure;
- `PermissionRequest`: Claude is about to ask the user for a tool permission;
- `Notification`: includes delayed permission/input/idle notifications;
- `SessionStart` and `SessionEnd`;
- `PreCompact` and `PostCompact`;
- `SubagentStart`, `SubagentStop`, `TeammateIdle`, task creation/completion, and other finer-grained lifecycle events.

This supports a robust state adapter: mark a session `working` on prompt submission, `needs_input` on `Stop` or `PermissionRequest`, and retain a more precise reason separately. `Stop` does **not** mean the user's larger task is finished; it only means Claude completed its current response. Product-level `finished` must remain a user-managed lifecycle state. [Anthropic: Hooks reference](https://code.claude.com/docs/en/hooks)

### Identity and resume are first-class

Claude supports `--name` and reports a custom or generated name in status data. `--resume` accepts a session ID or name and can also open an interactive picker; `--continue` resumes the most recent relevant conversation. `--fork-session` resumes context under a new session ID. [Anthropic: CLI reference](https://code.claude.com/docs/en/cli-reference)

## Codex findings

### App-server is the rich, supported integration boundary

The official Codex repository documents `codex app-server` as a JSON-RPC API used to build rich clients. It can list/search threads, list currently loaded threads, start/resume/fork/archive threads, start and interrupt turns, and stream thread/turn/item events. `turn/started` identifies active model work; `turn/completed` reports `completed`, `interrupted`, or `failed`; explicit server requests identify command/file-change/MCP/permission approvals and blocking user-input requests. This is substantially more reliable than inferring state from terminal pixels. [OpenAI Codex: app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

`thread/tokenUsage/updated` provides persisted and live token usage. The current source model separates accumulated session totals from the latest active context and includes input, cached input, cache-write input, output, reasoning output, total tokens, and the model context-window size. That is enough to display both lifetime token consumption and current context occupancy. [OpenAI Codex: token usage model](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/protocol.rs) and [OpenAI Codex: TUI token semantics](https://github.com/openai/codex/blob/main/codex-rs/tui/src/token_usage.rs)

For ChatGPT-authenticated accounts, app-server exposes `account/rateLimits/read` and sparse `account/rateLimits/updated` notifications. Responses include primary/secondary windows with used percentages, durations and reset timestamps when the backend supplies them. Availability and exact window shape are account/backend dependent. [OpenAI Codex: app-server rate limits](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#7-rate-limits-chatgpt)

The cost gap matters: the documented token structures do not provide an authoritative cumulative USD session cost. Sessionary can display token counts and subscription quota, but should not promise a precise Codex dollar cost without a separate supported billing source.

### The native TUI's external callback is deliberately coarse

The user-level `notify` configuration invokes a command with JSON when an agent turn completes. Current source shows the payload carrying a thread ID, turn ID, working directory, client, input messages, and last assistant message. This is enough to move a managed native Codex session from `working` to a general `needs_input` state after a completed turn. [OpenAI Codex: configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [OpenAI Codex: legacy notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)

It does not, by itself, provide context/rate-limit snapshots, turn start, every approval prompt, or process-independent session discovery. A wrapper can mark `working` when it forwards the user's input, but input submitted directly inside the untouched Codex TUI is opaque to the wrapper unless it owns the PTY and interprets traffic. Even with PTY ownership, terminal output parsing is fragile across Codex updates.

Codex's persisted rollout files contain richer event records and can realistically be observed locally. However, treating the JSONL archive or internal SQLite state as a product API couples Sessionary to storage schemas that OpenAI may change. Use such readers only behind a versioned, best-effort adapter with an explicit `unknown` fallback—not as the semantic source of truth.

## Recommended adapter contract

Avoid a lowest-common-denominator interface. Each adapter should report values with provenance and confidence:

```text
SessionIdentity: exact | discovered | manager_assigned
Activity: working | needs_input | stopped | unknown
AttentionReason: turn_complete | permission | question | failure | unknown
ContextUsage: { used_tokens, capacity_tokens, percent, observed_at } | unavailable
Consumption: { input, cached_input, output, reasoning, total } | unavailable
RateLimitWindow: { name, used_percent, resets_at }[] | unavailable
LifecycleCapabilities: a declared set per adapter/version
```

The first implementation should support these tiers:

1. **Claude native adapter:** status-line relay plus hooks; high-fidelity telemetry and activity while preserving the stock UI.
2. **Codex native adapter:** manager-owned launch/PTY plus `notify`; reliable process liveness and turn-complete attention, manager-owned naming/grouping, unknown context/rate-limit fields unless another supported source appears.
3. **Codex app-server adapter (later experiment):** high-fidelity telemetry and lifecycle, explicitly evaluated against the cost of recreating or embedding Codex interaction rather than claiming to be an untouched native TUI.

## Consequences for the UX prototypes

- Prototype rows must tolerate missing telemetry; use `—` or `unknown`, never a fake zero.
- `working` and `needs input` are observations of whose turn it is, while `finished` and `archived` remain user-owned lifecycle states.
- Context should be modeled as used tokens plus capacity, not only a percentage, because both harnesses can supply exact values on their rich interfaces.
- Account rate limits belong to the harness/account level, not to a session, even if Claude delivers them through each session's status-line payload.
- The UX should not assume every attention reason can be detected. Claude can distinguish permission from ordinary turn completion; the initial native Codex adapter may only know that the turn completed.

## Primary sources

- [Anthropic: Customize your status line](https://code.claude.com/docs/en/statusline)
- [Anthropic: Hooks reference](https://code.claude.com/docs/en/hooks)
- [Anthropic: CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Anthropic: Manage costs effectively](https://code.claude.com/docs/en/costs)
- [OpenAI Codex: app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [OpenAI Codex: configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [OpenAI Codex: token usage implementation](https://github.com/openai/codex/blob/main/codex-rs/tui/src/token_usage.rs)
- [OpenAI Codex: notify implementation](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/legacy_notify.rs)
