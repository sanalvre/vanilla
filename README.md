# Vanilla

A local-first knowledge base where AI agents do the filing.

Drop in documents. Agents read them, extract concepts, and propose structured wiki articles. You approve. Over time, your knowledge base grows into a graph your agents can actually navigate — not just search.

---

## Why this exists

Most RAG setups treat a knowledge base as a static pile of embeddings. Query comes in, nearest chunks come out. It works, but it doesn't compound — each query starts from scratch, with no awareness of what the system already knows.

Vanilla takes a different approach: agents actively maintain a **wiki** alongside your raw documents. Every approved article is a clean, deduplicated, cross-referenced piece of knowledge. The wiki grows with your vault. Future agent runs have richer context because they're reading synthesized understanding, not just raw chunks.

### Why markdown

Markdown is the natural language of agents. LLMs were trained on it, generate it fluently, and can reason about its structure without special parsers. Vanilla leans into this:

- Every knowledge article is a plain `.md` file with YAML frontmatter
- Relationships between concepts are expressed as `[[wikilinks]]` — readable by humans, parseable by machines
- The entire wiki is diffable, versionable, and portable — no database lock-in for your content
- You can open, edit, and search your vault in any editor (Obsidian, VS Code, etc.)

### Why the knowledge graph matters

The graph is not decoration. It's the index the agents use to think:

- **Hub detection** — concepts with many connections get larger context windows in future agent runs, because they're load-bearing ideas
- **Multi-hop traversal** — when analyzing a new document, agents don't just find similar articles by vector similarity; they also pull in graph neighbors, catching conceptual relationships that embeddings miss
- **Stale tracking** — when a source document changes, the graph knows which articles cited it and flags them for review
- **Degree-weighted search** — central concepts rank slightly higher in retrieval, matching how importance actually distributes in a knowledge domain

---

## How it works

```
You drop a file into clean-vault/
        ↓
Watcher detects the change (5-minute debounce)
        ↓
Ingest agent   — reads the file, extracts topics and a summary
Analysis agent — reads your existing wiki + graph, decides what to create or update
Proposal agent — drafts articles and writes them to a staging queue
        ↓
You review proposals and approve or reject each batch (one click)
        ↓
File-back agent — writes approved articles to wiki-vault/concepts/
                — updates the knowledge graph (nodes, edges, citations)
                — generates embeddings for future retrieval
                — updates the concept index
        ↓
Next run has richer context. The graph compounds.
```

### Vault structure

```
your-vault/
├── clean-vault/           # Your source documents (read-only for agents)
│   ├── raw/               # PDFs converted to markdown, scraped URLs
│   └── notes/             # Your own writing
└── wiki-vault/            # Agent-maintained knowledge base
    ├── concepts/          # One article per concept, approved by you
    │   └── transformer-architecture.md
    ├── staging/           # Pending proposals, waiting for your review
    ├── ontology.md        # Your domain schema — agents read this every run
    └── AGENTS.md          # Agent constitution — rules, article format, schema
```

The clean vault is yours. The wiki vault is the agents'. You're the editor-in-chief.

### Article format

Every wiki article is a plain markdown file:

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
status: approved
confidence: high
---

The Transformer is a sequence-to-sequence model that replaces recurrence
with [[Self-Attention]], enabling parallelization across positions...

## See also
- [[BERT]]
- [[Large Language Models]]
```

`[[wikilinks]]` automatically become graph edges. Typed relationships (`uses`, `is-a`, `derived-from`, `extends`, `contrasts-with`, `implements`, `part-of`) carry semantic meaning in traversal.

---

## Quick start

### Prerequisites

- Node.js 20+
- Python 3.10+
- Rust — [rustup.rs](https://rustup.rs)
- An API key: OpenAI, Anthropic, OpenRouter, or a local Ollama instance

### Install

```bash
git clone https://github.com/sanalvre/vanilla
cd vanilla

# Frontend dependencies
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

### Run in development

```bash
npm run tauri dev
```

### Build installer

```bash
npm run tauri build
# Windows: src-tauri/target/release/bundle/nsis/VanillaDB_0.1.0_x64-setup.exe
# macOS:   src-tauri/target/release/bundle/dmg/VanillaDB_0.1.0_x64.dmg
```

---

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
```

The Python sidecar binds to a random localhost port and is the sole owner of SQLite. The Tauri shell reads the port on startup and configures the React frontend to talk to it. Nothing leaves your machine unless you configure a git remote.

---

## LLM configuration

Config lives in `~/.vanilla/config.json`, created on first run via the in-app settings panel.

| Provider | Notes |
|----------|-------|
| OpenAI | `gpt-4o-mini` for ingest/analysis, `gpt-4o` for proposals |
| Anthropic | Claude Haiku for ingest, Claude Opus for proposals |
| OpenRouter | Any model via a single unified API |
| Ollama | Fully local — set base URL to `http://localhost:11434` |

**Embedding models**

| Model | Dims | Notes |
|-------|------|-------|
| `text-embedding-3-small` | 1536 | OpenAI — recommended |
| `nomic-embed-text` | 768 | Ollama — free, local |
| `mxbai-embed-large` | 1024 | Ollama — higher quality |

---

## Agent API

The sidecar exposes a REST API on a dynamic local port, printed to stdout on startup as `VANILLA_PORT:<n>`. Other agents and tools can query your knowledge base directly.

### Context retrieval

```http
GET /context?q=transformer+attention&k=5
```

Returns formatted context ready to inject into a prompt — full article content, ranked by hybrid BM25 + semantic similarity with Reciprocal Rank Fusion.

```json
{
  "context": "## Transformer Architecture\n...\n\n---\n\n## Self-Attention\n...",
  "sources": [
    {"path": "wiki-vault/concepts/transformer-architecture.md", "score": 0.91}
  ]
}
```

### Knowledge graph traversal

```http
GET /wiki/graph/concepts                            # All concepts
GET /wiki/graph/concepts/{id}                       # Concept + article + relationships
GET /wiki/graph/concepts/{id}/neighbors?depth=1     # Graph neighbors
GET /wiki/graph/concepts/{id}/neighbors?type=uses   # Filter by relationship type
```

### Ingest

```http
POST /ingest/file   {"file_path": "/absolute/path/to/doc.pdf"}
POST /ingest/url    {"url": "https://example.com/paper"}
GET  /ingest/status/{job_id}
```

---

## MCP integration

Vanilla ships an MCP server so Claude Desktop (and any MCP-compatible agent) can use your knowledge base as a native tool.

```bash
pip install fastmcp
VANILLA_URL=http://127.0.0.1:PORT python sidecar/mcp_server.py
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "vanilla": {
      "command": "python",
      "args": ["/path/to/vanilla/sidecar/mcp_server.py"],
      "env": { "VANILLA_URL": "http://127.0.0.1:YOUR_PORT" }
    }
  }
}
```

**Tools exposed:**

| Tool | What it does |
|------|-------------|
| `search_knowledge(query, k)` | Hybrid semantic + keyword search across the wiki |
| `get_context(query, k)` | RAG retrieval formatted for direct prompt injection |
| `get_related_concepts(concept, type)` | Traverse the knowledge graph from a concept |
| `list_concepts(category)` | Browse all concepts, optionally filtered by category |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, architecture notes, and contribution guidelines.

## License

MIT
