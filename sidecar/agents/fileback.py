"""
File-back agent — writes approved articles to wiki-vault.

Only runs when a human approves a proposal batch.
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from config import VanillaConfig
from db import repository as repo
from services.llm_service import chat_completion
from services.graph_service import (
    load_graph,
    save_graph,
    add_node,
    add_edge,
    add_source_citation,
)
from services.paths import normalize_path

logger = logging.getLogger("vanilla.fileback")

# Regex to extract YAML frontmatter from a markdown file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _extract_frontmatter(content: str) -> dict:
    """Extract YAML-like frontmatter fields from article content.

    Does a simple key: value parse to avoid requiring PyYAML.
    Handles list values (lines starting with ``-``).
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    result = {}
    current_key = None
    current_list = None

    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # List item under the current key
        if stripped.startswith("- ") and current_key:
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(stripped[2:].strip())
            continue

        # Key: value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            value = value.strip()
            current_list = None
            if value:
                result[current_key] = value
            else:
                result[current_key] = ""

    return result


def _extract_wikilinks(content: str) -> list[str]:
    """Return all [[wikilink]] targets found in content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "untitled"


async def execute_fileback(batch_id: str, config: VanillaConfig) -> dict:
    """
    Write approved articles from staging to wiki-vault/concepts/.

    Steps:
    1. Read batch from staging/batch_{id}/
    2. Copy approved .md files to wiki-vault/concepts/
    3. Update index.md with new article links
    4. Update graph.json with new nodes/edges + source_map
    5. Record sync writes so watcher doesn't re-trigger
    6. Clean up staging directory
    7. Update proposal status in DB

    Returns {"articles_written": int, "errors": list}
    """
    wiki_vault = config.wiki_vault_path
    if not wiki_vault:
        return {"articles_written": 0, "errors": ["No wiki vault configured"]}

    wiki_path = Path(wiki_vault)
    concepts_dir = wiki_path / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    staging_dir = wiki_path / "staging" / batch_id
    if not staging_dir.exists():
        return {"articles_written": 0, "errors": [f"Staging directory not found: {batch_id}"]}

    # Load graph
    graph = load_graph(wiki_vault)

    articles_written = 0
    errors = []
    written_articles = []  # Track for index update

    # Find all article .md files in staging (skip proposal.md)
    for md_file in staging_dir.glob("*.md"):
        if md_file.name == "proposal.md":
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            frontmatter = _extract_frontmatter(content)

            title = frontmatter.get("title", md_file.stem)
            category = frontmatter.get("category", "general")
            sources = frontmatter.get("sources", [])
            if isinstance(sources, str):
                sources = [sources]

            # Copy to concepts directory
            dest_path = concepts_dir / md_file.name
            dest_path.write_text(content, encoding="utf-8")

            # Record sync write to prevent watcher re-trigger
            relative_dest = normalize_path(
                f"wiki-vault/concepts/{md_file.name}"
            )
            repo.record_sync_write(relative_dest)

            # Update graph: add node
            node_id = _slugify(title)
            add_node(
                graph,
                node_id=node_id,
                label=title,
                path=relative_dest,
                category=category,
                batch_id=batch_id,
            )

            # Update graph: add source citations
            for source in sources:
                source_normalized = normalize_path(source)
                add_source_citation(graph, source_normalized, relative_dest)

            # Update graph: add edges from wikilinks
            wikilinks = _extract_wikilinks(content)
            for link_target in wikilinks:
                target_id = _slugify(link_target)
                add_edge(graph, source=node_id, target=target_id)

            # Update FTS index
            repo.upsert_fts(relative_dest, "wiki", title, content)

            # Clear stale flags for this article if any
            repo.clear_stale_article(relative_dest)

            # Update individual article status
            repo.update_article_status(batch_id, md_file.name, "approved")

            written_articles.append({"title": title, "filename": md_file.name})
            articles_written += 1

            logger.info("Wrote article: %s -> %s", md_file.name, dest_path)

        except Exception as e:
            error_msg = f"Error processing {md_file.name}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    # Save updated graph
    save_graph(wiki_vault, graph)
    repo.record_sync_write(normalize_path("wiki-vault/graph.json"))

    # Update index.md
    _update_index(wiki_path, written_articles)
    repo.record_sync_write(normalize_path("wiki-vault/index.md"))

    # Update proposal status in DB
    repo.update_proposal_status(batch_id, "approved")

    # Clean up staging directory
    try:
        shutil.rmtree(staging_dir)
        logger.info("Cleaned up staging directory: %s", staging_dir)
    except OSError as e:
        logger.warning("Could not clean staging dir %s: %s", staging_dir, e)

    logger.info(
        "Fileback complete for %s: %d articles written, %d errors",
        batch_id,
        articles_written,
        len(errors),
    )

    return {"articles_written": articles_written, "errors": errors}


def _update_index(wiki_path: Path, new_articles: list[dict]) -> None:
    """Append new articles to wiki-vault/index.md."""
    index_path = wiki_path / "index.md"

    if not new_articles:
        return

    # Read existing index
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
    else:
        existing = "# Wiki Index\n\n*Auto-maintained by the File-back Agent. Do not edit manually.*\n\n## Concepts\n"

    # Append new entries
    new_lines = []
    for art in new_articles:
        link = f"- [[{art['title']}]] — `concepts/{art['filename']}`"
        # Avoid duplicates
        if link not in existing:
            new_lines.append(link)

    if new_lines:
        updated = existing.rstrip() + "\n" + "\n".join(new_lines) + "\n"
        index_path.write_text(updated, encoding="utf-8")
