"""
Vault directory creation and validation.

Creates and validates the two-vault structure (clean-vault + wiki-vault).
Never auto-repairs — only warns about missing components.
"""

import json
import os
from pathlib import Path
from typing import Optional, List

from services.paths import normalize_path


# Default template for AGENTS.md — the agent constitution
DEFAULT_AGENTS_MD = """# AGENTS.md — Vanilla Wiki Constitution

This file defines how the AI agent should behave when processing the clean vault
and generating wiki content. The agent re-reads this file on every run.

## Directory Schema

- `concepts/` — Approved concept articles (one per concept)
- `staging/` — Proposed articles awaiting human approval
- `index.md` — Auto-maintained alphabetical index of all concepts
- `graph.json` — Serialized graph data for visualization and stale tracking

## Rules

1. Never write to the clean vault. It is read-only for agents.
2. Always write proposals to `staging/batch_NNN/` before they can be approved.
3. Every article must have YAML frontmatter with: title, sources, created, last_updated, status, confidence.
4. Sources must reference actual files in the clean vault using relative paths.
5. Use `[[wikilinks]]` to link between concept articles.
6. Group related concepts into a single batch when they come from the same source.
7. When updating an existing article, explain what changed and why in the proposal.

## Traceability Format

```yaml
---
title: Concept Name
sources:
  - clean-vault/raw/source_file.md
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
status: proposed | approved | rejected | stale
confidence: high | medium | low
---
```

## Ontology Reference

See `ontology.md` for the domain-specific ontology that shapes how concepts are categorized.
"""

DEFAULT_ONTOLOGY_MD = """# Ontology

This file defines the domain ontology for the wiki. It is generated during onboarding
and can be edited at any time. The agent reads this on every run.

## Concept Categories

(Generated during onboarding based on your vault description)

## Relationship Types

- **references** — One concept references another
- **extends** — One concept builds on another
- **contradicts** — Two concepts are in tension
- **exemplifies** — One concept is an example of another
"""

DEFAULT_INDEX_MD = """# Wiki Index

*Auto-maintained by the File-back Agent. Do not edit manually.*

## Concepts

(No concepts yet. Approve proposals to populate this index.)
"""

DEFAULT_GRAPH_JSON = {
    "nodes": [],
    "edges": [],
    "source_map": {},
}


def create_vault_structure(
    base_path: str,
    ontology_content: Optional[str] = None,
    agents_content: Optional[str] = None,
) -> dict:
    """
    Create the full two-vault directory structure.

    Args:
        base_path: Parent directory for both vaults (e.g., ~/Vanilla/)
        ontology_content: Custom ontology.md content (or use default)
        agents_content: Custom AGENTS.md content (or use default)

    Returns:
        dict with clean_vault_path and wiki_vault_path
    """
    base = Path(base_path)

    # Clean vault directories
    clean_vault = base / "clean-vault"
    (clean_vault / "raw").mkdir(parents=True, exist_ok=True)
    (clean_vault / "notes").mkdir(parents=True, exist_ok=True)

    # Wiki vault directories
    wiki_vault = base / "wiki-vault"
    (wiki_vault / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki_vault / "staging").mkdir(parents=True, exist_ok=True)
    (wiki_vault / "staging" / ".meta").mkdir(parents=True, exist_ok=True)

    # Write wiki vault files (only if they don't already exist)
    _write_if_missing(wiki_vault / "AGENTS.md", agents_content or DEFAULT_AGENTS_MD)
    _write_if_missing(wiki_vault / "ontology.md", ontology_content or DEFAULT_ONTOLOGY_MD)
    _write_if_missing(wiki_vault / "index.md", DEFAULT_INDEX_MD)
    _write_if_missing(
        wiki_vault / "graph.json",
        json.dumps(DEFAULT_GRAPH_JSON, indent=2),
    )

    return {
        "clean_vault_path": normalize_path(str(clean_vault)),
        "wiki_vault_path": normalize_path(str(wiki_vault)),
    }


def validate_vault_structure(base_path: str) -> List[str]:
    """
    Validate that the vault structure is intact.

    Returns a list of warnings (empty list = all good).
    Never auto-repairs — only reports issues.
    """
    warnings = []
    base = Path(base_path)

    # Check clean vault
    clean_vault = base / "clean-vault"
    if not clean_vault.exists():
        warnings.append("clean-vault/ directory is missing")
    else:
        if not (clean_vault / "raw").exists():
            warnings.append("clean-vault/raw/ directory is missing")
        if not (clean_vault / "notes").exists():
            warnings.append("clean-vault/notes/ directory is missing")

    # Check wiki vault
    wiki_vault = base / "wiki-vault"
    if not wiki_vault.exists():
        warnings.append("wiki-vault/ directory is missing")
    else:
        for required in ["concepts", "staging", "AGENTS.md", "ontology.md", "index.md", "graph.json"]:
            if not (wiki_vault / required).exists():
                warnings.append(f"wiki-vault/{required} is missing")

    return warnings


def _write_if_missing(path: Path, content: str) -> None:
    """Write content to a file only if it doesn't exist."""
    if not path.exists():
        path.write_text(content, encoding="utf-8")
