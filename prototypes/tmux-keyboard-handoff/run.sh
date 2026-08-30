#!/bin/sh
set -eu

stack=${1:-}
harness=${2:-mock}

case "$stack" in
  rust)
    (cd rust && cargo build)
    board_command="$(pwd)/rust/target/debug/sessionary-handoff-rust"
    ;;
  go)
    (cd go && go build -o sessionary-handoff-go .)
    board_command="$(pwd)/go/sessionary-handoff-go"
    ;;
  *)
    echo "usage: $0 rust|go [codex|claude|mock]" >&2
    exit 2
    ;;
esac

case "$harness" in
  codex|claude)
    command -v "$harness" >/dev/null 2>&1 || {
      echo "$harness is not installed" >&2
      exit 2
    }
    harness_command="$harness"
    ;;
  mock)
    harness_command="sh -c 'printf \"Mock Harness PID %s\\n\" \"\$\$\"; exec sh'"
    ;;
  *)
    echo "harness must be codex, claude, or mock" >&2
    exit 2
    ;;
esac

socket="sessionary-${stack}-$$"
session="handoff-${stack}"

tmux -L "$socket" new-session -d -s "$session" -n harness "$harness_command"
tmux -L "$socket" new-window -d -t "$session:" -n board "$board_command"
tmux -L "$socket" set-option -t "$session" remain-on-exit on
tmux -L "$socket" bind-key -n 'C-\' select-window -t "$session:board"
tmux -L "$socket" select-window -t "$session:harness"

echo "reattach: tmux -L $socket attach-session -t $session"
echo "cleanup:  tmux -L $socket kill-server"
exec tmux -L "$socket" attach-session -t "$session"
