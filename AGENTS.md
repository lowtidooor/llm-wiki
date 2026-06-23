# LLM-Wiki Agent Rules

All rules apply. Operating boundaries are hard constraints, and command rules do not relax them.

## Operating Boundaries

- `raw/` is user-owned source material.
- Agents may create new Markdown raw sources only when explicitly requested by the user.
- If the target raw path exists or is unclear, ask before writing.
- Existing `raw/` assets are immutable: never edit, move, delete, normalize, or annotate them.
- Agent-created raw sources must be Markdown under `raw/`, with a clear title, readable sections, and enough provenance in the text to explain what was captured.
- Preserve user-provided source content faithfully.
- Only summarize or synthesize it when the user explicitly asks for a summary/capture instead of a verbatim source.
- Maintain only `wiki/`, templates, deterministic scripts, generated retrieval artifacts, and explicitly requested new raw Markdown sources.
- Data model: `raw -> source -> subject`.
- Valid roles: `source`, `knowledge`, `entity`.
- Subjects are only `knowledge` or `entity`.
- Never create `wiki/log.md` or any global log.
- Do not add database systems, graph database systems, ontologies, embeddings, vector search, semantic indexes, graph retrieval, event systems, controlled vocabularies, privacy/sensitivity metadata, lock files, branch naming, coordination services, custom project skills, or core dependencies on `json-canvas`, `obsidian-cli`, or `defuddle`.
- Do not run automatic Git operations, including Git add, commit, reset, checkout, or destructive Git commands. If explicitly asked to commit/amend, use Conventional Commits: `<type>(<scope>): <subject>` or `<type>: <subject>` with type `docs`, `fix`, `feat`, `test`, `chore`, `refactor`, or `revert`.
- When command intent, scope, source identity, subject identity, provenance, merge/split/delete/archive decisions, or mutation safety is unclear, ask the user before mutating.
- Do not guess.

## Note Structure

- Copy the matching template in `wiki/templates/` when creating frontmatter.
- Set `created` and `updated` to the current ISO 8601 timestamp with timezone offset.
- Use YAML lists for `topics`, `tags`, and subject `aliases`.
- Use `aliases: []` when a subject has no aliases.
- Required frontmatter:
  - All wiki notes: `role`, `topics`, `tags`, `created`, `updated`.
  - `knowledge` and `entity`: `lifecycle`, `aliases`.
  - `source`: `raw`, `source_type`, `origin`, `processed_scope`.
- Metadata rules:
  - `raw` must be exactly one `[[raw/...]]` target.
  - `kind` is optional.
  - `source_type` is free-form.
  - Near-duplicates are warnings only.
  - Lifecycle values: `active`, `stub`, `superseded`, `archived`.
  - Topics are stable retrieval groups.
  - Tags are sparse maintenance/workflow labels.
- Required note bodies:
  - `wiki/sources/`: one note per raw asset.
  - Source notes must link the raw asset and record provenance, scope, evidence anchors, observations, affected notes, conflicts, and `## Processing Notes`.
  - Source `## Processing Notes`: processed scope, evidence anchors used, remaining scope, affected notes, processing timestamp. Use this plus `processed_scope` for large-source progress.
  - `wiki/knowledge/`: `## Summary`, `## Observations`, `## Conflicts`, `## Related`.
  - `wiki/entities/`: `## Current State`, `## Timeline`, `## Conflicts`, `## Related`.
- Section meaning:
  - `Current State` is best current synthesis.
  - `Timeline` holds dated and superseded facts.
  - Changing entity history must not live only in source notes.
  - `Conflicts` / `Conflicts And Uncertainty` hold contradictions with evidence.

## Provenance And Identity

- Page-level provenance is acceptable for low-risk synthesis.
- Claim-level evidence is required for people, clients, schedules, money, memberships, projects, decisions, temporal facts, disputed claims, operational state, and entity `Current State`.
- Use the best available evidence anchor: page, chapter, section, timestamp, message range, heading, or short quote fragment.
- Every updated `knowledge` or `entity` note must link to at least one supporting source note.
- Every source note must list affected knowledge/entity notes under `## Integrated Into` or `## Processing Notes`.
- Before creating a subject, check title, aliases, `wiki/catalog.jsonl`, backlinks, topic overlap, source overlap, and entity identifiers.
- Prefer updating existing subjects. Merge only same-referent notes. Split only when one note serves multiple independent query intents.
- Prefer `archived` or `superseded` over deletion. Delete only accidental empty/redundant pages with no unique content, evidence, or inbound links.
- Ask the user when identity is ambiguous.

## Commands

- `ingest [raw path] [raw scope]`:
  - Applies: exactly one raw Markdown asset and one source note. Raw scope defaults to the full file.
  - Behavior:
    - If no raw path is provided, inspect new or modified uncommitted Markdown files under `raw/`.
    - Requests like `ingest`, `ingest new data`, or `ingest new sources` count as no raw path.
    - Ingest when exactly one candidate exists.
    - Ask which file to process when multiple candidates exist.
    - Ask for a raw path when no candidates exist.
    - Read raw frontmatter when present.
    - Identify source identity/origin/type/scope/topics/entities.
    - Update matching subjects before creating subjects.
    - Add links/provenance.
  - Requires approval: ambiguous path, multiple candidates, unclear identity/provenance/mutation safety.
  - Ends by: run `scripts/reindex` then `scripts/check`. Repair ingest-caused errors for at most two cycles. Report remaining errors. Do not write logs.
- `query <question>` or a plain-language question about vault contents:
  - Applies: read-only questions about vault contents.
  - Behavior:
    - Treat plain-language questions as wiki queries only when they ask about knowledge represented in `wiki/` or supporting raw sources.
    - Treat questions about the repository, docs, scripts, or workflow as normal development requests.
    - Read `wiki/index.md`.
    - Semantically expand the query with the LLM.
    - Run `scripts/search`.
    - Inspect knowledge/entity notes first, source evidence second, raw only if needed.
  - Requires approval: ambiguous query/repository intent.
  - Ends by: return note paths and evidence links. Mutate nothing.
- `lint`:
  - Applies: safe maintenance only unless approved.
  - Behavior: validate metadata, regenerate stale artifacts, fix obvious broken links, normalize unambiguous formatting, add exact-match aliases/backlinks, report duplicates/orphans/source-type fragmentation/topic fragmentation.
  - Requires approval: merge, split, delete, archive, supersede, broad topic or `source_type` cleanup, structural rewrite.
  - Ends by: report findings and any allowed safe changes.

## Retrieval, Validation, And Concurrency

- `wiki/index.md` and `wiki/catalog.jsonl` are generated caches, not authority.
- Use lexical retrieval via `scripts/search`.
- LLM semantic expansion is allowed only during `query`.
- After mutating wiki notes, run `scripts/reindex`, then `scripts/check`, and repair validation errors caused by the change.
- `scripts/reindex` must not validate or repair ordinary notes.
- `scripts/check` is read-only and must not require source aliases, `kind`, privacy metadata, controlled vocabularies, or any global log.
- When modifying code, run `python3 -m ruff format`, `python3 -m ruff check`, and relevant validation/tests.
- Run `python3 -m unittest discover scripts/tests` when scripts, templates, metadata rules, or retrieval behavior change.
- Retrieval/query agents are read-only.
- Do not run multiple mutating agents concurrently.
- A mutating agent assumes it is the only writer to `wiki/`.
- Rebuild generated artifacts once before user review.
- When available, use `obsidian-markdown` for Markdown syntax.
- Do not copy skill files into this repository or make skills a runtime dependency.
