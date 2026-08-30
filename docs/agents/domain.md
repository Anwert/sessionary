# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists: it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure

This is a single-context repository:

```text
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-example-decision.md
│   └── 0002-another-decision.md
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, or a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, reconsider whether you're inventing language the project doesn't use or note the real gap for `/domain-modeling`.

## Keep canonical domain docs on main

`CONTEXT.md` and `docs/adr/` are shared sources of truth. Apply resolved domain-language and architecture-decision changes against the latest `origin/main` and push them to `main` promptly. If the current checkout is a research, prototype, or other working branch, use a temporary worktree based on `origin/main`; keep the artifact branch focused on its artifact, then sync it from `main` when needed.

Before editing, fetch `origin/main`. Before pushing, incorporate any newer `main` change and resolve overlapping edits from their primary decisions. Completion means the canonical files are present on `origin/main`, not merely committed on the current working branch.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
