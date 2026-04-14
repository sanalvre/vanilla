# Vault Schema

## Directory Structure

```
~/Vanilla/
  clean-vault/                # Human-owned vault
    raw/                      # Ingested files (PDFs->md, URLs->md)
    notes/                    # User's own markdown notes
    ...                       # User can organize freely

  wiki-vault/                 # Agent-owned vault (human reads only)
    concepts/                 # Approved concept articles
    index.md                  # Auto-maintained master index
    graph.json                # Serialized graph data (Reagraph + stale tracking)
    AGENTS.md                 # Constitution: schema, rules, ontology reference
    ontology.md               # User's domain ontology (from onboarding)
    staging/                  # Proposed articles awaiting approval
      .meta/                  # Temporary ingest/analysis metadata
      batch_001/
        proposal.md           # Human-readable batch summary
        article_a.md          # Draft concept article
        article_b.md
```

## Article Frontmatter Schema

Every wiki article in `concepts/` must have this YAML frontmatter:

```yaml
---
title: Concept Name
sources:
  - clean-vault/raw/paper_a.md
  - clean-vault/notes/meeting_notes.md
created: 2026-04-13
last_updated: 2026-04-13
status: approved          # proposed | approved | rejected | stale
confidence: high          # high | medium | low
---
```

## graph.json Schema

```json
{
  "nodes": [
    {
      "id": "concept-name",
      "label": "Concept Name",
      "path": "wiki-vault/concepts/concept-name.md",
      "category": "ontology-category",
      "lastBatch": "batch_003"
    }
  ],
  "edges": [
    {
      "source": "concept-a",
      "target": "concept-b",
      "type": "wikilink"
    }
  ],
  "source_map": {
    "clean-vault/raw/paper_a.md": [
      "wiki-vault/concepts/concept-name.md"
    ]
  }
}
```

- `nodes` and `edges`: consumed by Reagraph for visualization
- `source_map`: used by stale article detection (when a source changes, look up all articles citing it)

## Path Normalization Rules

All paths stored in frontmatter, graph.json, and SQLite use forward slashes regardless of OS:
- Windows: `C:\Users\User\Vanilla\clean-vault\raw\paper.md` -> stored as `clean-vault/raw/paper.md`
- macOS: `/Users/user/Vanilla/clean-vault/raw/paper.md` -> stored as `clean-vault/raw/paper.md`

Paths are always **relative to the Vanilla root directory** (the parent of both vaults).
