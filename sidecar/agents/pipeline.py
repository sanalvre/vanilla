"""
VanillaFlow — orchestrates the 4-agent pipeline.

Triggered by file changes (via on_file_ready callback) or manual /agent/run-now.
Chains: collect_changed_files -> ingest_step -> analysis_step -> proposal_step.
File-back runs separately on approval.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
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
    get_articles_citing,
)
from services.paths import normalize_path

logger = logging.getLogger("vanilla.pipeline")


class AgentPipelineStatus:
    """Tracks the current state of the pipeline for /status endpoint."""

    def __init__(self):
        self.running = False
        self.current_phase: Optional[str] = None  # "ingest" | "analysis" | "proposal"
        self.current_run_id: Optional[str] = None
        self.total_tokens = 0


pipeline_status = AgentPipelineStatus()

# Maximum characters of file content to send per file in the ingest prompt.
# Roughly 2000 tokens * 4 chars/token = 8000 chars.
_MAX_FILE_CHARS = 8000


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token per 4 characters."""
    return max(1, len(text) // 4)


def _check_token_budget(config: VanillaConfig) -> None:
    """Raise if total_tokens exceeds the configured safety limit."""
    limit = config.llm.max_tokens_per_run
    if pipeline_status.total_tokens > limit:
        raise RuntimeError(
            f"Token budget exceeded: {pipeline_status.total_tokens} > {limit}"
        )


def _parse_json_response(raw: str) -> object:
    """Extract a JSON object or array from an LLM response, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        match = re.search(r"[\[{][\s\S]*[\]}]", cleaned)
        if match:
            return json.loads(match.group())
        raise ValueError(f"LLM did not return valid JSON: {cleaned[:300]}")


def _slugify(text: str) -> str:
    """Convert a concept name to a filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "untitled"


# ─── Main Pipeline Entry Point ─────────────────────────────────────


async def run_pipeline(
    changed_paths: list[str],
    config: VanillaConfig,
) -> str:
    """
    Run the full pipeline for a set of changed file paths.

    Returns the run_id.
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    trigger_path = changed_paths[0] if changed_paths else None

    pipeline_status.running = True
    pipeline_status.current_run_id = run_id
    pipeline_status.total_tokens = 0

    repo.create_agent_run(run_id, trigger_path=trigger_path)

    try:
        # Step 1: Ingest — read changed files, produce summaries
        pipeline_status.current_phase = "ingest"
        ingest_results = await ingest_step(changed_paths, config, run_id)

        if not ingest_results:
            logger.info("No content to process after ingest step")
            repo.complete_agent_run(
                run_id, status="complete", tokens_used=pipeline_status.total_tokens
            )
            return run_id

        # Step 2: Analysis — compare against existing wiki, determine actions
        pipeline_status.current_phase = "analysis"
        analysis_results = await analysis_step(ingest_results, config, run_id)

        if not analysis_results:
            logger.info("No actions recommended by analysis")
            repo.complete_agent_run(
                run_id, status="complete", tokens_used=pipeline_status.total_tokens
            )
            return run_id

        # Step 3: Proposal — generate draft articles
        pipeline_status.current_phase = "proposal"
        await proposal_step(analysis_results, config, run_id)

        repo.complete_agent_run(
            run_id, status="complete", tokens_used=pipeline_status.total_tokens
        )
        logger.info(
            "Pipeline complete: %s (tokens: %d)", run_id, pipeline_status.total_tokens
        )

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        repo.complete_agent_run(
            run_id,
            status="error",
            error_msg=str(e),
            tokens_used=pipeline_status.total_tokens,
        )
    finally:
        pipeline_status.running = False
        pipeline_status.current_phase = None
        pipeline_status.current_run_id = None

    return run_id


# ─── Step 1: Ingest ────────────────────────────────────────────────


INGEST_SYSTEM_PROMPT = """\
You are a document analysis agent. Read the following document and output a JSON with:
- "title": document title (infer from content if not explicit)
- "topics": list of 3-5 topic tags
- "summary": 2-3 sentence summary of key concepts
- "key_concepts": list of named concepts/entities worth tracking

Return ONLY valid JSON.\
"""


async def ingest_step(
    changed_paths: list[str],
    config: VanillaConfig,
    run_id: str,
) -> list[dict]:
    """
    Read each changed file, send to LLM for topic extraction and summary.

    Returns list of dicts: {path, title, topics, summary, key_concepts}
    """
    results = []
    vault_root = ""
    if config.clean_vault_path:
        vault_root = str(Path(config.clean_vault_path).parent)

    for rel_path in changed_paths:
        _check_token_budget(config)

        # Resolve to absolute path
        if vault_root:
            abs_path = str(Path(vault_root) / rel_path)
        else:
            abs_path = rel_path

        # Read file content
        try:
            content = Path(abs_path).read_text(encoding="utf-8", errors="replace")
        except (OSError, FileNotFoundError):
            logger.warning("Cannot read file for ingest: %s", abs_path)
            continue

        if not content.strip():
            logger.debug("Skipping empty file: %s", rel_path)
            continue

        # Truncate to fit token budget
        truncated = content[:_MAX_FILE_CHARS]

        messages = [
            {"role": "system", "content": INGEST_SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ]

        model = config.llm.models.get("ingest", "gpt-4o-mini")
        try:
            raw = await chat_completion(
                provider=config.llm.provider,
                api_key=config.llm.api_key,
                model=model,
                messages=messages,
                base_url=config.llm.base_url,
                max_tokens=2000,
                temperature=0.3,
            )
        except Exception as e:
            logger.error("Ingest LLM call failed for %s: %s", rel_path, e)
            continue

        # Track tokens
        prompt_text = INGEST_SYSTEM_PROMPT + truncated
        pipeline_status.total_tokens += _estimate_tokens(prompt_text) + _estimate_tokens(raw)

        try:
            parsed = _parse_json_response(raw)
            if isinstance(parsed, dict):
                results.append({
                    "path": normalize_path(rel_path),
                    "title": parsed.get("title", "Untitled"),
                    "topics": parsed.get("topics", []),
                    "summary": parsed.get("summary", ""),
                    "key_concepts": parsed.get("key_concepts", []),
                })
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Failed to parse ingest response for %s: %s", rel_path, e)
            continue

    logger.info("Ingest step complete: %d files processed", len(results))
    return results


# ─── Step 2: Analysis ──────────────────────────────────────────────


ANALYSIS_SYSTEM_PROMPT = """\
You are a knowledge-base analysis agent for Vanilla. Your job is to compare \
newly ingested source material against the existing wiki and determine what \
actions to take.

You will receive:
1. Summaries of newly ingested documents
2. The list of existing wiki article titles
3. The ontology rules
4. A list of stale articles (articles whose source material has changed)

Determine which wiki articles should be created or updated.

Output a JSON array of action objects. Each action:
{
  "action": "create" or "update",
  "concept": "Concept Name",
  "reason": "Why this article should be created/updated",
  "sources": ["clean-vault/raw/source-file.md"],
  "category": "category-name"
}

If no actions are needed, return an empty array: []

Return ONLY valid JSON.\
"""


async def analysis_step(
    ingest_results: list[dict],
    config: VanillaConfig,
    run_id: str,
) -> list[dict]:
    """
    Compare ingest results against existing wiki state and determine actions.

    Returns list of action dicts: {action, concept, reason, sources, category}
    """
    _check_token_budget(config)

    wiki_vault = config.wiki_vault_path
    if not wiki_vault:
        logger.warning("No wiki vault configured, skipping analysis")
        return []

    # Load current graph to get existing article titles
    graph = load_graph(wiki_vault)
    existing_articles = [node.get("label", node["id"]) for node in graph.get("nodes", [])]

    # Read ontology.md (always re-read, never cached)
    ontology_content = ""
    ontology_path = Path(wiki_vault) / "ontology.md"
    if ontology_path.exists():
        try:
            ontology_content = ontology_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Read AGENTS.md (always re-read, never cached)
    agents_content = ""
    agents_path = Path(wiki_vault) / "AGENTS.md"
    if agents_path.exists():
        try:
            agents_content = agents_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Get stale articles
    stale_articles = repo.get_stale_articles()
    stale_list = [
        {"article": s["article_path"], "changed_source": s["source_path"]}
        for s in stale_articles
    ]

    # Build the user message
    user_parts = []
    user_parts.append("## Newly Ingested Documents\n")
    for r in ingest_results:
        user_parts.append(f"### {r['title']}")
        user_parts.append(f"- Source: {r['path']}")
        user_parts.append(f"- Topics: {', '.join(r['topics'])}")
        user_parts.append(f"- Summary: {r['summary']}")
        user_parts.append(f"- Key concepts: {', '.join(r['key_concepts'])}")
        user_parts.append("")

    user_parts.append("## Existing Wiki Articles\n")
    if existing_articles:
        for title in existing_articles:
            user_parts.append(f"- {title}")
    else:
        user_parts.append("(No articles exist yet)")
    user_parts.append("")

    user_parts.append("## Ontology Rules\n")
    user_parts.append(ontology_content or "(No ontology defined)")
    user_parts.append("")

    user_parts.append("## Agent Constitution\n")
    user_parts.append(agents_content or "(No agent constitution defined)")
    user_parts.append("")

    user_parts.append("## Stale Articles\n")
    if stale_list:
        for s in stale_list:
            user_parts.append(f"- {s['article']} (source changed: {s['changed_source']})")
    else:
        user_parts.append("(No stale articles)")

    user_message = "\n".join(user_parts)

    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    model = config.llm.models.get("analysis", "gpt-4o-mini")
    raw = await chat_completion(
        provider=config.llm.provider,
        api_key=config.llm.api_key,
        model=model,
        messages=messages,
        base_url=config.llm.base_url,
        max_tokens=4096,
        temperature=0.3,
    )

    # Track tokens
    prompt_text = ANALYSIS_SYSTEM_PROMPT + user_message
    pipeline_status.total_tokens += _estimate_tokens(prompt_text) + _estimate_tokens(raw)

    try:
        parsed = _parse_json_response(raw)
        if isinstance(parsed, list):
            actions = parsed
        elif isinstance(parsed, dict) and "actions" in parsed:
            actions = parsed["actions"]
        else:
            actions = []
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse analysis response: %s", e)
        actions = []

    logger.info("Analysis step complete: %d actions recommended", len(actions))
    return actions


# ─── Step 3: Proposal ──────────────────────────────────────────────


PROPOSAL_SYSTEM_PROMPT = """\
You are a wiki article writer for Vanilla. Write a well-structured Markdown \
article for a knowledge base.

The article MUST begin with YAML frontmatter in exactly this format:

```yaml
---
title: {concept}
category: {category}
sources:
{sources_yaml}
created_by: vanilla-agent
batch_id: {batch_id}
status: draft
---
```

After the frontmatter, write a clear, informative article about the concept. \
Include:
- A concise introduction
- Key details and explanations
- Use [[wikilinks]] to reference related concepts when appropriate
- Keep it factual and well-sourced

Return the COMPLETE article including frontmatter. No extra explanation.\
"""


async def proposal_step(
    analysis_results: list[dict],
    config: VanillaConfig,
    run_id: str,
) -> None:
    """
    For each recommended action, generate a draft article and write to staging.
    Creates proposal records in the database.
    """
    wiki_vault = config.wiki_vault_path
    if not wiki_vault:
        logger.warning("No wiki vault configured, skipping proposal step")
        return

    batch_id = f"batch_{run_id}"
    staging_dir = Path(wiki_vault) / "staging" / batch_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    articles_written = []

    for action in analysis_results:
        _check_token_budget(config)

        concept = action.get("concept", "Untitled")
        category = action.get("category", "general")
        reason = action.get("reason", "")
        sources = action.get("sources", [])
        action_type = action.get("action", "create")

        # Build sources YAML block
        sources_yaml = "\n".join(f"  - {s}" for s in sources) if sources else "  - unknown"

        # Build the prompt with placeholders filled in
        system_prompt = PROPOSAL_SYSTEM_PROMPT.format(
            concept=concept,
            category=category,
            sources_yaml=sources_yaml,
            batch_id=batch_id,
        )

        user_message = (
            f"Write a wiki article about: {concept}\n\n"
            f"Action: {action_type}\n"
            f"Reason: {reason}\n"
            f"Category: {category}\n"
            f"Sources: {', '.join(sources)}\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        model = config.llm.models.get("proposal", "gpt-4o")
        try:
            article_content = await chat_completion(
                provider=config.llm.provider,
                api_key=config.llm.api_key,
                model=model,
                messages=messages,
                base_url=config.llm.base_url,
                max_tokens=4096,
                temperature=0.5,
            )
        except Exception as e:
            logger.error("Proposal LLM call failed for %s: %s", concept, e)
            continue

        # Track tokens
        prompt_text = system_prompt + user_message
        pipeline_status.total_tokens += _estimate_tokens(prompt_text) + _estimate_tokens(
            article_content
        )

        # Write article file to staging
        slug = _slugify(concept)
        filename = f"{slug}.md"
        article_path = staging_dir / filename
        article_path.write_text(article_content, encoding="utf-8")

        articles_written.append({
            "filename": filename,
            "title": concept,
            "action": action_type,
            "slug": slug,
        })

    if not articles_written:
        logger.info("No proposal articles generated")
        return

    # Write proposal.md summary
    summary_lines = [
        f"# Proposal: {batch_id}\n",
        f"Run ID: {run_id}",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## Articles\n",
    ]
    for art in articles_written:
        summary_lines.append(f"- **{art['title']}** ({art['action']}) — `{art['filename']}`")

    proposal_md = "\n".join(summary_lines) + "\n"
    (staging_dir / "proposal.md").write_text(proposal_md, encoding="utf-8")

    # Record in database
    batch_path = normalize_path(str(staging_dir))
    summary_text = f"{len(articles_written)} article(s): " + ", ".join(
        a["title"] for a in articles_written
    )
    repo.create_proposal(batch_id, batch_path, summary_text)

    for art in articles_written:
        repo.add_proposal_article(
            batch_id, art["filename"], art["title"], action=art["action"]
        )

    logger.info(
        "Proposal step complete: batch %s with %d articles",
        batch_id,
        len(articles_written),
    )
