# Background session hosting

## Question

What can keep an unmodified Claude Code or Codex terminal session alive after
Sessionary's UI closes, and what does each option imply for the UX?

## Decision

Use a **live terminal host** as the primary persistence model and treat
harness-native resume as recovery, not as the normal meaning of “return to a
session.” For an initial product implementation, put that host behind a small
backend interface and implement a **tmux backend first**. Do not build a custom
PTY daemon until the tmux-backed UX has proved that tmux itself is the limiting
factor.

This gives the UI the guarantee the product actually needs: closing or crashing
the UI does not stop the harness, and reopening a session returns to the same
live terminal. It also avoids coupling the product to Claude Code's or Codex's
internal conversation storage.

## Persistence models

### tmux: best first live-host backend

tmux runs a server separate from attached clients. Its sessions contain PTYs,
survive client detach or connection loss, and can have multiple attached
clients. The server lasts while it has sessions. This is exactly the lifetime
boundary Sessionary wants: the manager UI is merely a client, not the owner of
the harness process. [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)

It is also unusually integration-friendly. tmux control mode is a documented
text protocol for issuing commands and receiving asynchronous session, pane,
and output notifications; it supports stable IDs, pane output, resize, flow
control, and format subscriptions. Sessionary can therefore manage tmux without
scraping tmux's human UI. [tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)

UX consequences:

- Focus mode can attach to the exact live PTY and preserve native harness
  behavior, including prompts and an in-progress agent turn.
- Overview can list and switch sessions without keeping every terminal rendered.
- Sessionary should use a private tmux socket/server namespace and stable tmux
  IDs. This avoids colliding with the user's own tmux layout and key bindings.
- The tmux server is still a single failure boundary: killing it or rebooting the
  machine ends live processes. Stored metadata and harness resume IDs remain
  necessary for graceful degradation.
- Shipping tmux as a dependency is operational work, especially if macOS-first
  installation should feel self-contained. It is nevertheless much smaller
  than implementing a terminal multiplexer.

### Zellij: viable live host, richer but less neutral

Zellij can create sessions in the background and attach to already-running
sessions, so it can provide the same basic UI-independent lifetime.
[Zellij commands](https://zellij.dev/documentation/commands.html)

Zellij additionally serializes exited sessions. That feature is **recreation,
not process continuity**: it stores layout and discovered pane commands, then
reruns those commands (behind a confirmation banner by default). Viewport and
scrollback persistence are optional, and command discovery can be inaccurate.
[Zellij session resurrection](https://zellij.dev/documentation/session-resurrection.html)

UX consequences:

- Attaching to a running Zellij session can support exact live return.
- “Resurrecting” after a Zellij crash must not be presented as the same guarantee:
  restarting `claude` or `codex` is not equivalent to restoring its process and
  may require harness-native resume arguments.
- Zellij brings its own layout, modes, plugins, and session-manager concepts.
  Those are useful for a human-facing multiplexer but overlap more with
  Sessionary's product surface. It is a reasonable later backend, not the best
  reference backend for a deliberately harness-agnostic shell.

### Dedicated PTY daemon: maximum control, maximum terminal work

A custom daemon can own a PTY master for each harness while short-lived UI
clients attach over a Unix socket. `forkpty` combines PTY creation, process
creation, and establishment of the slave as the child's controlling terminal;
the host must retain and broker the master side.
[openpty/forkpty manual](https://man7.org/linux/man-pages/man3/openpty.3.html)

That minimal description hides most of a multiplexer. The host must handle
terminal modes, controlling process groups, window-size propagation, signals,
input ownership, output buffering and backpressure, scrollback, reconnect and
client races, Unicode/escape streams, authentication of its socket, process
reaping, and crash cleanup. The terminal ioctl surface alone includes window
size, controlling-terminal, process-group, and PTY controls.
[terminal ioctl manual](https://man7.org/linux/man-pages/man4/tty_ioctl.4.html)

UX consequences:

- It offers the cleanest invisible implementation: no foreign prefix keys,
  status bar, or user-visible multiplexer concepts.
- Sessionary could define exact multi-client, resize, history, and notification
  semantics.
- The daemon becomes the same live-session failure boundary as tmux, but one the
  project must make reliable. A daemon restart cannot recreate an arbitrary
  running process merely from saved metadata.
- Building it before validating the navigation UX spends substantial effort on
  terminal correctness without answering the product question.

### Harness-native resume: recovery, not background execution

Claude Code supports continuing the most recent conversation and resuming a
specific session by ID. [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-reference)
Codex exposes `codex resume`, with a picker by default and `--last` for the most
recent saved interactive session; its current CLI source also separates resume,
archive, delete, unarchive, and fork operations.
[Codex CLI source](https://github.com/openai/codex/blob/main/codex-rs/cli/src/main.rs#L2499-L2524)

These commands start a new harness process from saved conversation state. They
do not keep the original terminal process alive. Consequently, native resume
cannot preserve an in-progress local command, a permission prompt currently on
screen, ephemeral terminal modes, or exact screen state. It is nonetheless the
right fallback after logout, reboot, live-host failure, or an intentionally
stopped session.

UX consequences:

- Sessionary must distinguish **live attach** from **conversation resume** even
  if both are surfaced as one “Open” command. Recovery may take longer or fail.
- It needs a per-harness adapter for capturing and invoking stable resume IDs.
- Native resume is harness-specific and version-sensitive, so it cannot be the
  sole abstraction behind a promise of uniform background work.
- A resumed conversation should keep the same Sessionary session identity while
  its underlying process/PTY identity changes.

## Recommended abstraction

Keep these identities separate:

1. **Sessionary session** — durable product identity, name, group, lifecycle,
   repository metadata, and harness resume locator.
2. **Live terminal** — optional runtime identity owned by a host backend.
3. **Harness conversation** — optional durable locator understood by Claude Code
   or Codex.

Opening should follow one policy:

1. Attach when a live terminal exists.
2. Otherwise offer or automatically perform harness-native resume when a valid
   conversation locator exists.
3. Otherwise report that the session has no recoverable runtime rather than
   silently starting a blank conversation.

The host interface only needs operations such as create, attach, detach, list,
resize, send input, stream/capture output, and terminate. A tmux implementation
can validate this seam. Zellij and a custom daemon remain substitutable later
without making either one's vocabulary part of the domain model.

## What this does not decide

- How Claude Code and Codex session IDs and metrics are discovered reliably.
- Whether Sessionary bundles tmux or requires an external installation.
- Reboot persistence policy and whether conversations resume automatically.
- Multi-client write arbitration.
- The exact mechanism used to infer `Working` versus `Needs input`.
