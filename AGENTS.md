# LLM-Wiki Agent Rules

All rules apply. Operating boundaries are hard constraints; command rules do not relax them.

## Operating Boundaries

- `raw/` is user-owned source material. Existing assets are immutable: never edit, move, delete, normalize, or annotate them.
- Create a raw source only on explicit user request. It must be Markdown under `raw/`, have a clear title and readable sections, and contain enough provenance to explain the capture. Ask before writing when its target path is existing or unclear.
- Preserve user-provided source content faithfully. Summarize or synthesize it only when the user explicitly requests a summary/capture rather than a verbatim source.
- Maintain only `wiki/`, templates, deterministic scripts, generated retrieval artifacts, and explicitly requested new raw Markdown sources.
- Data model: `raw -> source -> subject`. Roles are `source`, `knowledge`, and `entity`; only `knowledge` and `entity` are subjects.
- Never create `wiki/log.md` or a global log. Do not add database systems, graph database systems, ontologies, embeddings, vector search, semantic indexes, graph retrieval, event systems, controlled vocabularies, privacy/sensitivity metadata, lock files, branch naming, coordination services, custom project skills, or core dependencies on `json-canvas`, `obsidian-cli`, or `defuddle`.
- Do not run automatic Git operations, including Git add, commit, reset, checkout, or destructive Git commands. Only when explicitly asked to commit/amend, use Conventional Commits: `<type>(<scope>): <subject>` or `<type>: <subject>`, with `docs`, `fix`, `feat`, `test`, `chore`, `refactor`, or `revert`.
- Ask before mutating when command intent, scope, source/subject identity, provenance, merge/split/delete/archive decisions, or mutation safety is unclear. Do not guess.

## Note Structure

- Copy the matching template in `wiki/templates/`. `scripts/check` is authoritative for required fields, list types, lifecycle values, valid raw targets, required sections, and source Processing Notes bullets.
- Required metadata: every note has `role`, `topics`, `tags`, `created`, and `updated`; subjects also have `lifecycle` and `aliases`; sources also have `raw`, `source_type`, `origin`, and `processed_scope`. Set timestamps to current ISO 8601 with timezone offset; use YAML lists and `aliases: []` when empty.
- `raw` is exactly one `[[raw/...]]` target; `kind` is optional; `source_type` is free-form; near-duplicates are warnings only. Lifecycle is `active`, `stub`, `superseded`, or `archived`.
- Topics are stable retrieval groups; tags are sparse maintenance/workflow labels.
- Create one source note per raw asset. It links the raw asset and records provenance, scope, evidence anchors, observations, affected notes, conflicts, and Processing Notes. Use its `processed_scope` and Processing Notes to track large-source progress.
- Knowledge notes use Summary, Observations, Conflicts, and Related. Entity notes use Current State, Timeline, Conflicts, and Related. Current State is the best current synthesis; Timeline holds dated/superseded facts; changing entity history must not live only in source notes; conflict sections record contradictions with evidence.

## Provenance And Identity

- Page-level provenance is acceptable for low-risk synthesis. Require claim-level evidence for people, clients, schedules, money, memberships, projects, decisions, temporal or disputed claims, operational state, and entity Current State.
- Use the best evidence anchor available: page, chapter, section, timestamp, message range, heading, or short quote fragment.
- Every updated subject links at least one supporting source note. Every source lists affected subjects under Integrated Into or Processing Notes.
- Before creating a subject, check title, aliases, `wiki/catalog.jsonl`, backlinks, topic/source overlap, and entity identifiers. Prefer updating existing subjects.
- Merge only same-referent notes; split only independent query intents. Prefer archived or superseded over deletion; delete only accidental empty/redundant pages with no unique content, evidence, or inbound links. Ask when identity is ambiguous.

## Ingest Retrieval Budget

During `ingest`, do not reason over the entire vault:

1. Read the target raw file or requested scope, then its matching source note; create a source draft only after source identity is clear.
2. Extract title terms, named entities, explicit concepts, aliases, technologies/products/frameworks/standards, and relevant origin/channel/author/publication terms.
3. Search `wiki/catalog.jsonl` and `scripts/search`; inspect exact title/alias matches, then at most 10 lexically relevant knowledge/entity candidates and their direct links when identity, overlap, or provenance requires it.
4. If there is no strong match, create a new subject rather than broad-scanning. If more than 10 plausible subjects remain, stop and produce an ingest plan before mutation.
5. Read another raw source only when its source note points to it as evidence and the subject note is insufficient. Do not inspect unrelated generic-topic notes; broad vault sweeps require explicit approval.

## Commands

- `ingest [raw path] [raw scope]` applies to one raw Markdown asset and one source note; the default scope is the full file. With no path (including `ingest`, `ingest new data`, or `ingest new sources`), inspect new/modified uncommitted Markdown under `raw/`: ingest one candidate, ask which when multiple, and ask for a path when none. Read raw frontmatter when present; identify source identity/origin/type/scope/topics/entities; update matching subjects before creating new ones; add links and provenance. Require approval for ambiguous path, multiple candidates, or unclear identity/provenance/mutation safety. Finish with `scripts/reindex`, then `scripts/check`; repair ingest-caused errors for at most two cycles, report remaining errors, and write no log.
- `query <question>` and plain-language vault questions are read-only. Treat repository/docs/scripts/workflow questions as normal development work; ask when ambiguous. Read `wiki/index.md`, semantically expand only this query, run `scripts/search`, inspect knowledge/entity notes before source evidence and raw only when needed, then return note paths and evidence links. Mutate nothing.
- `lint` performs only safe maintenance: validate metadata, regenerate stale artifacts, fix obvious broken links, normalize unambiguous formatting, add exact-match aliases/backlinks, and report duplicates, orphans, source-type fragmentation, and topic fragmentation. Require approval for merge, split, delete, archive, supersede, broad topic/source-type cleanup, or structural rewrite; report findings and allowed changes.

## Retrieval, Validation, And Concurrency

- `wiki/index.md` and `wiki/catalog.jsonl` are generated caches, not authority. Use lexical retrieval via `scripts/search`; LLM semantic expansion is allowed only during `query`.
- After changing wiki notes, run `scripts/reindex`, then `scripts/check`, repairing change-caused errors. Reindex must not validate or repair ordinary notes; check is read-only and must not require source aliases, `kind`, privacy metadata, controlled vocabularies, or a global log.
- For code changes, run `python3 -m ruff format`, `python3 -m ruff check`, and relevant validation/tests. Run `python3 -m unittest discover scripts/tests` when scripts, templates, metadata rules, or retrieval behavior change.
- Retrieval/query agents are read-only. Do not run multiple mutating agents concurrently; a mutating agent is the only writer to `wiki/`. Rebuild generated artifacts once before user review.
- When available, use `obsidian-markdown` for Markdown syntax. Do not copy skill files into this repository or make skills a runtime dependency.
