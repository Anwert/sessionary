# Existing Harness Session discovery and import feasibility

Research date: 2026-08-30

## Question

Using only official hooks, events, APIs, documented local state, and first-party
source code, what can Sessionary reliably discover about Claude Code and Codex
Sessions it did not launch? Can it tell whether they are live or resumable and
return to them while preserving the native Harness TUI?

Screen scraping is excluded. This note establishes technical capabilities and
does not decide what the product should call “import” or how that UX should work.

## Conclusion

Sessionary can discover **resumable Harness conversations** on the local machine
for both Claude Code and Codex, then start the Harness's native TUI with the
conversation's stable ID. It cannot, from Harness persistence alone, reliably
tell whether the original terminal process is still alive or attach to that
exact terminal.

Exact live attachment is feasible when the process already lives in a reachable
tmux server: tmux can enumerate its sessions, windows and panes using documented
formats and attach a client to the existing PTY. Correlating such a pane to a
Harness Session is exact only when an official Harness signal supplied the
conversation ID or Sessionary-owned metadata was previously written to the tmux
object. Process names and working directories are useful candidate hints, not a
stable identity join.

Therefore there are two technically distinct import capabilities:

1. **Adopt a live terminal:** exact and native when Sessionary can correlate a
   tmux pane with a Harness conversation ID; otherwise present only a candidate
   that requires confirmation.
2. **Register a resumable conversation:** broadly feasible for persisted local
   conversations; opening starts a new native Harness TUI process rather than
   reattaching to the old terminal.

## Capability matrix

| Capability | Claude Code | Codex | Confidence / boundary |
|---|---|---|---|
| Enumerate stored conversations | Documented local JSONL directory and interactive picker; no documented machine-readable list API | Stable app-server `thread/list` API with pagination and filters | High; Claude enumeration metadata is less formally specified |
| Stable conversation ID | `session_id`; transcript filename is `<session-id>.jsonl` | app-server `thread.id` / CLI resume ID | High |
| Useful metadata | Hook/status payloads: ID, name, transcript, cwd; picker shows name/title, recency, branch, project | app-server thread metadata includes ID, preview/name, cwd, timestamps, source, archive state and status | High through official surfaces; do not parse terminal output |
| Determine resumability | Attempt native resume; retention and disabled persistence can remove history | `thread/read` and `thread/resume`; CLI can resume by ID | High, but the final authority is a successful resume |
| Determine whether original native TUI is live | Not from transcript storage; hooks observe only sessions that invoke them | A separate app-server lists stored threads as `notLoaded`; `thread/loaded/list` is runtime-local, not a global OS process registry | Not reliably possible from Harness state alone |
| Attach to exact live native TUI | Yes only through its existing terminal host (for example tmux), not by `claude --resume` | Same for stock Codex TUI | High |
| Resume into a new native TUI | `claude --resume <session-id>` | `codex resume <session-id>` | High |
| Detect future activity after adoption | Official Claude hooks can report the ID and lifecycle once installed and invoked | Stock TUI has only coarse supported callbacks; app-server has full events but is a different client surface | Capability-based and version-dependent |

## Claude Code

### Stored conversation discovery

Claude Code documents CLI transcript storage at
`~/.claude/projects/<project>/<session-id>.jsonl` (or beneath
`CLAUDE_CONFIG_DIR`). Sessions are saved continuously, retained for 30 days by
default, and may be suppressed with `CLAUDE_CODE_SKIP_PROMPT_HISTORY` or
`--no-session-persistence`. This makes directory enumeration a documented way to
find candidate IDs, but the documentation only promises that JSONL lines are
messages, tool uses, or metadata entries; it does not publish a versioned schema
for building a complete external index from transcript contents. Sessionary
should treat the filename/ID and path as durable locators and avoid depending on
undocumented JSON fields. [Anthropic: Manage sessions](https://code.claude.com/docs/en/sessions#export-and-locate-session-data)

The native picker has richer discovery semantics but is interactive rather than
a machine API. It can widen from the current worktree to all worktrees or every
project on the machine, and shows names or generated titles, recency, branch,
project path, and file size. It intentionally omits `-p` and Agent SDK sessions,
although those remain resumable by exact ID. Consequently, reproducing the
picker's visible list is not equivalent to enumerating all persisted
conversations. [Anthropic: Manage sessions](https://code.claude.com/docs/en/sessions#use-the-session-picker)

### Identity, liveness, and return

Official hooks provide `session_id`, `transcript_path`, and `cwd` on every hook
event. `SessionStart` distinguishes `startup` from `resume`, and `SessionEnd`
reports termination. A status-line command additionally receives the unique ID
and `session_name`. These signals can create an exact correlation for a Session
that emits an event after Sessionary's integration is configured; they do not
retroactively prove that every transcript has a live terminal process.
[Anthropic: Hooks reference](https://code.claude.com/docs/en/hooks#common-input-fields)
and [Anthropic: status-line data](https://code.claude.com/docs/en/statusline#available-data)

`claude --resume <session-id>` resumes the same conversation and appends to its
history in a new native CLI process. This is conversation continuity, not PTY
attachment. Anthropic explicitly warns that resuming one session in two
terminals causes messages from both to interleave in one transcript, so a
discovered live copy must not be blindly resumed in parallel.
[Anthropic: Manage sessions](https://code.claude.com/docs/en/sessions#resume-a-session)

Resume does not restore every launch option: settings supplied through flags
such as `--mcp-config`, `--settings`, `--plugin-dir`, `--fallback-model`, and
`--add-dir` may need to be provided again. A successful resume therefore proves
conversation recovery, not exact reconstruction of the original invocation.
[Anthropic: what is restored on resume](https://code.claude.com/docs/en/sessions#what-gets-restored)

## Codex

### Stored thread discovery through app-server

Codex has the stronger machine-readable discovery surface. The official
`codex app-server` protocol exposes `thread/list`, `thread/read`, and
`thread/resume`. `thread/list` is paginated and filters by source kind, model
provider, archive state, cwd, and search text. The default source filter includes
interactive CLI and VS Code threads, so an exhaustive importer must explicitly
request every supported source kind it intends to consider rather than assuming
the default means “all.” Returned thread metadata includes stable ID, preview or
name, cwd, timestamps, source, archive state, and status.
[OpenAI: codex app-server thread APIs](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#threads)

Codex also persists rollout JSONL under the Codex home sessions directory, and
first-party source implements discovery from these files. Direct file reading is
not needed for Sessionary's primary discovery path because app-server already
provides a typed protocol over that persistence. The rollout storage and index
are implementation details and have already changed; using app-server avoids
binding import to their schemas.
[OpenAI: rollout persistence source](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/recorder.rs)

### Liveness and return

`thread/list` reports `notLoaded`, `idle`, `active`, or `systemError`, and
`thread/loaded/list` returns IDs loaded in the current app-server runtime. These
are reliable for threads owned by that app-server, but a newly started app-server
is not a global registry of unrelated stock Codex TUI processes. In particular,
a stored thread normally appears `notLoaded` to this new runtime even if another
terminal process exists. The protocol also documents exclusive write ownership
for newer paginated threads: a resume can fail if another app-server process
already owns the thread. Sessionary may use that failure as evidence of a
conflict, but not as a complete live-process discovery mechanism.
[OpenAI: thread list and loaded list](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#list-threads-with-pagination--filters)
and [OpenAI: resume ownership](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#resume-a-thread)

`thread/resume` continues a conversation inside an app-server client; it does
not attach to an existing stock TUI and would require Sessionary to provide the
interaction UI. To preserve the native Codex TUI, Sessionary can instead invoke
the official CLI resume command with the discovered ID. That starts a new native
TUI process, so the same duplicate-live-session caution applies even though the
technical resume mechanism is sound.
[OpenAI: Codex CLI sessions](https://learn.chatgpt.com/docs/codex/cli#resume-conversations)

## tmux as the live correlation layer

tmux can enumerate sessions/windows/panes through list commands and documented
formats, and control mode exposes stable session/window/pane IDs plus structured
notifications. Its documentation recommends IDs over names or indexes because
IDs are unambiguous. A client can attach to an existing session without stopping
the programs in its panes, preserving the exact native Harness TUI and any
in-progress prompt.
[tmux: Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)
and [tmux: Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started#attaching-and-detaching)

For tmux objects created outside Sessionary, documented formats such as
`pane_pid`, `pane_current_command`, and `pane_current_path` can narrow candidates.
They cannot supply the Harness conversation ID, distinguish all wrapper/process
tree arrangements, or prove that a similarly named process is the intended
Session. Sessionary should never upgrade those hints into an automatic identity
match. Exact correlation requires one of:

- a Harness hook/event carrying the conversation ID and a tmux pane identity;
- Sessionary metadata previously written as a tmux user option; or
- explicit user confirmation of the candidate.

tmux user options are a documented metadata channel and format subscriptions can
observe changes without parsing pane output.
[tmux: formats and user options](https://github.com/tmux/tmux/wiki/Control-Mode#general-notes)

## Feasible technical contract

Discovery should return evidence, not a false binary “importable” flag:

```text
DiscoveredConversation {
  harness
  conversation_id
  resume_locator
  metadata
  evidence: official_api | documented_storage | hook_event
  live_terminal: Exact(host_id) | Candidate(host_id) | None
  capabilities: { native_resume, exact_live_attach, live_activity_events }
}
```

Rules supported by the evidence:

- Never infer identity or status from terminal pixels.
- Prefer Claude's documented ID/path and Codex app-server over parsing internal
  transcript or rollout schemas.
- Treat “stored/resumable” and “live/attachable” as independent facts.
- Attempt native resume only after checking for an exact live-terminal match or
  obtaining confirmation; a successful resume is the final resumability check.
- Preserve the Harness conversation ID while keeping it distinct from the
  Sessionary Session identity and tmux pane/session IDs.
- Record adapter version and evidence provenance so behavior can degrade to
  `Needs input` when a supported capability is absent or uncertain.

## Remaining uncertainty and validation work

- Claude Code exposes no documented non-interactive equivalent of its complete
  picker. A small compatibility test should compare documented transcript
  enumeration with the current picker across interactive, `-p`, SDK, forked,
  worktree, expired, and persistence-disabled sessions.
- Verify whether hooks added while an already-running Claude process is open are
  reloaded soon enough to establish live correlation; no guarantee was found, so
  the design must not depend on it.
- Exercise Codex `thread/list` with every source kind and multiple simultaneously
  running stock TUI/app-server processes. Do not interpret `notLoaded` as “not
  live” until first-party semantics provide a machine-wide guarantee.
- Test native resume conflicts for each Harness. The safe product behavior is a
  later UX decision; the technical layer should report the exact evidence and
  refusal/error without inventing a lifecycle state.

## Primary sources

- [Anthropic: Manage sessions](https://code.claude.com/docs/en/sessions)
- [Anthropic: Hooks reference](https://code.claude.com/docs/en/hooks)
- [Anthropic: Customize your status line](https://code.claude.com/docs/en/statusline)
- [OpenAI: Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [OpenAI: Codex rollout recorder source](https://github.com/openai/codex/blob/main/codex-rs/rollout/src/recorder.rs)
- [OpenAI: Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
- [tmux: Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)
- [tmux: Getting Started](https://github.com/tmux/tmux/wiki/Getting-Started)
