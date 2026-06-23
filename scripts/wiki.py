from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import difflib
import hashlib
import json
import posixpath
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
CATALOG = WIKI / "catalog.jsonl"
INDEX = WIKI / "index.md"
NOTE_DIRS = {
    "source": WIKI / "sources",
    "knowledge": WIKI / "knowledge",
    "entity": WIKI / "entities",
}
REQUIRED_STRUCTURE = (
    ROOT / "raw",
    WIKI,
    WIKI / "sources",
    WIKI / "knowledge",
    WIKI / "entities",
    WIKI / "templates",
)
ALLOWED_ROLES = frozenset(NOTE_DIRS)
ALLOWED_LIFECYCLES = frozenset({"active", "stub", "superseded", "archived"})
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$")
WIKILINK_RE = re.compile(r"!?\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
PROCESSING_BULLETS = (
    "- Processed scope:",
    "- Evidence anchors used:",
    "- Remaining scope:",
    "- Affected notes:",
    "- Processing timestamp:",
)


@dataclasses.dataclass(frozen=True)
class Note:
    path: Path
    relpath: str
    frontmatter: dict[str, Any]
    body: str
    raw_text: str

    @property
    def title(self) -> str:
        first_heading = re.search(r"^#\s+(.+?)\s*$", self.body, flags=re.MULTILINE)
        return first_heading.group(1).strip() if first_heading else self.path.stem

    @property
    def role(self) -> str | None:
        value = self.frontmatter.get("role")
        return str(value) if value is not None else None


@dataclasses.dataclass
class CheckResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def wiki_note_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in NOTE_DIRS.values():
        if directory.exists():
            paths.extend(directory.rglob("*.md"))
    return sorted(paths, key=lambda p: rel(p).lower())


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw_yaml = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(raw_yaml) or {}
    if not isinstance(data, dict):
        return {}, body
    return dict(data), body


def read_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    return Note(path=path, relpath=rel(path), frontmatter=frontmatter, body=body, raw_text=text)


def read_notes() -> list[Note]:
    return [read_note(path) for path in wiki_note_paths()]


def jsonable(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def headings(body: str) -> list[str]:
    return [match.group(2).strip() for match in HEADING_RE.finditer(body)]


def lead(body: str) -> str:
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#") or stripped == "---":
            continue
        return stripped[:280]
    return ""


def wikilinks(text: str) -> list[str]:
    return sorted({match.group(1).strip() for match in WIKILINK_RE.finditer(text)})


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized_link_candidates(target: str) -> list[str]:
    cleaned = target.strip().strip("/")
    candidates = [cleaned]
    if cleaned.endswith(".md"):
        candidates.append(cleaned[:-3])
    else:
        candidates.append(f"{cleaned}.md")
    candidates.append(Path(cleaned).name)
    if not cleaned.endswith(".md"):
        candidates.append(Path(cleaned).with_suffix(".md").name)
    return [candidate.replace("\\", "/") for candidate in dict.fromkeys(candidates)]


def build_link_index(notes: list[Note]) -> dict[str, str]:
    index: dict[str, str] = {}
    for note in notes:
        without_ext = note.relpath[:-3] if note.relpath.endswith(".md") else note.relpath
        names = {
            note.relpath,
            without_ext,
            note.path.name,
            note.path.stem,
        }
        for name in names:
            index[name] = note.relpath
    return index


def resolve_wikilink(target: str, link_index: dict[str, str]) -> str | None:
    for candidate in normalized_link_candidates(target):
        if candidate in link_index:
            return link_index[candidate]
        raw_candidate = raw_path(candidate)
        if raw_candidate is not None and raw_candidate.exists():
            return candidate
    return None


def raw_path(target: str) -> Path | None:
    normalized = normalize_raw_target(target)
    if normalized is None:
        return None
    path = (ROOT / normalized).resolve()
    raw_root = (ROOT / "raw").resolve()
    try:
        path.relative_to(raw_root)
    except ValueError:
        return None
    return path


def normalize_raw_target(target: str) -> str | None:
    normalized = posixpath.normpath(target.strip().replace("\\", "/").strip("/"))
    if normalized in {"", "."} or normalized == "raw" or normalized.startswith("../"):
        return None
    if not normalized.startswith("raw/"):
        return None
    return normalized


def resolve_raw_target(target: str) -> str | None:
    for candidate in normalized_link_candidates(target):
        raw_candidate = raw_path(candidate)
        if raw_candidate is not None and raw_candidate.exists():
            return normalize_raw_target(candidate)
    return None


def source_raw_target(note: Note, errors: list[str]) -> str | None:
    value = note.frontmatter.get("raw")
    if value is None:
        errors.append(f"{note.relpath}: source notes require `raw`")
        return None
    if not isinstance(value, str):
        errors.append(f"{note.relpath}: `raw` must be a single raw path or wikilink")
        return None

    targets = wikilinks(value)
    if len(targets) > 1:
        errors.append(f"{note.relpath}: `raw` must contain exactly one raw target")
        return None
    target = targets[0] if targets else value.strip()
    if not target:
        errors.append(f"{note.relpath}: `raw` must not be empty")
        return None
    if normalize_raw_target(target) is None:
        errors.append(f"{note.relpath}: `raw` must point under `raw/`")
        return None
    resolved = resolve_raw_target(target)
    if resolved is None:
        errors.append(f"{note.relpath}: `raw` target does not exist: {target}")
        return None
    return resolved


def catalog_records(notes: list[Note] | None = None) -> list[dict[str, Any]]:
    notes = read_notes() if notes is None else notes
    link_index = build_link_index(notes)
    outgoing: dict[str, list[str]] = {}
    for note in notes:
        resolved = []
        for target in wikilinks(note.raw_text):
            resolved_target = resolve_wikilink(target, link_index)
            resolved.append(resolved_target or target)
        outgoing[note.relpath] = sorted(dict.fromkeys(resolved))

    backlinks: dict[str, list[str]] = defaultdict(list)
    for source, targets in outgoing.items():
        for target in targets:
            if target in link_index.values():
                backlinks[target].append(source)

    records: list[dict[str, Any]] = []
    for note in notes:
        fm = note.frontmatter
        record: dict[str, Any] = {
            "schema_version": 1,
            "path": note.relpath,
            "title": note.title,
            "role": jsonable(fm.get("role")),
            "lifecycle": jsonable(fm.get("lifecycle")),
            "topics": jsonable(as_list(fm.get("topics"))),
            "tags": jsonable(as_list(fm.get("tags"))),
            "updated": jsonable(fm.get("updated")),
            "lead": lead(note.body),
            "headings": headings(note.body),
            "links": outgoing.get(note.relpath, []),
            "backlinks": sorted(backlinks.get(note.relpath, [])),
            "raw": jsonable(fm.get("raw")),
            "content_hash": sha256_text(note.raw_text),
            "body": normalize_text(note.body),
        }
        if "kind" in fm:
            record["kind"] = jsonable(fm.get("kind"))
        if note.role in {"knowledge", "entity"}:
            record["aliases"] = jsonable(as_list(fm.get("aliases")))
        elif "aliases" in fm:
            record["aliases"] = jsonable(as_list(fm.get("aliases")))
        records.append(record)
    return sorted(records, key=lambda item: item["path"].lower())


def render_catalog(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "".join(
        json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records
    )


def render_index(records: list[dict[str, Any]]) -> str:
    role_counts = Counter(record.get("role") or "missing" for record in records)
    topic_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for record in records:
        topic_counts.update(str(item) for item in record.get("topics", []))
        tag_counts.update(str(item) for item in record.get("tags", []))

    lines = [
        "# LLM-Wiki Index",
        "",
        "> Generated by `scripts/reindex`. Do not edit manually.",
        "",
        "## Notes By Role",
        "",
    ]
    if role_counts:
        for role in sorted(role_counts):
            lines.append(f"- {role}: {role_counts[role]}")
    else:
        lines.append("- No wiki notes indexed.")

    lines.extend(["", "## Notes By Topic", ""])
    if topic_counts:
        for topic, count in sorted(topic_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {topic}: {count}")
    else:
        lines.append("- No topics indexed.")

    lines.extend(["", "## Recent Updates", ""])
    recent = sorted(records, key=lambda item: str(item.get("updated") or ""), reverse=True)[:20]
    if recent:
        for record in recent:
            note_link = f"[[{record['path'][:-3]}|{record['title']}]]"
            note_meta = f"{record.get('role')}, {record.get('updated')}"
            lines.append(f"- {note_link} ({note_meta})")
    else:
        lines.append("- No wiki notes indexed.")

    lines.extend(["", "## Maintenance Tags", ""])
    maintenance_tags = [(tag, count) for tag, count in tag_counts.items() if "/" in tag]
    if maintenance_tags:
        for tag, count in sorted(maintenance_tags, key=lambda item: (-item[1], item[0])):
            lines.append(f"- {tag}: {count}")
    else:
        lines.append("- No maintenance tags indexed.")

    lines.extend(["", "## Validation Warnings", ""])
    check = validate(records=records, check_staleness=False)
    if check.warnings:
        for warning in check.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No validation warnings from indexed notes.")

    lines.extend(["", "## All Notes", ""])
    if records:
        for record in records:
            topics = ", ".join(record.get("topics", [])) or "no topics"
            lines.append(
                f"- [[{record['path'][:-3]}|{record['title']}]] - {record.get('role')} - {topics}"
            )
    else:
        lines.append("- No wiki notes indexed.")

    return "\n".join(lines) + "\n"


def write_generated_artifacts() -> None:
    records = catalog_records()
    CATALOG.write_text(render_catalog(records), encoding="utf-8")
    INDEX.write_text(render_index(records), encoding="utf-8")


def section_text(body: str, heading_name: str) -> str:
    matches = list(HEADING_RE.finditer(body))
    for index, match in enumerate(matches):
        if match.group(2).strip().lower() == heading_name.lower():
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            return body[start:end]
    return ""


def validate(
    records: list[dict[str, Any]] | None = None, check_staleness: bool = True
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []
    validate_required_structure(errors)
    notes = read_notes()
    link_index = build_link_index(notes)

    for note in notes:
        fm = note.frontmatter
        prefix = note.relpath
        if not fm:
            errors.append(f"{prefix}: missing YAML frontmatter")
            continue

        role = note.role
        if role not in ALLOWED_ROLES:
            errors.append(f"{prefix}: role must be one of {sorted(ALLOWED_ROLES)}")

        for key in ("role", "topics", "tags", "created", "updated"):
            if key not in fm:
                errors.append(f"{prefix}: missing required metadata `{key}`")

        for key in ("topics", "tags"):
            if key in fm and not isinstance(fm[key], list):
                errors.append(f"{prefix}: `{key}` must be a list")

        for key in ("created", "updated"):
            if key in fm and not is_timestamp(fm[key]):
                errors.append(f"{prefix}: `{key}` must be ISO 8601 with timezone offset")

        if role in {"knowledge", "entity"}:
            if "lifecycle" not in fm:
                errors.append(f"{prefix}: subject notes require `lifecycle`")
            elif str(fm["lifecycle"]) not in ALLOWED_LIFECYCLES:
                errors.append(f"{prefix}: lifecycle must be one of {sorted(ALLOWED_LIFECYCLES)}")
            if "aliases" not in fm:
                errors.append(f"{prefix}: subject notes require `aliases`")
            elif not isinstance(fm["aliases"], list):
                errors.append(f"{prefix}: `aliases` must be a list")

        if role == "source":
            validate_source_note(note, errors)
        elif role == "knowledge":
            require_sections(note, ("Summary", "Observations", "Conflicts", "Related"), errors)
        elif role == "entity":
            require_sections(note, ("Current State", "Timeline", "Conflicts", "Related"), errors)

        for target in wikilinks(note.raw_text):
            if resolve_wikilink(target, link_index) is None:
                errors.append(f"{prefix}: broken wikilink `[[{target}]]`")

    validate_duplicate_raw_mappings(notes, errors)
    validate_source_type_fragmentation(notes, warnings)

    if check_staleness:
        records = catalog_records(notes)
        expected_catalog = render_catalog(records)
        expected_index = render_index(records)
        if CATALOG.exists():
            actual_catalog = CATALOG.read_text(encoding="utf-8")
            if actual_catalog != expected_catalog:
                errors.append("wiki/catalog.jsonl is stale; run scripts/reindex")
        else:
            errors.append("wiki/catalog.jsonl is missing; run scripts/reindex")
        if INDEX.exists():
            actual_index = INDEX.read_text(encoding="utf-8")
            if actual_index != expected_index:
                errors.append("wiki/index.md is stale; run scripts/reindex")
        else:
            errors.append("wiki/index.md is missing; run scripts/reindex")

    return CheckResult(
        errors=sorted(dict.fromkeys(errors)), warnings=sorted(dict.fromkeys(warnings))
    )


def validate_required_structure(errors: list[str]) -> None:
    for path in REQUIRED_STRUCTURE:
        if not path.is_dir():
            errors.append(f"{rel(path)} is missing")


def is_timestamp(value: Any) -> bool:
    if isinstance(value, dt.datetime):
        return value.tzinfo is not None
    if isinstance(value, str):
        return bool(TIMESTAMP_RE.match(value))
    return False


def require_sections(note: Note, required: tuple[str, ...], errors: list[str]) -> None:
    existing = {
        match.group(2).strip().lower()
        for match in HEADING_RE.finditer(note.body)
        if match.group(1) == "##"
    }
    for heading in required:
        if heading.lower() not in existing:
            errors.append(f"{note.relpath}: missing section `## {heading}`")


def validate_source_note(note: Note, errors: list[str]) -> None:
    source_raw_target(note, errors)
    if "source_type" not in note.frontmatter:
        errors.append(f"{note.relpath}: source notes require `source_type`")
    if "origin" not in note.frontmatter:
        errors.append(f"{note.relpath}: source notes require `origin`")
    if "processed_scope" not in note.frontmatter:
        errors.append(f"{note.relpath}: source notes require `processed_scope`")
    require_sections(
        note,
        (
            "Summary",
            "Evidence",
            "Integrated Into",
            "Conflicts And Uncertainty",
            "Processing Notes",
        ),
        errors,
    )
    section = section_text(note.body, "Processing Notes")
    for bullet in PROCESSING_BULLETS:
        if bullet not in section:
            errors.append(f"{note.relpath}: Processing Notes missing `{bullet}`")


def validate_duplicate_raw_mappings(notes: list[Note], errors: list[str]) -> None:
    seen: dict[str, list[str]] = defaultdict(list)
    local_errors: list[str] = []
    for note in notes:
        if note.role == "source":
            target = source_raw_target(note, local_errors)
            if target is not None:
                seen[target].append(note.relpath)
    for raw, paths in seen.items():
        if raw and len(paths) > 1:
            errors.append(f"duplicate raw-to-source mapping {raw}: {', '.join(sorted(paths))}")


def normalize_source_type(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "", lowered)
    return lowered.removesuffix("s")


def validate_source_type_fragmentation(notes: list[Note], warnings: list[str]) -> None:
    values = sorted(
        {
            str(note.frontmatter.get("source_type"))
            for note in notes
            if note.role == "source" and note.frontmatter.get("source_type")
        }
    )
    by_normalized: dict[str, set[str]] = defaultdict(set)
    for value in values:
        by_normalized[normalize_source_type(value)].add(value)
    for normalized, originals in by_normalized.items():
        if normalized and len(originals) > 1:
            warnings.append(f"near-duplicate source_type values: {', '.join(sorted(originals))}")
    for left_index, left in enumerate(values):
        for right in values[left_index + 1 :]:
            if (
                normalize_source_type(left) != normalize_source_type(right)
                and difflib.SequenceMatcher(None, left.lower(), right.lower()).ratio() >= 0.86
            ):
                warnings.append(f"near-duplicate source_type values: {left}, {right}")


def load_catalog() -> list[dict[str, Any]]:
    if not CATALOG.exists():
        raise FileNotFoundError("wiki/catalog.jsonl is missing; run scripts/reindex")
    records = []
    for line_number, line in enumerate(CATALOG.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"wiki/catalog.jsonl:{line_number}: invalid JSON: {exc}") from exc
    return records


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}


def search_records(
    query: str, role: str | None = None, limit: int = 20
) -> list[tuple[int, dict[str, Any]]]:
    query_norm = normalize_text(query).lower()
    query_tokens = tokens(query)
    results: list[tuple[int, dict[str, Any]]] = []
    for record in load_catalog():
        if role and record.get("role") != role:
            continue
        score = score_record(record, query_norm, query_tokens)
        if score > 0:
            results.append((score, record))
    results.sort(key=lambda item: (-item[0], item[1]["path"]))
    return results[:limit]


def score_record(record: dict[str, Any], query_norm: str, query_tokens: set[str]) -> int:
    score = 0
    title = str(record.get("title") or "")
    aliases = [str(alias) for alias in record.get("aliases", [])]
    topics = [str(item) for item in record.get("topics", [])]
    tags = [str(item) for item in record.get("tags", [])]
    kind = str(record.get("kind") or "")
    headings_ = [str(item) for item in record.get("headings", [])]
    lead_ = str(record.get("lead") or "")
    body = str(record.get("body") or "")

    if title.lower() == query_norm:
        score += 1000
    if any(alias.lower() == query_norm for alias in aliases):
        score += 900
    score += 120 * len(query_tokens & tokens(title))
    score += 90 * sum(len(query_tokens & tokens(alias)) for alias in aliases)
    score += 60 * sum(len(query_tokens & tokens(topic)) for topic in topics)
    score += 45 * sum(len(query_tokens & tokens(tag)) for tag in tags)
    score += 40 * len(query_tokens & tokens(kind))
    score += 25 * sum(len(query_tokens & tokens(heading)) for heading in headings_)
    score += 12 * len(query_tokens & tokens(lead_))
    score += 2 * len(query_tokens & tokens(body))
    return score


def main_reindex() -> int:
    write_generated_artifacts()
    print("Regenerated wiki/index.md and wiki/catalog.jsonl")
    return 0


def main_search(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lexical search over wiki/catalog.jsonl")
    parser.add_argument("query")
    parser.add_argument("--role", choices=sorted(ALLOWED_ROLES))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        results = search_records(args.query, role=args.role, limit=args.limit)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for score, record in results:
        print(f"{score}\t{record['path']}\t{record.get('title', '')}\t{record.get('role', '')}")
    return 0


def main_check() -> int:
    result = validate()
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if result.ok:
        print("OK")
        return 0
    return 1
