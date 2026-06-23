import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WikiScriptsTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="llm-wiki-test-"))
        shutil.copytree(
            ROOT / "scripts",
            self.tmpdir / "scripts",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for relpath in (
            "wiki/sources",
            "wiki/knowledge",
            "wiki/entities",
        ):
            (self.tmpdir / relpath).mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / "wiki" / "templates", self.tmpdir / "wiki" / "templates")
        (self.tmpdir / "raw").mkdir(exist_ok=True)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(self.tmpdir / "scripts")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def run_script(self, *args):
        return subprocess.run(
            [str(self.tmpdir / "scripts" / args[0]), *args[1:]],
            cwd=self.tmpdir,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_note(self, relpath, text):
        path = self.tmpdir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_raw(self, relpath, text="# raw\n"):
        path = self.tmpdir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_source_note(
        self,
        relpath="wiki/sources/article.md",
        raw='"[[raw/article]]"',
        extra_frontmatter="",
        sections=None,
    ):
        sections = (
            sections
            or """## Summary

## Evidence

## Integrated Into

## Conflicts And Uncertainty

## Processing Notes

- Processed scope:
- Evidence anchors used:
- Remaining scope:
- Affected notes:
- Processing timestamp:
"""
        )
        return self.write_note(
            relpath,
            f"""---
role: source
topics: []
tags: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
raw: {raw}
source_type: article
origin: ""
processed_scope: "all"
{extra_frontmatter}---

# Article

{sections}""",
        )

    def test_reindex_builds_catalog_with_links_backlinks_raw_and_aliases(self):
        self.write_raw("raw/article.md")
        self.write_note(
            "wiki/sources/article.md",
            """---
role: source
topics: [retrieval]
tags: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
raw: "[[raw/article]]"
source_type: article
origin: ""
processed_scope: "all"
---

# Article

## Summary

source lead.

## Evidence

## Integrated Into

- [[wiki/knowledge/Retrieval-Augmented Generation]]

## Conflicts And Uncertainty

## Processing Notes

- Processed scope:
- Evidence anchors used:
- Remaining scope:
- Affected notes:
- Processing timestamp:
""",
        )
        self.write_note(
            "wiki/knowledge/Retrieval-Augmented Generation.md",
            """---
role: knowledge
lifecycle: active
topics: [retrieval, ai]
tags: []
aliases: [RAG]
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
kind: concept
---

# Retrieval-Augmented Generation

## Summary

Grounded generation.

## Observations

- Supported by [[wiki/sources/article]].

## Conflicts

## Related
""",
        )

        result = self.run_script("reindex")
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [
            json.loads(line)
            for line in (self.tmpdir / "wiki" / "catalog.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        by_path = {record["path"]: record for record in records}
        knowledge = by_path["wiki/knowledge/Retrieval-Augmented Generation.md"]
        source = by_path["wiki/sources/article.md"]
        self.assertEqual(knowledge["aliases"], ["RAG"])
        self.assertIn("wiki/sources/article.md", knowledge["links"])
        self.assertIn("wiki/knowledge/Retrieval-Augmented Generation.md", source["links"])
        self.assertIn("wiki/sources/article.md", knowledge["backlinks"])
        self.assertEqual(source["raw"], "[[raw/article]]")

    def test_check_does_not_require_aliases_on_source(self):
        self.write_raw("raw/article.md")
        self.write_note(
            "wiki/sources/article.md",
            """---
role: source
topics: []
tags: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
raw: "[[raw/article]]"
source_type: article
origin: ""
processed_scope: "all"
---

# Article

## Summary

## Evidence

## Integrated Into

## Conflicts And Uncertainty

## Processing Notes

- Processed scope:
- Evidence anchors used:
- Remaining scope:
- Affected notes:
- Processing timestamp:
""",
        )
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_requires_subject_aliases_and_lifecycle(self):
        self.write_note(
            "wiki/knowledge/Missing Metadata.md",
            """---
role: knowledge
topics: []
tags: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
---

# Missing Metadata

## Summary

## Observations

## Conflicts

## Related
""",
        )
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("subject notes require `aliases`", result.stderr)
        self.assertIn("subject notes require `lifecycle`", result.stderr)

    def test_check_requires_source_origin(self):
        self.write_raw("raw/article.md")
        self.write_note(
            "wiki/sources/article.md",
            """---
role: source
topics: []
tags: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
raw: "[[raw/article]]"
source_type: article
processed_scope: "all"
---

# Article

## Summary

## Evidence

## Integrated Into

## Conflicts And Uncertainty

## Processing Notes

- Processed scope:
- Evidence anchors used:
- Remaining scope:
- Affected notes:
- Processing timestamp:
""",
        )
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source notes require `origin`", result.stderr)

    def test_check_requires_level_two_sections(self):
        self.write_raw("raw/article.md")
        self.write_source_note(
            sections="""### Summary

## Evidence

## Integrated Into

## Conflicts And Uncertainty

## Processing Notes

- Processed scope:
- Evidence anchors used:
- Remaining scope:
- Affected notes:
- Processing timestamp:
""",
        )
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing section `## Summary`", result.stderr)

    def test_check_validates_source_raw_target(self):
        self.write_raw("raw/a.md")
        self.write_raw("raw/b.md")
        self.write_source_note("wiki/sources/missing.md", raw='"[[raw/missing]]"')
        self.write_source_note("wiki/sources/outside.md", raw='"[[../README.md]]"')
        self.write_source_note("wiki/sources/multiple.md", raw='"[[raw/a]] and [[raw/b]]"')
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "wiki/sources/missing.md: `raw` target does not exist: raw/missing",
            result.stderr,
        )
        self.assertIn("wiki/sources/outside.md: `raw` must point under `raw/`", result.stderr)
        self.assertIn(
            "wiki/sources/multiple.md: `raw` must contain exactly one raw target",
            result.stderr,
        )

    def test_check_uses_normalized_raw_target_for_duplicates(self):
        self.write_raw("raw/article.md")
        self.write_source_note("wiki/sources/article-a.md", raw='"[[raw/article]]"')
        self.write_source_note("wiki/sources/article-b.md", raw='"raw/article.md"')
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate raw-to-source mapping raw/article.md", result.stderr)

    def test_search_ranks_exact_alias(self):
        self.write_note(
            "wiki/knowledge/Retrieval-Augmented Generation.md",
            """---
role: knowledge
lifecycle: active
topics: [retrieval]
tags: []
aliases: [RAG]
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
---

# Retrieval-Augmented Generation

## Summary

## Observations

## Conflicts

## Related
""",
        )
        self.write_note(
            "wiki/knowledge/Ragged Edge.md",
            """---
role: knowledge
lifecycle: active
topics: []
tags: []
aliases: []
created: 2026-06-17T10:00:00+08:00
updated: 2026-06-17T10:00:00+08:00
---

# Ragged Edge

## Summary

RAG appears in body only.

## Observations

## Conflicts

## Related
""",
        )
        self.assertEqual(self.run_script("reindex").returncode, 0)
        result = self.run_script("search", "RAG", "--role", "knowledge")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            result.stdout.splitlines()[0]
            .split("\t")[1]
            .endswith("Retrieval-Augmented Generation.md")
        )


if __name__ == "__main__":
    unittest.main()
