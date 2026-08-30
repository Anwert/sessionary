# Native Harness session-state observability

Research date: 2026-08-30

## Question

What can an external terminal-session manager reliably observe from the native
Claude Code and Codex TUIs to distinguish `Working`, `Needs input`, and `Idle`,
without replacing either Harness UI? What follows for Sessionary's Finish gate?

This note reports facts and their decision consequences. It does not choose the
product state model. It uses the terminology and constraints in `CONTEXT.md`,
the map “Find the keyboard-first multi-harness session manager UX,” and the
resolution of “Decide whether Finish stops the live Harness”: Finish currently
stops a live Harness and is allowed only from `Idle`.

## Executive findings

1. **Claude Code exposes a supported, native-TUI lifecycle surface.**
   `UserPromptSubmit`, `PermissionRequest`, `Stop`, and `StopFailure` hooks give
   Sessionary reliable turn-start, blocked-on-permission, and turn-end events.
   Claude Code's `Stop` means “Claude finished responding,” not “the user has
   acknowledged the result” and not “the larger task is finished.”
2. **Current native Codex exposes more than its legacy `notify` callback.**
   `notify` still reports only completed turns, but the stock TUI now has a
   configurable terminal-title surface. It can emit `Ready`, `Working`, or
   `Thinking`, and an `Action Required` title while an approval modal requires
   the user. tmux records application-set terminal titles as `pane_title`, so a
   private tmux host can observe this without screen-scraping or replacing the
   Codex TUI.
3. **The Codex terminal-title signal is version- and configuration-dependent.**
   Sessionary would need to detect support and launch Codex with the appropriate
   terminal-title items. Older versions still provide only turn-complete
   `notify` plus raw terminal traffic. Raw PTY/process observations alone do not
   prove semantic `Idle`.
4. **Harness run state and user attention are not the same axis.** A completed
   turn is no longer running, but its unseen result may still be `Needs input`
   in Sessionary. Conversely, an approval request is `Needs input` while the
   same turn remains active. One state label therefore cannot by itself answer
   both “does the user owe attention?” and “is it safe to stop without cutting
   off a turn?”
5. **Allowing Finish from every `Needs input` Session is unsafe.** It would also
   permit Finish during an in-turn approval or elicitation. Treating uncertain
   observations as `Needs input` is conservative for attention, but it does not
   establish the idle/no-active-turn precondition needed by the current Finish
   rule.

## Observable transition matrix

| Situation | Claude Code native TUI | Codex native TUI, current | Codex native TUI, legacy fallback |
|---|---|---|---|
| User submits a prompt | Exact `UserPromptSubmit` hook | Terminal title changes from `Ready` to an active run state | No supported turn-start callback; PTY input interpretation only |
| Harness performs a turn | Between submit and `Stop`/`StopFailure` | `Working` or `Thinking` terminal-title run state; animated activity can supplement it | Not provable from process liveness; screen/output heuristics only |
| Approval is requested | Exact `PermissionRequest` hook | Terminal title becomes `Action Required` for a pending approval modal | External `notify` does not report approvals |
| Other structured user input is requested | `Elicitation` hook for MCP input; notifications can identify permission/input/idle prompts | Native UI has action-required presentation, but the exact coverage of every prompt type should be capability-tested against the installed version | Not comprehensively exposed |
| Turn completes | Exact `Stop`, or `StopFailure` on API failure | Exact legacy `notify` callback; run-state title also returns to `Ready` | Exact `notify` callback |
| Process exits | Exact `SessionEnd` hook plus terminal-host process exit | Terminal-host process exit | Terminal-host process exit |
| User has seen/acknowledged a completed result | Not a Harness lifecycle event | Not a Harness lifecycle event | Not a Harness lifecycle event |

## Claude Code

Claude Code documents hooks as lifecycle events that fire in the terminal TUI
as well as its other clients. Its per-turn sequence includes
`UserPromptSubmit` before processing, `PermissionRequest` when a tool needs a
decision, `Stop` when Claude finishes responding, and `StopFailure` when the
turn ends because of an API error. `Elicitation` fires when an MCP server asks
the user for input. `SessionStart` and `SessionEnd` bracket process/session
lifecycle. [Anthropic hooks reference](https://code.claude.com/docs/en/hooks#hook-lifecycle)

These events support the following reliable adapter facts while preserving the
native UI:

- `UserPromptSubmit` establishes that a main turn began.
- `PermissionRequest` establishes both that attention is required and that the
  turn has not ended.
- `Stop` or `StopFailure` establishes that the turn ended. Neither establishes
  that the user has read the result.
- `SessionEnd` establishes that the native session terminated.

Claude's `Notification` event can add reasons such as permission prompts,
input prompts, and idle prompts, but it is a notification surface, not a
replacement for the turn lifecycle above. [Anthropic `Notification` hook](https://code.claude.com/docs/en/hooks#notification)

Therefore Claude can prove “no main turn currently active” after a matched
`Stop`/`StopFailure`, assuming Sessionary observed the session continuously and
did not miss/reorder hook delivery. The separate transition from “completed
result needs attention” to Sessionary `Idle` must come from Sessionary's own
acknowledgement policy (for example, focusing/visiting the Session), because
Claude has no event meaning “the user has absorbed this result.”

## Native Codex

### Legacy `notify`: exact turn end, nothing more

The user-level `notify` command is documented and implemented as an external
command spawned after each completed turn. Its payload contains an
`agent-turn-complete` type, thread and turn IDs, cwd, client, input messages,
and the last assistant message. The implementation has only the
`AgentTurnComplete` variant. It does not emit turn start, approval requested,
or arbitrary user-input-request events. [Codex configuration source](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/core/src/config/mod.rs#L988-L1011),
[legacy notify implementation](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/hooks/src/legacy_notify.rs#L12-L42)

The TUI's own notification settings include events such as completed turns and
approval requests, but those settings choose desktop/in-terminal notification
delivery; they do not broaden the external legacy `notify` hook. The first-party
repository explicitly describes `notify` as running when the agent finishes a
turn. [Codex native README](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/README.md#notifications)

### Terminal title: a native, externally observable run-state surface

Current Codex source defines configurable terminal-title items. In particular:

- `activity` is a spinner while working and an action-required message while
  blocked;
- `run-state` renders `Ready`, `Working`, or `Thinking` (and currently an
  internal `Waiting` state for a background terminal);
- the default title selection is `activity` plus project name, while explicit
  configuration can include `run-state`.

[Codex terminal-title item definitions](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/tui/src/bottom_pane/title_setup.rs#L27-L111),
[run-state rendering](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/tui/src/chatwidget/status_surfaces.rs#L927-L966)

The TUI writes the title as an OSC 0 terminal escape sequence. Its tests verify
that an execution approval changes the title to `Action Required`, and that the
normal title is restored after approval. [Codex OSC title writer](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/tui/src/terminal_title.rs#L42-L78),
[approval/title tests](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/tui/src/chatwidget/tests/terminal_title.rs#L65-L128)

tmux gives each pane a title and allows the program in the pane to set it with
the same terminal escape mechanism. The value is available as the
`pane_title` format; a control-mode client can subscribe to formats and receive
a notification when the expanded value changes. This is structured terminal
metadata, not parsing rendered Codex screen cells. [tmux pane-title documentation](https://github.com/tmux/tmux/wiki/Advanced-Use#pane-titles-and-the-terminal-title),
[tmux control-mode format subscriptions](https://github.com/tmux/tmux/wiki/Control-Mode#format-subscriptions)

A current native-Codex adapter can consequently launch Codex with a dedicated
title selection including both `run-state` and `activity`, then subscribe to
`#{pane_title}` on its private tmux pane. This preserves direct use of the
native TUI, including native prompt editing and skill completion.

Important limits:

- This capability is not present in every historical Codex version. It needs a
  version/capability check and a fallback, not an assumption about all installs.
- Sessionary must control or compose the terminal-title configuration. If the
  user removes `run-state` or `activity`, the corresponding fact disappears.
- `Action Required` is a presentation-level category. Current source/tests
  establish it for approval views. Sessionary should validate other blocking
  prompt types per supported Codex version before claiming exhaustive coverage.
- A missing or stale title is not proof of `Ready`; process exit, startup,
  configuration errors, dropped observation, and unsupported versions must be
  represented separately in adapter health/capabilities.

### Why PTY/process observation is not an equivalent fallback

A PTY host observes a process lifetime and a terminal byte stream. tmux control
mode forwards pane output, including terminal escape sequences, but does not
attach Harness semantics to arbitrary screen output. [tmux control-mode pane output](https://github.com/tmux/tmux/wiki/Control-Mode#pane-output)

Without a declared signal such as Codex's terminal title, the same live process
can be blocked on terminal input, waiting on a child process, waiting on the
network, or ready in its composer. Output silence occurs in all of those cases.
Input bytes also do not reliably mean “a prompt was submitted”: they include
editing, completion, navigation, paste, approval keys, and escape sequences.
Interpreting rendered text or persisted rollout/SQLite internals may be useful
as a versioned best-effort adapter, but it is not a stable semantic contract.

Thus process liveness proves only “live versus exited.” Raw input/output may
support heuristics, but cannot prove `Working`, `Needs input`, or `Idle` in the
legacy fallback.

## Codex app-server alternative

`codex app-server` is a supported JSON-RPC integration surface. It emits
`turn/started` and `turn/completed`, and sends explicit server requests for
command/file approvals and `request_user_input`. This is the strongest Codex
source for exact turn and blocking-request lifecycle. [Codex app-server lifecycle and turn events](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/app-server/README.md#lifecycle-overview),
[approvals and user input](https://github.com/openai/codex/blob/28327355b861ab6cc76b01c7248663eb1be440cf/codex-rs/app-server/README.md#approvals)

The tradeoff is presentation, not merely installation. With app-server,
Sessionary becomes the client that sends input, renders streaming items, and
presents approvals/input requests. It therefore replaces or recreates the
stock Codex TUI interaction instead of attaching the user directly to it. That
conflicts with the map's current native-Harness constraint unless Codex gains a
supported way to mirror app-server events into an independently running stock
TUI.

## Consequences for Sessionary's state and Finish decision

### “Idle” has two possible meanings that must not be conflated

The established definition says an `Idle` Session is neither performing a turn
nor requiring user attention. Harness signals can establish the first half;
only Sessionary interaction policy can settle the second after a completed
result:

```text
turn active, no prompt       -> Working
turn active, blocked on user -> Needs input (unsafe to stop as idle)
turn ended, result unseen    -> Needs input (no active turn)
turn ended, result seen      -> Idle
```

Both middle rows are legitimately `Needs input` under the current definition,
but they have different termination safety. An internal fact such as
`turn_activity = active | inactive | unknown`, or an equivalent Finish
precondition independent of the display state, would preserve that distinction
without necessarily adding another user-visible Session state.

### Can Idle be proven?

- **Claude native:** turn inactivity can be proven from a continuously observed
  submit/stop hook pair. Sessionary must still supply acknowledgement to clear
  attention and reach `Idle`.
- **Current Codex native:** `Ready` plus absence of `Action Required`, observed
  from a healthy, configured terminal-title capability, can establish TUI run
  inactivity; turn-complete `notify` strengthens the transition. Sessionary
  still supplies acknowledgement.
- **Legacy/unsupported Codex native:** raw PTY and process signals cannot prove
  inactivity. The honest fact is `unknown`, even if the conservative UI label
  is `Needs input`.
- **Codex app-server:** exact turn lifecycle and pending request state are
  available, at the cost of replacing native-TUI presentation.

### Can Needs input safely subsume ambiguity?

It can conservatively subsume ambiguity for routing attention: the user is less
likely to overlook a Session. It cannot convert ambiguity into proof that no
turn is active. If Sessionary shows uncertain legacy Codex as `Needs input`, it
still needs a separate capability/observation fact for operations whose safety
depends on turn inactivity.

### Can Finish safely be allowed from Needs input?

Not as a blanket rule. `Needs input` includes active-turn approvals and input
requests in both Harnesses. Terminating there cuts off an unfinished turn—the
condition the existing Idle-only rule was created to prevent.

The evidence leaves several decision shapes open:

- retain `Idle` and make user acknowledgement the `Needs input -> Idle`
  transition, while requiring exact `turn inactive` evidence for Finish;
- retain the visible states but model turn activity/observation health as a
  separate internal fact used by Finish;
- define a distinct, explicit force-stop path for unknown/blocked states, with
  semantics different from ordinary Finish;
- decline Finish for native-Codex versions that lack the required title
  capability, rather than inferring safety from PTY silence.

Removing `Idle` does not remove the operational question. If Finish remains a
safe stop rather than an interruption, the product still needs to distinguish
an inactive completed turn from an active turn blocked on the user.

## Source snapshot

Codex source links in this note are pinned to commit
`28327355b861ab6cc76b01c7248663eb1be440cf` (the `main` head observed on
2026-08-30). Because the native terminal-title integration is evolving,
implementation should validate its minimum supported Codex version against
that capability rather than relying only on the research date.
