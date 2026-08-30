# Persistence and migrations in Rust and Go

Research date: 2026-08-30

## Question

For the shortlisted Rust/Ratatui and Go/Bubble Tea ecosystems, which local
persistence and migration foundations best support stable Session and Group
identity, durable metadata, forward-only automatic migrations, crash-safe
writes, reconciliation with live tmux Sessions, and preservation of user data
across Homebrew upgrades?

## Executive conclusion

**SQLite is the better persistence boundary than a single JSON, TOML, or other
whole-document file in both Rust and Go.** Sessionary has multiple related,
independently changing records (Sessions, Groups, live-host bindings, Harness
locators and adapter capabilities). SQLite supplies atomic multi-record
transactions, constraints, crash recovery, explicit schema inspection, and
online backup without Sessionary inventing a storage engine. SQLite itself
states that transactions remain atomic and durable across process, OS, and
power failures, subject to the filesystem correctly implementing the sync
operations SQLite uses.
[SQLite transactional guarantees](https://www.sqlite.org/transactional.html)
[SQLite corruption and sync assumptions](https://www.sqlite.org/howtocorrupt.html#_failure_to_sync)

The smallest credible foundations are:

- **Rust:** `rusqlite` with bundled SQLite, plus either a tiny application-owned
  forward migration runner or `rusqlite_migration` if its `PRAGMA user_version`
  ownership constraint is accepted.
- **Go:** `database/sql` with either `modernc.org/sqlite` for cgo-free builds or
  `mattn/go-sqlite3` for the most direct C SQLite binding, plus embedded SQL
  migrations applied by a narrow application-owned runner or Goose.

This research does not select Rust versus Go or a final library. The decisive
Go trade-off is packaging: `modernc.org/sqlite` preserves ordinary pure-Go
cross-builds but carries a generated Go port and a documented exact-version
coupling to `modernc.org/libc`; `mattn/go-sqlite3` embeds upstream SQLite more
directly but requires cgo, a C compiler, and architecture-specific build
toolchains. Rust's `rusqlite` `bundled` feature also compiles upstream SQLite C
code, but Cargo makes that the library's documented default recommendation for
applications controlling their own databases.

On persistence alone, the evidence does not reveal a material Rust
disadvantage that should override the developer's standing tie-breaker in its
favor. If the terminal/integration prototype also leaves Rust and Go
substantially tied, `rusqlite` with bundled SQLite is a sound foundation and
the desire to learn and use Rust may decide the stack. Conversely, that
preference must not outweigh a demonstrated terminal-correctness, reliability,
or distribution disadvantage elsewhere in the map.

## Why a whole-document file is not the smaller system

A whole-document file initially needs only serialization and filesystem APIs.
It is reasonable for immutable configuration or a tiny cache that can be
discarded. It is a poor canonical store for Sessionary's compatibility promise:

- changing a Session, moving it between Groups, and updating its live tmux
  binding should commit together or not at all;
- stable identity and uniqueness need enforceable invariants, not only decode
  checks after loading the entire document;
- concurrent hook/event writers and the foreground TUI need serialization;
- every schema change rewrites and revalidates the complete document;
- crash-safe replacement needs a temporary file, flushed file contents, atomic
  rename, and directory synchronization, with recovery rules for leftovers;
- backups and repair need their own snapshot/version protocol.

SQLite already defines this machinery. It permits many concurrent readers but
only one writer, and explicit transactions allow the application to make a
reconciliation update atomic.
[SQLite transactions](https://www.sqlite.org/lang_transaction.html)

The database should still store opaque structured payloads as JSON columns
where queryability is unnecessary (for example versioned Harness-specific
metadata). That is different from treating one serialized object graph as the
transaction boundary.

## SQLite durability mode

SQLite defaults to a rollback journal and offers WAL as an alternative. WAL
allows readers and a writer to proceed concurrently and usually performs fewer
sync operations, which can suit a TUI reading while hook relays write. It also
creates `-wal` and `-shm` companion files, requires same-host access, needs
checkpointing, and still permits only one writer.
[SQLite WAL](https://www.sqlite.org/wal.html)

WAL is therefore credible but not an automatic requirement. Sessionary's
initial write volume is likely small. Start with the default rollback journal
unless measurement or the hook-writer design demonstrates contention. If WAL
is enabled:

- use a SQLite release containing the 2026 WAL-reset corruption fix (SQLite
  3.51.3+, or an officially documented fixed backport);
- keep the database, WAL, and SHM files together during manual copies;
- set and test an explicit `synchronous` policy rather than inheriting driver
  defaults accidentally;
- handle `SQLITE_BUSY` and bound retry time so persistence cannot freeze the
  TUI;
- checkpoint before producing a file-level diagnostic copy, or use SQLite's
  backup API instead.

SQLite documents the WAL-reset bug as affecting WAL databases with multiple
connections that write or checkpoint concurrently; the fix first shipped in
3.51.3 with backports to selected branches. Bundling/pinning the engine makes
that security-and-durability decision reproducible.
[SQLite WAL reset bug](https://www.sqlite.org/wal.html#wal_reset_bug)

## Migration contract

Sessionary promises forward compatibility, not downgrade migrations. The
application should enforce these rules independently of language or library:

1. Migrations are immutable, ordered, embedded in the executable, and applied
   automatically before normal access.
2. Each migration runs in a transaction. If a migration cannot be
   transactional, it requires an explicit exceptional design review and a
   recovery procedure.
3. Opening a database whose schema version is newer than the executable must
   fail readably without writing. An older binary must never guess how to
   downgrade it.
4. Before applying any pending migration, make a consistent backup through
   SQLite's online backup API or after an exclusive clean close—not by copying
   only the main file of a live WAL database.
5. Never edit a released migration. Add a correcting forward migration.
6. Preserve stable Session and Group IDs in every data transformation; add
   foreign keys and uniqueness constraints that express the domain rules.
7. Record an application identifier and schema/migration history that can be
   inspected during support and recovery.

SQLite reserves `PRAGMA user_version` as an integer for applications and does
nothing with it itself; `PRAGMA application_id` identifies an application file.
`PRAGMA integrity_check` checks low-level structure and constraints, but does
not replace application-level invariant checks.
[SQLite pragmas](https://www.sqlite.org/pragma.html#pragma_user_version)

For Sessionary's strong compatibility posture, a migration-history table with
version, name, checksum, applied timestamp, and application version is more
diagnosable than `user_version` alone. `user_version` remains suitable for a
minimal runner if the application owns it exclusively and keeps immutable
migration definitions in source control.

## Rust foundation

### `rusqlite` with bundled SQLite

`rusqlite` is a synchronous, direct SQLite wrapper. Its `bundled` feature
compiles and links an embedded SQLite amalgamation, avoiding dependence on the
macOS system SQLite version. The project explicitly recommends this mode for
applications that control their own database. Optional features expose the
online backup API, hooks, serialization, and JSON conversion.
[rusqlite README](https://github.com/rusqlite/rusqlite)

This is a good fit for a local single-user TUI:

- a single writer/storage actor can own one connection and keep blocking DB
  calls away from the render/input loop;
- SQL transactions directly protect domain operations;
- the pinned bundled SQLite version makes Intel/ARM behavior and WAL fixes
  consistent;
- the resulting Homebrew artifact still needs no separately installed SQLite
  library.

The cost is native C compilation during release builds. Universal distribution
already requires building Rust for both macOS architectures; each slice must
compile/link the bundled engine and be tested before any `lipo` merge.

### Migration choices

`rusqlite_migration` is the smallest existing companion. It embeds SQL strings
or directories, validates definitions, applies migrations atomically, and can
detect a database newer than the known migration list. It stores only the
current number in `user_version`; its own documentation warns that behavior is
unspecified if any other code changes that field.
[rusqlite_migration](https://github.com/cljoly/rusqlite_migration)
[rusqlite_migration API](https://docs.rs/rusqlite_migration/latest/rusqlite_migration/struct.Migrations.html)

That is acceptable only if Sessionary declares exclusive ownership of
`user_version`. It is less suitable if support diagnostics need checksums and
application-version provenance.

`refinery` embeds SQL migrations, records version/name/checksum/applied time in
a history table, detects divergent or missing migrations, and runs each
migration transactionally by default. It implements forward-only rollback by
adding a new migration, matching Sessionary's policy. It is more machinery and
supports many databases Sessionary does not need.
[Refinery](https://github.com/rust-db/refinery)

A small application-owned runner over `rusqlite` is also credible: create one
history table, embed ordered SQL files with `include_str!`, verify immutable
checksums, and apply each pending file plus history row in one transaction.
This minimizes dependencies but makes migration correctness Sessionary's code
to test. It should be chosen only if that implementation remains genuinely
smaller than adopting Refinery.

## Go foundation

### Driver choice

Go's `database/sql` supplies the common connection/transaction boundary, but
the driver determines packaging.

`modernc.org/sqlite` is a cgo-free port of SQLite registered as a
`database/sql` driver. It preserves normal Go cross-compilation for
`darwin/arm64` and `darwin/amd64` and avoids requiring a C toolchain in release
jobs. Its documentation calls out a fragile dependency: applications should
pin exactly the `modernc.org/libc` version used by the driver. The transpiled
SQLite sources are generated in a separate project, adding supply-chain and
upgrade surface compared with compiling the upstream amalgamation directly.
[modernc.org/sqlite package](https://pkg.go.dev/modernc.org/sqlite)

`mattn/go-sqlite3` wraps SQLite through cgo and conforms to `database/sql`. It
requires `CGO_ENABLED=1` and GCC; cross-compilation may require setting a cross
C compiler. The project embeds an SQLite binding by default and can instead
link a system library. This gives a direct, mature binding at the cost of
complicating the otherwise simple two-architecture Go release pipeline.
[mattn/go-sqlite3](https://github.com/mattn/go-sqlite3)
[go-sqlite3 compilation](https://github.com/mattn/go-sqlite3/blob/master/README.md#compilation)

Neither option changes the on-disk SQLite format. A driver can be replaced
later behind storage tests, but WAL version/compile options and connection DSN
semantics must be treated as part of the migration test matrix.

### Migration choices

Goose works as a library, supports SQLite, embeds SQL migrations through
Go's `embed.FS`, and runs migrations in transactions by default. It supports
explicit non-transactional migrations, which Sessionary should reject by
policy. Goose is multi-database and feature-rich, so it is broader than the
product needs, but its embedded library use avoids shipping a second CLI.
[Goose](https://github.com/pressly/goose)

`golang-migrate` is another mature embedded/CLI option. It tracks a schema
version plus a dirty flag and refuses further migrations when dirty until an
operator investigates and forces a version. That behavior is useful for
servers but creates an undesirable manual-repair path for an automatically
upgrading desktop tool unless Sessionary wraps it with backup/restore UX.
[golang-migrate](https://github.com/golang-migrate/migrate)
[golang-migrate dirty state](https://github.com/golang-migrate/migrate/blob/master/GETTING_STARTED.md#forcing-your-database-version)

As in Rust, a narrow application-owned runner is credible. Go's `embed`
package can compile ordered `.sql` files into the binary; a history table and
`database/sql` transaction require little code. Goose is preferable if its
tested parsing/history behavior is smaller than maintaining those pieces.

## Reconciliation with live tmux Sessions

Persistence must not claim ownership of process truth. Reconciliation should
read a tmux snapshot, then commit one database transaction that classifies
bindings without deleting user meaning:

- a matching live-host ID refreshes runtime metadata;
- a stored Session with no live tmux target retains its stable Sessionary
  identity and Harness resume locator;
- an unrecognized tmux Session is a discovery/import candidate, not an
  automatically invented Session;
- a live-host identifier is not a Session primary key and can change after
  Harness resume;
- reconciliation records observed time/source so a stale scan cannot overwrite
  newer hook data.

This design works identically through `rusqlite` and `database/sql`. It favors
SQLite over a document because uniqueness, foreign keys, and all-or-nothing
reconciliation are native operations.

## Upgrade, backup, and recovery behavior

Homebrew upgrades replace the executable/formula contents, not the user's data
directory. Sessionary must place the database under the platform-appropriate
user application-data directory, never under the Homebrew prefix. The binary
should:

1. acquire a single migration/startup lock;
2. open read-only first to inspect application/schema version;
3. refuse a newer schema without modification;
4. create a consistent timestamped pre-migration backup;
5. migrate transactionally;
6. run `foreign_key_check` plus targeted domain invariant queries (and reserve
   full `integrity_check` for diagnostics or selected upgrades);
7. retain enough prior backups to recover from semantic migration bugs, with a
   documented retention limit.

An automatic restore should happen only when Sessionary can prove migration
failure and no post-migration writes occurred. Otherwise preserve both files
and present a recovery path; silent replacement risks discarding valid newer
data.

## Required compatibility tests

Run the same black-box storage suite against whichever language/driver is
selected:

- open and migrate a golden database fixture from every public release;
- verify IDs, names, Group membership, lifecycle, Harness locator, and opaque
  adapter metadata after each upgrade path;
- interrupt each migration at injected statement/commit boundaries and verify
  old-or-new state, never a partial schema;
- reject a database from a future schema without changing its bytes;
- test disk-full, permission-denied, corrupt-page, `SQLITE_BUSY`, and stale
  WAL/SHM recovery behavior;
- reconcile identical, missing, replaced, and foreign tmux targets
  idempotently;
- build and execute the suite against both Intel and ARM release artifacts;
- test backup restoration and re-upgrade, not merely backup creation.

Library-level in-memory tests are insufficient for crash safety. Use temporary
on-disk databases and subprocess kill points for the durability suite.

## Concrete choices left for the stack decision

This research narrows, but deliberately does not settle, these choices:

- whether the workload warrants WAL or the default rollback journal;
- `user_version` simplicity versus a checksummed migration-history table;
- `rusqlite_migration`, Refinery, or an application-owned Rust runner;
- `modernc.org/sqlite` pure-Go packaging versus `mattn/go-sqlite3` direct C
  binding;
- Goose versus an application-owned Go runner;
- backup timing/retention and the user-visible recovery workflow.

The persistence prototype should compare the smallest Rust and Go combinations
using the same fixtures and failure cases. Driver benchmarks are not important
for this data volume; release reproducibility and migration/recovery evidence
are.

## Primary sources

- [SQLite transactional guarantees](https://www.sqlite.org/transactional.html)
- [SQLite transactions](https://www.sqlite.org/lang_transaction.html)
- [SQLite WAL](https://www.sqlite.org/wal.html)
- [SQLite pragmas](https://www.sqlite.org/pragma.html)
- [SQLite corruption and sync assumptions](https://www.sqlite.org/howtocorrupt.html)
- [rusqlite](https://github.com/rusqlite/rusqlite)
- [rusqlite_migration](https://github.com/cljoly/rusqlite_migration)
- [Refinery](https://github.com/rust-db/refinery)
- [modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite)
- [mattn/go-sqlite3](https://github.com/mattn/go-sqlite3)
- [Goose](https://github.com/pressly/goose)
- [golang-migrate](https://github.com/golang-migrate/migrate)
