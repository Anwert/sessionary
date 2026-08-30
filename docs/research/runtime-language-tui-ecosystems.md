# Runtime, language, and TUI ecosystems

Research date: 2026-08-30

## Question

Which runtime, language, and TUI ecosystems are credible candidates for
Sessionary's macOS MVP technical foundation, without limiting the search to the
developer's current familiarity?

## Executive conclusion

The credible primary candidates are **Rust with Ratatui/Crossterm** and **Go
with Bubble Tea**. Both can ship as small native executables for Intel and
Apple Silicon Macs, consume tmux and Harness text/event protocols without
screen scraping, isolate platform-specific process code, and support a
testable model-driven TUI. Neither ecosystem has a decisive advantage for
Harness hooks or tmux: those are external structured protocols.

**TypeScript/Node with Ink** remains a credible prototype and product option,
especially for fast UI iteration, but it has a concrete distribution penalty:
PTY support comes from `node-pty`, a native addon tied to Node versions and
requiring Xcode to compile on macOS. A bundled Node application must therefore
solve two-architecture runtime and native-addon packaging, while Rust and Go
produce architecture-specific native executables directly.

**Swift with TermKit** and **.NET with Terminal.Gui** are technically viable
long-list candidates, but neither currently earns a place in the first
implementation comparison. Swift is strongest when embracing Apple-native UI;
its terminal-UI ecosystem is much smaller, and Swift's official cross-platform
support does not mean one macOS build cross-compiles directly to Linux or
Windows. .NET has a rich terminal toolkit and documented single-file/universal
packaging, but brings a substantially larger runtime/toolchain surface without
a Sessionary-specific capability unavailable in Rust or Go.

This research does **not** select Rust or Go. It narrows the next decision to
those two and identifies one discriminating prototype: prove the exact
keyboard handoff between the Sessionary shell and an attached native Harness
TUI, then compare the resulting implementation and terminal tests. That
boundary, not hooks, persistence, or tmux command execution, is where the
remaining technical uncertainty lives.

## Constraints that do not discriminate among languages

### tmux is a documented protocol boundary

tmux control mode is a documented, text-only protocol. It accepts normal tmux
commands, frames responses with `%begin`/`%end` or `%error`, emits asynchronous
notifications, recommends stable session/window/pane IDs, and supports format
subscriptions. Its hooks and user options provide additional structured
integration points. Any candidate able to supervise a subprocess and parse a
line protocol can integrate without scraping tmux's human-facing output.
[tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)
[tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)

This also means Sessionary does not need an in-process PTY library merely to
host sessions: tmux owns their PTYs and lifetime. A PTY library is relevant
only if a later design embeds a tmux client or replaces tmux, neither of which
is required by the current foundation.

### Harness observability is adapter work, not runtime work

Official Harness hooks/events arrive as commands, JSON payloads, or protocol
messages. Rust, Go, TypeScript, Swift, and .NET can all consume them. The
adapter contract should declare capabilities and normalize confirmed activity
to `Working` or `Idle`; anything it cannot classify reliably becomes `Needs
input`. Screen scraping is excluded entirely, including as a fallback.

Consequently, a language should not receive credit for supposedly making
activity classification more accurate. Accuracy depends on the official
events exposed by each Harness and on adapter logic, not on the runtime.

### Local persistence is not a useful first-round discriminator

All shortlisted ecosystems can use SQLite and versioned forward migrations.
Sessionary's backward-compatibility commitment is architectural and procedural:
stable durable identifiers, explicit schema versions, migration fixtures, and
upgrade tests. Choosing a particular language does not provide that discipline
automatically. Database-library selection belongs after the runtime decision.

## Candidate comparison

| Concern | Rust + Ratatui/Crossterm | Go + Bubble Tea | TypeScript/Node + Ink | Swift + TermKit | .NET + Terminal.Gui |
|---|---|---|---|---|---|
| TUI/input model | Explicit renderer plus separate event API; maximum control, more orchestration code | Elm-style `Init`/`Update`/`View`; concise event loop and declarative terminal modes | React renderer and hooks; fastest high-level composition | Conventional widget toolkit; smaller ecosystem | Rich widget toolkit and instance-based app model |
| Keyboard interception | Crossterm exposes key press/repeat/release, modifiers, paste, focus and resize events | Bubble Tea v2 exposes structured press/release events and progressive keyboard enhancements | Ink `useInput` exposes characters and normalized key fields; raw-mode behavior is runtime-managed | Toolkit-specific | Toolkit-specific, broad key-binding surface |
| Native Harness handoff | Must explicitly suspend Sessionary terminal modes and attach tmux | Must explicitly suspend program/renderer and attach tmux | Ink has a documented `suspendTerminal` API for child handoff | Requires validation | Requires validation |
| Terminal tests | Ratatui ships a `TestBackend` for deterministic buffer assertions | Model/update logic is ordinary Go; renderer/input integration still needs PTY-level tests | `ink-testing-library` exposes rendered frames; native handoff still needs PTY-level tests | Tests exist, but no equally mature documented headless contract found | Toolkit has a large testable widget surface; still needs PTY-level integration tests |
| macOS artifacts | Official Tier-1 `aarch64-apple-darwin` and `x86_64-apple-darwin` targets; build both and optionally merge with `lipo` | Official `darwin/arm64` and `darwin/amd64` targets; simple cross-builds, then optionally merge | Node distributes x64/arm64 runtimes, but native addons must match architecture and ABI | Natural macOS toolchain; universal release still requires two slices/merge | Documented self-contained single-file or Native AOT builds per architecture and `lipo` merge |
| Later platforms | Ratatui's default Crossterm backend supports Linux/macOS/Windows | Go supports broad GOOS/GOARCH targets; `creack/pty` itself is Unix-only if later adopted | `node-pty` supports Linux/macOS/Windows (ConPTY on modern Windows) | Swift officially supports macOS/Linux/Windows, but builds are platform-targeted | Terminal.Gui and .NET support Windows/macOS/Linux |
| Main cost | Rust ownership/concurrency and lower-level terminal lifecycle increase implementation effort | Less compile-time modeling power; careful domain types and error boundaries are still needed | Runtime/native-addon packaging and dependency footprint | TUI ecosystem depth and non-Apple portability confidence | Runtime/artifact size and extra platform surface |

## Rust with Ratatui and Crossterm

Ratatui deliberately separates rendering from input. Its backend abstraction
draws cells and manages terminal state; applications obtain input from a
backend library such as Crossterm. Ratatui includes a `TestBackend`, which is a
strong fit for deterministic layout and rendering assertions.
[Ratatui backends](https://ratatui.rs/concepts/backends/)

Crossterm exposes keyboard, mouse, paste, focus, and resize events. It supports
polling or an event stream and requires raw mode for keyboard events. This is
the control Sessionary needs for a keyboard-first shell, but also places
responsibility for correct raw-mode and alternate-screen teardown/recovery on
the application.
[Crossterm events](https://docs.rs/crossterm/latest/crossterm/event/index.html)
[Ratatui alternate screen](https://ratatui.rs/concepts/backends/alternate-screen/)

Rust officially treats both Apple Silicon and Intel macOS targets as Tier 1
with host tools. It also has Tier-1 Linux and Windows targets, so isolating
terminal/process implementations behind internal interfaces does not create a
language-level portability barrier.
[Rust platform support](https://doc.rust-lang.org/rustc/platform-support.html)

The ecosystem's advantage is explicit control and a small native deployment.
Its cost is engineering complexity at exactly the boundary Sessionary must get
right: subprocess lifecycle, cancellation, input ownership, and terminal
restoration. Ratatui does not provide a built-in “give the terminal to this
child and restore me” operation; that flow must be designed and tested.

## Go with Bubble Tea

Bubble Tea uses a model/update/view architecture. Its current v2 API makes
alternate screen, focus reporting, mouse mode, cursor state, and keyboard
enhancements declarative on the returned view. Structured keyboard events
include presses/releases, modifiers, repeat information when supported, and
progressive enhancement negotiation.
[Bubble Tea v2 source/API](https://github.com/charmbracelet/bubbletea/blob/main/tea.go)
[Bubble Tea v2 upgrade guide](https://github.com/charmbracelet/bubbletea/blob/main/UPGRADE_GUIDE_V2.md)

That architecture naturally separates domain transitions from rendering and
therefore makes most keyboard/navigation behavior unit-testable without a real
terminal. The remaining risk is the same as Rust's: proving that focus mode can
stop consuming input, restore terminal modes, attach the live tmux Session,
and then redraw safely after detach.

Go officially supports `darwin/arm64` and `darwin/amd64`, as well as many later
OS/architecture targets. Apple Silicon includes cgo and external linking
support, though a pure-Go dependency graph keeps release builds simplest.
[Go build targets](https://go.dev/doc/install/source#environment)
[Go Apple Silicon support](https://go.dev/doc/go1.16#darwin)

If Sessionary later replaces tmux, `creack/pty` provides a direct Unix PTY API,
but its own description is explicitly Unix-only. Windows would require a
separate ConPTY implementation behind the host abstraction.
[creack/pty](https://github.com/creack/pty)

## TypeScript/Node with Ink

Ink provides React composition, raw input through `useInput`, deterministic
frame tests through `ink-testing-library`, alternate-screen rendering, and a
particularly relevant `suspendTerminal` operation. That operation stops Ink's
input/output, restores terminal modes, runs a child such as an editor, and then
restores Ink and forces a redraw. This makes Ink the strongest documented
high-level handoff API in the candidates.
[Ink README and API](https://github.com/vadimdemedes/ink/blob/master/readme.md)

The drawback is release construction. Node's standard process APIs do not
create a PTY. The usual supported addon, Microsoft's `node-pty`, binds
`forkpty` on Unix and ConPTY on Windows, supports all three target OS families,
and requires Xcode to compile on macOS. Its supported Node version is tied
largely to the version used by VS Code. Even if tmux removes the immediate need
for `node-pty`, distributing a self-contained developer tool still means
bundling or requiring Node; adopting PTY support later introduces native ABI
and per-architecture artifacts.
[node-pty](https://github.com/microsoft/node-pty)

Ink should therefore remain available as a fallback if UI iteration speed or
its terminal suspension behavior proves materially better in a spike. It is
not the default release foundation when “easy to install on a new Mac” and a
small stable artifact are core requirements.

## Long-list candidates

### Swift with TermKit

Swift is officially supported for development and deployment on macOS, several
Linux distributions, and Windows, with Swift Package Manager available across
them. The support matrix also shows an important constraint: toolchains largely
build for their own platform family; macOS tools target Apple platforms rather
than promising direct macOS-to-Windows builds.
[Swift platform support](https://www.swift.org/platform-support/)

TermKit is a real cross-platform terminal widget toolkit and includes a
terminal view, lists, tables, menus, text editors, and tests. Its repository is
nevertheless far smaller and less established than Ratatui, Bubble Tea, Ink,
or Terminal.Gui. Swift earns reconsideration if Sessionary moves toward a
native AppKit menu-bar/window product or needs SwiftTerm's embedded terminal
emulator. Neither condition is part of the current terminal-first MVP.
[TermKit](https://github.com/migueldeicaza/termkit)
[SwiftTerm](https://github.com/migueldeicaza/SwiftTerm)

### .NET with Terminal.Gui

Terminal.Gui is a mature, cross-platform, keyboard-first toolkit with rich
widgets and both inline and full-screen operation. .NET can publish
self-contained single-file or Native AOT binaries for `osx-arm64` and
`osx-x64`; Microsoft's documented universal-binary process builds both and
merges/re-signs them with `lipo`.
[Terminal.Gui](https://github.com/gui-cs/Terminal.Gui)
[.NET macOS deployment](https://learn.microsoft.com/en-us/dotnet/core/deploying/macos)

It is credible, but the richer widget set does not resolve the native Harness
handoff automatically, and its runtime/artifact footprint buys little for the
current UI. Keep it outside the first prototype unless Rust and Go both expose
a concrete blocker.

## Packaging and compatibility consequences

Homebrew does not force a language choice: a formula can install an
architecture-specific binary and depend on `tmux`. For all native candidates,
the safest initial release is two tested macOS artifacts (`arm64` and `x86_64`)
selected by Homebrew. A universal binary is practical by merging slices, but
is not necessary for a good `brew install` experience and doubles the code
payload. “Universal where nearly free; otherwise Apple Silicon required and
Intel best effort” remains compatible with either Rust or Go.

Backward compatibility should be verified independently of packaging:

- migration tests open fixtures from every previously released schema;
- durable Session and Group identities survive upgrades;
- CLI and configuration contracts change only through explicit compatibility
  policy;
- adapters persist source/version/capability metadata so improved event
  support does not silently reinterpret old state.

## Recommended next decision

Carry **Rust/Ratatui/Crossterm** and **Go/Bubble Tea** forward. Do not rank them
abstractly. Build one throwaway, behavior-identical vertical prototype in each
that proves:

1. Sessionary owns global/navigation keys in its shell.
2. Entering Focus detaches the shell renderer/input loop and attaches an
   existing tmux pane running an unmodified interactive program.
3. The focused program receives ordinary keys and terminal resize events
   unchanged.
4. A deliberately reserved escape returns to Sessionary without leaving raw
   mode, cursor, alternate-screen, or resize state corrupted.
5. The flow passes deterministic model tests plus an end-to-end PTY test on
   both Apple Silicon and Intel CI/runners where available.

If both pass, compare the code and tests on conceptual locality, failure
handling, release artifact construction, and maintenance cost. TypeScript/Ink
should enter the prototype only if its documented `suspendTerminal` mechanism
suggests a meaningfully cleaner UX than either native candidate.

## Primary sources

- [tmux control mode](https://github.com/tmux/tmux/wiki/Control-Mode)
- [tmux manual](https://man7.org/linux/man-pages/man1/tmux.1.html)
- [Ratatui backends and test backend](https://ratatui.rs/concepts/backends/)
- [Crossterm events](https://docs.rs/crossterm/latest/crossterm/event/index.html)
- [Rust platform support](https://doc.rust-lang.org/rustc/platform-support.html)
- [Bubble Tea v2 API](https://github.com/charmbracelet/bubbletea/blob/main/tea.go)
- [Go build targets](https://go.dev/doc/install/source#environment)
- [Ink API](https://github.com/vadimdemedes/ink/blob/master/readme.md)
- [node-pty](https://github.com/microsoft/node-pty)
- [Swift platform support](https://www.swift.org/platform-support/)
- [TermKit](https://github.com/migueldeicaza/termkit)
- [Terminal.Gui](https://github.com/gui-cs/Terminal.Gui)
- [.NET macOS deployment](https://learn.microsoft.com/en-us/dotnet/core/deploying/macos)
