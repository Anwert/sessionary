#!/usr/bin/env python3
"""THROWAWAY PROTOTYPE: frequency-ranked Sessionary keyboard navigation."""

from __future__ import annotations

import os
import select
import shutil
import sys
import termios
import tty


SESSIONS = [
    ["Fix OAuth callback", "Release 2.4", "Working", False, "Claude Code", 68, "web-api", "fix/oauth-callback"],
    ["Investigate billing retry", "Release 2.4", "Idle", True, "Codex", 41, "billing", "investigate/retries"],
    ["Draft release changelog", "Release 2.4", "Finished", False, "Claude Code", 82, "web-api", "release/2.4"],
    ["Verify schema migration", "Release 2.4", "Working", False, "Codex", 56, "billing", "release/schema-v12"],
    ["Run release smoke suite", "Release 2.4", "Working", False, "Claude Code", 37, "web-app", "release/2.4"],
    ["Retire rollout flags", "Release 2.4", "Idle", True, "Codex", 48, "web-api", "release/remove-flags"],
    ["Prepare support notes", "Release 2.4", "Finished", False, "Claude Code", 26, "support", "release/2.4-notes"],
    ["Refresh onboarding docs", "Website refresh", "Finished", False, "Claude Code", 87, "website", "docs/onboarding"],
    ["Trace startup regression", "Website refresh", "Idle", True, "Claude Code", 76, "website", "perf/startup"],
    ["Polish homepage hero", "Website refresh", "Idle", False, "Codex", 35, "website", "design/hero"],
    ["Audit legacy redirects", "Website refresh", "Working", False, "Claude Code", 49, "website", "seo/redirect-audit"],
    ["Reconcile duplicate invoices", "Billing incidents", "Idle", True, "Codex", 63, "billing", "incident/duplicate-invoices"],
    ["Replay failed webhooks", "Billing incidents", "Working", False, "Claude Code", 72, "billing", "incident/webhooks"],
    ["Check tax rounding drift", "Billing incidents", "Idle", False, "Codex", 28, "ledger", "investigate/tax-rounding"],
    ["Write incident timeline", "Billing incidents", "Finished", False, "Claude Code", 91, "ops", "postmortem/billing"],
    ["Prototype fuzzy search", "Sessionary MVP", "Idle", False, "Codex", 23, "sessionary", "prototype/search"],
    ["Spike tmux attachment", "Sessionary MVP", "Idle", True, "Claude Code", 59, "sessionary", "spike/tmux"],
    ["Model session states", "Sessionary MVP", "Working", False, "Codex", 44, "sessionary", "model/session-state"],
    ["Expand fake session fixtures", "Sessionary MVP", "Finished", False, "Claude Code", 31, "sessionary", "prototype/fixtures"],
    ["Evaluate analytics SDK", "Analytics rollout", "Idle", True, "Codex", 67, "web-app", "spike/analytics-sdk"],
    ["Define product events", "Analytics rollout", "Idle", False, "Claude Code", 38, "web-app", "analytics/event-schema"],
    ["Validate KPI dashboard", "Analytics rollout", "Finished", False, "Codex", 79, "analytics", "dashboard/kpi-review"],
    ["Review consent behavior", "Analytics rollout", "Working", False, "Claude Code", 52, "web-app", "privacy/consent"],
    ["Triage checkout test flakes", "Maintenance", "Idle", True, "Codex", 33, "web-app", "test/checkout-flakes"],
    ["Update terminal dependencies", "Maintenance", "Idle", False, "Claude Code", 47, "sessionary", "chore/dependencies"],
    ["Reduce noisy API logs", "Maintenance", "Working", False, "Codex", 61, "web-api", "chore/log-volume"],
    ["Rotate staging secrets", "Maintenance", "Finished", False, "Claude Code", 18, "ops", "ops/secret-rotation"],
]

GROUPS = list(dict.fromkeys(session[1] for session in SESSIONS)) + [""]
state = {"selected": 0, "view": "all", "screen": "board", "help": False, "toast": "", "last_key": ""}


def color(code: int, text: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m"


def label(session: list) -> str:
    if session[3]:
        return "Idle · Needs input"
    return session[2]


def visible_indices() -> list[int]:
    if state["view"] == "input":
        return [i for i, session in enumerate(SESSIONS) if session[2] != "Archived" and session[3]]
    if state["view"] == "archive":
        return [i for i, session in enumerate(SESSIONS) if session[2] == "Archived"]
    return [i for i, session in enumerate(SESSIONS) if session[2] != "Archived"]


def ensure_selection() -> None:
    visible = visible_indices()
    if visible and state["selected"] not in visible:
        state["selected"] = visible[0]


def fit(text: str, width: int) -> str:
    return (text[: max(0, width - 1)] + "…") if len(text) > width else text.ljust(width)


def board_lines(width: int) -> tuple[list[str], int]:
    visible = visible_indices()
    columns = max(1, min(4, width // 28))
    gap = 2
    card_width = max(20, (width - gap * (columns - 1)) // columns)
    lines: list[str] = []
    selected_line = 0
    for group in GROUPS:
        items = [i for i in visible if SESSIONS[i][1] == group]
        if not items and state["view"] != "all":
            continue
        lines.append(color(36, f" {group or 'Ungrouped'} ".upper()) + color(90, f" {len(items)} Sessions"))
        if not items:
            lines.append(color(90, "  Empty Group · n creates its first Session"))
            lines.append("")
            continue
        for start in range(0, len(items), columns):
            row = items[start : start + columns]
            rendered = [[], [], []]
            for index in row:
                session = SESSIONS[index]
                selected = index == state["selected"]
                mark = "▶" if selected else " "
                attention = "●" if session[3] else "○"
                rendered[0].append(fit(f"{mark} {attention} {session[0]}", card_width))
                rendered[1].append(fit(f"  {session[4]} · {label(session)}", card_width))
                rendered[2].append(fit(f"  {session[6]} · ctx {session[5]}%", card_width))
                if selected:
                    selected_line = len(lines)
            for rendered_line in rendered:
                lines.append((" " * gap).join(rendered_line))
            lines.append("")
    return lines, selected_line


def render_board(width: int, height: int) -> str:
    ensure_selection()
    visible = visible_indices()
    need_input = sum(1 for session in SESSIONS if session[2] != "Archived" and session[3])
    view_name = {"all": "ALL", "input": "NEEDS INPUT", "archive": "ARCHIVE"}[state["view"]]
    header = color(1, "SESSIONARY") + f"  {view_name} · showing {len(visible)} of {len(SESSIONS)} Sessions · " + color(33, f"{need_input} need input")
    footer = "←↑↓→ select · Shift+arrows move Session · Ctrl+↑/↓ order Group · Enter focus · n new · d archive · ? help · q quit"
    lines, selected_line = board_lines(width)
    available = max(3, height - 4)
    start = max(0, min(max(0, len(lines) - available), selected_line - available // 2))
    body = lines[start : start + available]
    while len(body) < available:
        body.append("")
    status = state["toast"] or f"received: {state['last_key'] or '—'}"
    return "\n".join([header, color(90, "─" * min(width, 120)), *body, color(90, fit(status, width)), fit(footer, width)])


def render_harness(width: int, height: int) -> str:
    session = SESSIONS[state["selected"]]
    lines = [
        color(90, f"{session[1]} / {session[0]} · {session[4]} · context {session[5]}%"),
        "",
        color(32, "assistant ›") + " Native Harness placeholder: input belongs to the Harness here.",
        "",
        color(32, "you ›") + " ▉",
    ]
    lines += [""] * max(0, height - len(lines) - 2)
    lines.append(color(33, "Ctrl+Space") + " open Session board · this replacement for F2 is provisional")
    lines.append(color(90, f"last terminal event: {state['last_key'] or '—'}"))
    return "\n".join(fit(line, width) if "\x1b" not in line else line for line in lines)


def render_help(width: int, height: int) -> str:
    help_lines = [
        color(1, "KEYBOARD MAP — press ? to return"),
        "",
        "VERY HIGH  Ctrl+Space   Harness ↔ board (candidate replacing rejected F2)",
        "VERY HIGH  arrows       select Session spatially",
        "VERY HIGH  Enter        focus native Harness",
        "HIGH       1 / 2        All / Needs input",
        "MEDIUM     n / d        new Session / archive selected Session",
        "LOW        3 / r        Archive view / restore",
        "LOW        Shift+arrows move Session spatially",
        "LOW        Ctrl+↑/↓     reorder current Group",
        "",
        "This standalone raw-terminal prototype decodes xterm modifier sequences itself.",
        "The footer exposes the last event received, so missing Shift/Ctrl information is evidence",
        "about the terminal configuration rather than a browser conflict.",
    ]
    return "\n".join(fit(line, width) if "\x1b" not in line else line for line in help_lines[:height])


def draw() -> None:
    width, height = shutil.get_terminal_size((120, 36))
    if state["help"]:
        content = render_help(width, height)
    elif state["screen"] == "harness":
        content = render_harness(width, height)
    else:
        content = render_board(width, height)
    sys.stdout.write("\x1b[H\x1b[2J" + content)
    sys.stdout.flush()


SEQUENCES = {
    b"\x1b[A": "up", b"\x1b[B": "down", b"\x1b[C": "right", b"\x1b[D": "left",
    b"\x1b[1;2A": "shift-up", b"\x1b[1;2B": "shift-down", b"\x1b[1;2C": "shift-right", b"\x1b[1;2D": "shift-left",
    b"\x1b[1;5A": "ctrl-up", b"\x1b[1;5B": "ctrl-down", b"\x1b[1;5C": "ctrl-right", b"\x1b[1;5D": "ctrl-left",
}


def read_key(fd: int) -> str:
    data = os.read(fd, 1)
    if data == b"\x1b":
        while select.select([fd], [], [], 0.025)[0]:
            data += os.read(fd, 1)
    if data in SEQUENCES:
        return SEQUENCES[data]
    if data in (b"\r", b"\n"):
        return "enter"
    if data == b"\x00":
        return "ctrl-space"
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return repr(data)


def prompt_line(fd: int, original: list, prompt: str, default: str = "") -> str:
    termios.tcsetattr(fd, termios.TCSADRAIN, original)
    sys.stdout.write("\x1b[?25h\x1b[H\x1b[2J" + prompt)
    sys.stdout.flush()
    try:
        value = input()
    finally:
        tty.setraw(fd)
        sys.stdout.write("\x1b[?25l")
    return value.strip() or default


def navigate(direction: str) -> None:
    visible = visible_indices()
    if not visible:
        return
    position = visible.index(state["selected"])
    width = shutil.get_terminal_size((120, 36)).columns
    columns = max(1, min(4, width // 28))
    delta = {"left": -1, "right": 1, "up": -columns, "down": columns}[direction]
    state["selected"] = visible[max(0, min(len(visible) - 1, position + delta))]


def move_session(direction: str) -> None:
    selected = state["selected"]
    session = SESSIONS[selected]
    peers = [i for i, candidate in enumerate(SESSIONS) if candidate[1] == session[1] and candidate[2] != "Archived"]
    position = peers.index(selected)
    columns = max(1, min(4, shutil.get_terminal_size((120, 36)).columns // 28))
    delta = {"left": -1, "right": 1, "up": -columns, "down": columns}[direction]
    target_position = position + delta
    if 0 <= target_position < len(peers):
        target = peers[target_position]
        SESSIONS[selected], SESSIONS[target] = SESSIONS[target], SESSIONS[selected]
        state["selected"] = target
        state["toast"] = f"Moved Session {direction}"
        return
    if direction in ("up", "down"):
        group_position = GROUPS.index(session[1])
        next_group = max(0, min(len(GROUPS) - 1, group_position + (1 if direction == "down" else -1)))
        session[1] = GROUPS[next_group]
        state["toast"] = f"Moved Session to {GROUPS[next_group] or 'Ungrouped'}"


def reorder_group(direction: str) -> None:
    group = SESSIONS[state["selected"]][1]
    position = GROUPS.index(group)
    target = max(0, min(len(GROUPS) - 1, position + (1 if direction == "down" else -1)))
    if target != position:
        GROUPS[position], GROUPS[target] = GROUPS[target], GROUPS[position]
        state["toast"] = f"Moved Group {direction}"


def handle(key: str, fd: int, original: list) -> bool:
    state["last_key"] = key
    state["toast"] = ""
    if key == "q" and state["screen"] == "board" and not state["help"]:
        return False
    if key == "?":
        state["help"] = not state["help"]
        return True
    if state["help"]:
        return True
    if key == "ctrl-space":
        state["screen"] = "board" if state["screen"] == "harness" else "harness"
        return True
    if state["screen"] == "harness":
        return True
    if key in ("left", "right", "up", "down"):
        navigate(key)
    elif key.startswith("shift-"):
        move_session(key.removeprefix("shift-"))
    elif key in ("ctrl-up", "ctrl-down"):
        reorder_group(key.removeprefix("ctrl-"))
    elif key == "enter" and visible_indices():
        state["screen"] = "harness"
    elif key in ("1", "2", "3"):
        state["view"] = {"1": "all", "2": "input", "3": "archive"}[key]
        ensure_selection()
    elif key == "n":
        current_group = SESSIONS[state["selected"]][1] if SESSIONS else ""
        name = prompt_line(fd, original, "Session name: ", "New Session")
        SESSIONS.append([name, current_group, "Idle", False, "Codex", 1, "current repository", "current branch"])
        state["selected"] = len(SESSIONS) - 1
        state["view"] = "all"
        state["toast"] = f"Created {name} in {current_group or 'Ungrouped'}"
    elif key == "d" and visible_indices() and state["view"] != "archive":
        session = SESSIONS[state["selected"]]
        session.append(session[2])
        session[2], session[3] = "Archived", False
        state["toast"] = f"Archived {session[0]}"
        ensure_selection()
    elif key == "r" and state["view"] == "archive" and visible_indices():
        session = SESSIONS[state["selected"]]
        session[2] = session[8] if len(session) > 8 else "Finished"
        state["view"] = "all"
        state["toast"] = f"Restored {session[0]}"
    return True


def main() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit("Run this prototype directly in an interactive terminal.")
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    sys.stdout.write("\x1b[?1049h\x1b[?25l")
    tty.setraw(fd)
    try:
        running = True
        while running:
            draw()
            running = handle(read_key(fd), fd, original)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
