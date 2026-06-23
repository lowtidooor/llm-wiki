# LLM-Wiki

LLM-Wiki is a Markdown-first, Obsidian-compatible knowledge vault for agent-maintained notes over user-owned raw material.

## Inspiration

This repository is a custom implementation of the LLM Wiki pattern described in Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), with its own schema, scripts, and operating rules.

## Vault Model

LLM-Wiki stores raw source material separately from the agent-maintained wiki built from it:

```text
raw/                 Original source files; agents read existing files and may create new Markdown files only on explicit request
wiki/sources/        One provenance and evidence note per raw asset
wiki/knowledge/      Reusable topic synthesis across sources
wiki/entities/       Current state and timeline for people, projects, or objects
```

The important boundary is that `raw/` remains the source of truth, while `wiki/` is a reviewed synthesis layer.

## Project Files

The content folders are described in the vault model above. Supporting project files:

```text
wiki/templates/              Note templates for manual edits
wiki/index.md                Generated human-readable index
wiki/catalog.jsonl           Generated machine-readable catalog
scripts/                     Reindexing, search, validation, and tests
AGENTS.md                    Agent operating rules
```

## Usage

1. Add Markdown source material under `raw/`.
   Example: `raw/book-notes.md`

2. Ask an agent to ingest one source.
   - `ingest`: ingest the single new or modified raw Markdown file; ask which file to use if there are multiple.
   - `ingest raw/book-notes.md`: ingest a specific raw file.
   - `ingest raw/book-notes.md ch. 2`: ingest only chapter 2; default raw scope is the full file.

3. Review the result.
   The agent updates `wiki/`, runs `scripts/reindex` and `scripts/check`, and reports whether validation passed.

4. Commit manually after review.

5. Ask questions about vault contents in plain language.
   Example: `How does the new CQRS implementation differ from the old ones?`
   The agent answers from the wiki without editing it.

6. Keep useful answers as new source material.
   Ask the agent to create a new raw Markdown source under `raw/`, then run `ingest`.

7. Periodically run `lint` for wiki maintenance.
   It may perform allowed safe changes and report findings; merge/split/delete/archive/supersede actions, broad cleanup, and structural rewrites require explicit approval.

## Operating Rules

- Agents never modify existing `raw/` files; they may create new raw Markdown sources only when explicitly requested.
- Users review `wiki/` changes before committing.
- `wiki/index.md` and `wiki/catalog.jsonl` are generated caches, not source of truth.
- The project does not use `wiki/log.md` or automatic Git operations.

## Note Metadata

Wiki notes use YAML frontmatter so agents and scripts can validate, index, and retrieve them consistently. Supported roles are `source`, `knowledge`, and `entity`.

Use the templates in `wiki/templates/` when creating notes manually. After manual note edits, ask the agent to reindex and check the vault.

Raw Markdown files do not require frontmatter. If a raw source already has YAML frontmatter, the agent may use it as ingest context, but existing `raw/` files remain user-owned and immutable.

## Troubleshooting

- Failed or stale check: fix the reported issue, run `scripts/reindex`, then run `scripts/check` again.
- Duplicate candidates: review titles, aliases, raw mappings, and source type warnings before merging or splitting notes.
- Missing provenance: ensure each source links to its raw asset, and each updated knowledge or entity note links to supporting source notes.
