# Evidence captured before human evaluation

Environment: macOS arm64, tmux 3.7b, Rust 1.98.0, Go 1.26.5.

## Automated smoke result

Both implementations compiled successfully. Each was then run in a fresh,
isolated tmux server with a shell standing in for the Harness. For both stacks:

- the board pane was alive before handoff;
- sending `Enter` to the board selected the Harness window;
- the board pane remained alive for the next invocation;
- the Harness pane remained alive;
- no Harness output was read or interpreted.

The Rust launcher was additionally exercised through a real attached tmux client:
`Ctrl-\` opened the board, `Enter` returned to the same mock Harness process,
`Ctrl-\` reopened the board, and `q` detached the client. After detachment, tmux
still reported the original Harness pane and PID alive.

## Concrete implementation differences

| Dimension | Rust / Ratatui | Go / Bubble Tea |
| --- | --- | --- |
| Board source | 82 lines | 66 lines |
| Event model | Explicit poll/read/draw loop with Crossterm | Framework `Init`/`Update`/`View` loop |
| Terminal lifecycle | Explicit `ratatui::init()` and `restore()` | `WithAltScreen()` managed by Bubble Tea |
| tmux handoff | Synchronous command with explicit status check | A Bubble Tea command returning the process result as a message |
| Dependencies | Ratatui plus direct Crossterm dependency | Bubble Tea (transitive terminal/rendering packages) |

These are observations, not a stack verdict. The guided real-Harness checks in
the README must establish whether either difference produces visible key loss,
resize artifacts, terminal corruption, or worse failure recovery.
