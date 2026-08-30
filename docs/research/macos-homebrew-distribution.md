# macOS packaging and Homebrew distribution constraints

Research for [Research macOS packaging and Homebrew distribution constraints](https://github.com/Anwert/sessionary/issues/16), based on primary documentation retrieved 2026-08-30.

## Answer

Sessionary should initially ship as a **Homebrew formula in a project-owned tap**, with `tmux` as a declared runtime dependency. A formula matches a terminal-first executable; a cask is the appropriate Homebrew vehicle when the primary artifact is a native macOS `.app` or proprietary/platform-specific binary. A tap provides the intended one-command installation immediately (`brew install Anwert/tap/sessionary`) without waiting for acceptance into `homebrew/core`; installed taps participate in normal `brew update`/`brew upgrade` behavior. Homebrew explicitly recommends direct, fully-qualified installation from a tap and can generate GitHub Actions workflows that test and publish bottles.[^tap][^acceptable]

This distribution choice does **not** materially constrain the implementation language. The important constraints are a reproducible non-interactive release build, immutable versioned sources/artifacts with SHA-256 checksums, no in-app self-updater, and release outputs for both Apple Silicon and Intel. Go and Rust both officially support `darwin/arm64` and `darwin/amd64`/`x86_64-apple-darwin`; neither has a decisive packaging advantage at this level.[^go-targets][^rust-targets]

## Formula versus cask

- Use a formula while Sessionary is a CLI/TUI executable. Homebrew says native `.app` bundles belong in casks and that a formula should primarily provide a command-line or library component.[^acceptable]
- Declare `depends_on "tmux"`. Homebrew installs declared formula dependencies and puts declared build dependencies on the isolated build `PATH`; relying on a user's undeclared `PATH` is specifically unsupported.[^formula]
- Mark the formula macOS-only initially (`depends_on :macos`, optionally with a minimum version). This does not prevent later `on_linux` packaging; Homebrew's formula DSL has explicit OS- and architecture-specific blocks.[^formula]
- Do not add Sessionary self-update behavior. Homebrew says self-updating software conflicts with its version and upgrade management; upgrades should arrive as new formula versions.[^acceptable]
- A cask only becomes attractive if Sessionary later ships a primary `.app`, DMG, or installer. Cask upgrades can uninstall/reinstall or replace in place, and unsigned accessibility-enabled apps require permissions to be re-enabled after every update, which is undesirable for a keyboard/terminal tool.[^cask][^faq]

## Architectures and release artifacts

Homebrew bottles are versioned, per-platform binary packages selected automatically for the user's system. Their metadata distinguishes OS/architecture, and Homebrew's tap template can build bottles in GitHub Actions.[^bottles][^tap] Therefore:

1. Treat Apple Silicon as required and Intel as required when the selected toolchain and dependencies continue to support it.
2. Prefer separate native arm64 and x86_64 release artifacts/bottles over a universal Mach-O. A universal binary is optional convenience for a direct-download channel, not a Homebrew requirement.
3. Run release smoke tests natively on both architectures. GitHub currently documents standard hosted macOS runner labels for both arm64 and Intel, so this does not require self-hosted hardware.[^runners]
4. Pin the minimum macOS deployment target deliberately and test it. Rust, for example, exposes this through `MACOSX_DEPLOYMENT_TARGET`; its two Darwin targets have different documented minimum OS versions.[^rust-targets]

Go officially lists `darwin/amd64` and `darwin/arm64` as valid targets. Rust distributes both Apple Darwin targets, though it classifies arm64 as Tier 1 and x86_64 as Tier 2. Native dependencies can make cross-compilation harder in either ecosystem, so successful compilation alone is not a substitute for native tests.[^go-targets][^rust-targets]

## Signing and notarization

For software distributed directly outside the Mac App Store, Apple's recommended trust path is Developer ID signing, hardened runtime, a secure timestamp, notarization, and stapling the returned ticket. Developer ID requires Apple Developer Program membership. Apple's command-line `notarytool` supports scripted CI submission of ZIP, PKG, and DMG artifacts.[^developer-id][^notarization]

This creates two sensible stages:

- **MVP Homebrew formula:** signing/notarization need not block the first tap release if Homebrew builds/installs the formula and the shipped product remains a terminal executable. Validate actual Gatekeeper behavior on a clean Mac before release; do not claim a polished direct-download installation yet.
- **Direct downloads or `.app` distribution:** sign and notarize every executable in the archive. This should be automated and treated as required for the promised easy-install experience, not left to users to bypass Gatekeeper.

Signing is thus a distribution-channel concern, not a reason to select an Apple-only implementation stack. App Sandbox is optional for Developer ID distribution outside the App Store; hardened runtime is part of Apple's notarization preparation.[^notarization]

## Release and upgrade design

A low-maintenance release pipeline is:

1. Create an immutable stable tag and GitHub release; produce checksummed arm64 and Intel artifacts, or reproducibly build them through the formula.
2. Test install, launch, `tmux` dependency resolution, upgrade, and persisted-data migration on both architectures.
3. Update the tap formula URL/version/checksum and publish architecture bottles. `brew tap-new` supplies test and `brew pr-pull` workflows; Homebrew documents pinning the reviewed head SHA when publishing bottles.[^tap][^testbot]
4. Let `brew update` refresh tap metadata and `brew upgrade sessionary` install the new version. Avoid an internal updater.[^tap][^acceptable]
5. Consider `homebrew/core` only after stable releases, user interest, and cross-platform/build-matrix expectations justify its added acceptance and maintenance burden. Core requires stable immutable releases, verifiable sources, source builds or platform-independent output, and its supported CI matrix.[^acceptable]

## Preserving user data across upgrades

Never store the Sessionary database or user-owned configuration inside the versioned Homebrew Cellar keg. Homebrew removes old formula versions during upgrades and periodic cleanup. Homebrew's formula guidance explicitly places persistent mutable data under `var` and persistent configuration under `etc`; Sessionary may instead use the normal per-user macOS application-support/configuration location, which is independent of the Homebrew prefix.[^persistent][^faq]

Packaging cannot supply application-level backward compatibility. Sessionary must:

- keep a versioned data schema and run forward migrations transactionally before opening the new version;
- back up or otherwise preserve the pre-migration store until the migration succeeds;
- never let formula `post_install` own schema migration, because it lacks the user's live application context and must not make user data dependent on Homebrew's keg lifecycle;
- test upgrades from every supported public schema/version, including upgrade with active tmux sessions;
- keep uninstall distinct from deleting user data. A future cask should only delete user data in an explicit `--zap` path; Homebrew says `zap` is never performed by default.[^cask]

## Consequences for stack selection

Packaging provides a filter, not a winner. Reject a stack only if it cannot reliably produce reproducible macOS arm64 and Intel binaries, requires a large or fragile undeclared runtime, makes native testing impractical, or couples persistent data to its installation directory. Compare the remaining stacks on Sessionary's harder needs—terminal process control, Harness event integration, conceptual integrity, and durable migrations—rather than on Homebrew support, which is viable across credible compiled ecosystems.

## Decision-ready recommendation

Adopt a project-owned Homebrew tap and formula as the MVP channel; declare `tmux`; publish/test native Apple Silicon and Intel bottles; keep data outside the keg with application-owned forward migrations; omit self-update; and defer mandatory Developer ID signing/notarization only while Homebrew is the sole supported channel. Record signing/notarization as a release requirement before advertising direct downloads or shipping an app bundle.

[^tap]: [Homebrew, “How to Create and Maintain a Tap”](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap)
[^acceptable]: [Homebrew, “Acceptable Formulae”](https://docs.brew.sh/Acceptable-Formulae)
[^formula]: [Homebrew, “Formula Cookbook”](https://docs.brew.sh/Formula-Cookbook)
[^cask]: [Homebrew, “Cask Cookbook”](https://docs.brew.sh/Cask-Cookbook)
[^faq]: [Homebrew, “FAQ”](https://docs.brew.sh/FAQ)
[^bottles]: [Homebrew, “Bottles (Binary Packages)”](https://docs.brew.sh/Bottles)
[^testbot]: [Homebrew, “BrewTestBot”](https://docs.brew.sh/BrewTestBot)
[^go-targets]: [The Go Project, “Installing Go from source,” supported operating systems and architectures](https://go.dev/doc/install/source#environment)
[^rust-targets]: [The Rust Project, “`*-apple-darwin` platform support”](https://doc.rust-lang.org/rustc/platform-support/apple-darwin.html)
[^runners]: [GitHub Docs, “Choosing the runner for a job”](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
[^developer-id]: [Apple Developer, “Developer ID”](https://developer.apple.com/support/developer-id/)
[^notarization]: [Apple Developer Documentation, “Notarizing macOS software before distribution”](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
[^persistent]: [Homebrew, “Formula Cookbook: Handling files that should persist over formula upgrades”](https://docs.brew.sh/Formula-Cookbook#handling-files-that-should-persist-over-formula-upgrades)
