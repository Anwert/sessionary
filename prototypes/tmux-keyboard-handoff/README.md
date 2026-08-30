# Throwaway prototype: tmux keyboard handoff

This prototype answers one question: can a Ratatui or Bubble Tea process provide
the same transient Session Board in front of an unmodified Harness TUI, then
return cleanly to it while tmux continues owning the Harness process?

It is deliberately not production code. Both implementations use the same tmux
topology and key contract:

- tmux window `harness` owns the native Harness TUI.
- tmux window `board` runs the selected prototype.
- `Ctrl-\` is a tmux root-table binding that switches from the Harness to the
  board before the Harness sees the key.
- `Enter` or `Esc` in the board switches back to the Harness.
- `q` in the board detaches the client. The tmux session and Harness stay alive.

## Run

Requirements: tmux plus either Rust/Cargo or Go. From this directory:

```sh
./run.sh rust codex
./run.sh go codex
```

Replace `codex` with `claude`, or with `mock` for a credential-free smoke test.
Each invocation uses an isolated tmux socket and prints its session/socket names
before attaching. After detaching with `q`, reattach with the printed command to
verify that the Harness remained alive. Remove it afterward with the printed
cleanup command.

The launcher compiles the chosen board, starts the Harness directly (no PTY
emulation and no output inspection), and installs only a tmux key-table binding.
It does not screen-scrape or interpret Harness output.

## Guided checks

Run the same sequence once for each implementation:

1. Type into the native Harness and confirm ordinary editing works.
2. Press `Ctrl-\`; confirm the board appears and its state names the active
   Harness window.
3. Press `Enter`; confirm focus returns and the partially typed Harness input is
   intact.
4. Repeat with `Esc`.
5. Resize the terminal while the board is open; confirm its displayed dimensions
   update and the UI remains usable.
6. Open the board, press `q`, then run the printed reattach command; confirm the
   same Harness process and conversation are still present.
7. Kill only the board window with `Ctrl-b &`; press `Ctrl-\` in the Harness and
   observe the explicit tmux failure rather than damage to the Harness window.

Record anything behaviorally different between the Rust and Go runs, including
build time, resize artifacts, key leakage, terminal restoration, and recovery.

## Expected architectural finding

The global key is owned by tmux, not by Ratatui or Bubble Tea. Consequently the
frameworks receive identical board-local events and neither framework needs to
proxy, emulate, or scrape the native Harness TUI. The spike is meant to validate
that claim on a real terminal and reveal framework-specific correctness issues.
