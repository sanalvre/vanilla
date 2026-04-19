# VanillaDB

An agent-native desktop knowledge base. Drop in documents, let AI agents extract concepts and build a knowledge graph, then explore and edit your vault.

## What it does

1. **Ingest** — drop PDFs, markdown files, or URLs into your vault. An AI pipeline extracts concepts, topics, and summaries.
2. **Analyze** — agents compare new content against your existing knowledge graph and determine what to create or update.
3. **Propose** — draft articles land in a staging queue. You review and approve or reject each batch.
4. **Write** — approved articles are written to your wiki vault with structured frontmatter, relationships, and source citations.
5. **Explore** — browse your vault with a force-directed knowledge graph, search semantically, and edit articles inline.

## Architecture

```
┌──────────────────────────────────────┐
│  Tauri Desktop Shell (Rust)          │
│  ┌────────────────┐                  │
│  │  React + Vite  │  ← UI           │
│  └────────────────┘                  │
│          ↕ localhost HTTP            │
│  ┌──────────────────────────────┐   │
│  │  Python Sidecar (FastAPI)    │   │
│  │  • Agent pipeline (CrewAI)   │   │
│  │  • SQLite + FTS5 + vectors   │   │
│  │  • Hybrid search (BM25+ANN)  │   │
│  │  • Git sync                  │   │
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
          ↕
  ~/your-vault/
  ├── clean-vault/     ← source documents
  └── wiki-vault/      ← generated knowledge base
      ├── concepts/    ← approved articles
      ├── staging/     ← pending proposals
      ├── ontology.md  ← your domain schema
      └── AGENTS.md    ← agent instructions
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.10+
- Rust: https://rustup.rs
- An LLM API key (OpenAI, Anthropic, OpenRouter, or local Ollama)

### Install

```bash
git clone https://github.com/sanalvre/vanilla
cd vanilladb

# Frontend
npm install

# Python sidecar
cd sidecar
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[agents,ingestion]"
cd ..
```

### Build the sidecar binary

```bash
cd sidecar
pyinstaller vanilla.spec
cd ..

# Copy to Tauri's expected location
# Windows:
copy sidecar\dist\vanilla-sidecar.exe src-tauri\binaries\vanilla-sidecar-x86_64-pc-windows-msvc.exe
# macOS:
cp sidecar/dist/vanilla-sidecar src-tauri/binaries/vanilla-sidecar-x86_64-apple-darwin
```

### Development

```bash
npm run tauri dev
```

### Build installer

```bash
npm run tauri build
# Windows: src-tauri/target/release/bundle/nsis/VanillaDB_0.1.0_x64-setup.exe
# macOS:   src-tauri/target/release/bundle/dmg/VanillaDB_0.1.0_x64.dmg
```

## LLM Configuration

VanillaDB stores config in `~/.vanilla/config.json`, created on first run via the in-app settings panel.

| Provider | Notes |
|----------|-------|
| OpenAI | Recommended. Uses `gpt-4o-mini` for ingest/analysis, `gpt-4o` for proposals |
| Anthropic | Claude Haiku for ingest, Claude Sonnet for proposals |
| OpenRouter | Any model via unified API |
| Ollama | Fully local — set base URL to `http://localhost:11434` |

### Embedding models

| Model | Dims | Provider |
|-------|------|----------|
| `text-embedding-3-small` | 1536 | OpenAI (recommended) |
| `nomic-embed-text` | 768 | Ollama (free, local) |
| `mxbai-embed-large` | 1024 | Ollama (higher quality) |

## Agent API

The sidecar exposes a REST API on a dynamic local port. The port is printed to stdout on startup (`VANILLA_PORT:<n>`) and can also be read from `~/.vanilla/config.json` after first run.

### Context retrieval (RAG)

```http
GET /context?q=transformer+attention&k=5
```

Returns formatted context from the knowledge base, ready to inject into a prompt. Unlike `/search`, this returns actual article content ranked by relevance.

```json
{
  "context": "## Transformer Architecture\n...\n\n---\n\n## Self-Attention\n...",
  "sources": [
    {"path": "wiki-vault/concepts/transformer-architecture.md", "title": "Transformer Architecture", "score": 0.91}
  ]
}
```

### Semantic search

```http
GET /search?q=neural+networks&vault=wiki&limit=10
```

Hybrid BM25 + semantic search with Reciprocal Rank Fusion. Returns ranked results with snippets.

### Knowledge graph traversal

```http
GET /wiki/graph/concepts                           # List all concepts
GET /wiki/graph/concepts/{id}                      # Concept + full article content + relationships
GET /wiki/graph/concepts/{id}/neighbors?depth=1    # Related concepts (depth 1 or 2)
GET /wiki/graph/concepts/{id}/neighbors?type=uses  # Filter by relationship type
```

### Ingest

```http
POST /ingest/file?file_path=/absolute/path/to/doc.pdf
POST /ingest/url   {"url": "https://example.com/paper"}
GET  /ingest/status/{job_id}
```

## MCP Integration

VanillaDB ships an MCP server so AI agents and Claude Desktop can use your knowledge base as a native tool.

```bash
pip install fastmcp

# Set the port printed by the running sidecar
VANILLA_URL=http://127.0.0.1:PORT python sidecar/mcp_server.py
```

**Tools exposed:**

| Tool | Description |
|------|-------------|
| `search_knowledge(query, k)` | Hybrid semantic + keyword search |
| `get_context(query, k)` | RAG retrieval formatted for prompt injection |
| `get_related_concepts(concept, type)` | Traverse the knowledge graph |
| `list_concepts(category)` | Browse all concepts, optionally filtered by category |

**Claude Desktop config** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "vanilladb": {
      "command": "python",
      "args": ["/path/to/vanilladb/sidecar/mcp_server.py"],
      "env": {
        "VANILLA_URL": "http://127.0.0.1:YOUR_PORT"
      }
    }
  }
}
```

## Vault structure

```
your-vault/
├── clean-vault/           # Source documents (PDF, markdown, web pages)
│   └── raw/
└── wiki-vault/
    ├── concepts/          # Approved knowledge base articles
    │   └── concept-name.md
    ├── staging/           # Pending agent proposals (per-batch subdirs)
    ├── ontology.md        # Define your domain's categories and relationships
    └── AGENTS.md          # Instructions for the agent pipeline
```

### Article format

```markdown
---
title: Transformer Architecture
category: model
sources:
  - clean-vault/raw/attention-is-all-you-need.md
relationships:
  - target: Self-Attention
    type: uses
  - target: BERT
    type: derived-from
created_by: vanilla-agent
---

Article body in plain markdown...
```

### Relationship types

`uses` · `is-a` · `derived-from` · `extends` · `contrasts-with` · `implements` · `part-of` · `related-to`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, workflow, and contribution guidelines.

## License

MIT
