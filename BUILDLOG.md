# Vanilla Build Log

Reverse-chronological log of all development activity. This is the primary context source for any agent or developer picking up work on this project.

---

## 2026-04-14 — [Phase 9.0] LLM Configuration UI + UI Polish

**What changed:**

Backend:
- `sidecar/main.py` — new `GET /llm/config` endpoint returns current provider, masked API key, model map, token limit
- `src/api/sidecar.ts` — `getLLMConfig()`, `validateLLM()`, `LLMConfig` interface

Phase 9 UI:
- `src/components/settings/SettingsPanel.tsx` — slide-in settings panel: provider picker (OpenAI/Anthropic/OpenRouter/Ollama), API key input with show/hide toggle, model selector, Ollama base URL, "Test & Save" button with spinner, success/error feedback, key masked in status banner, escape to close
- `src/App.tsx` — gear icon button in top-right header opens SettingsPanel; `settingsOpen` state

UI Polish (from audit):
- `FileTree.tsx` — loading skeleton (5 shimmer rows), `transition-colors` on all buttons, `aria-expanded` on folders, `aria-current="page"` on active file, `focus-visible:ring-1` keyboard nav, better empty state with hint text, slimmer font (text-xs throughout), improved file icon colors
- `EditorPanel.tsx` — spinner on loading instead of text, document icon on empty state, breadcrumb with tooltip on truncated path, status indicators right-aligned, read-only badge downsized, cleaner min-w-0 flex handling
- `IngestStatus.tsx` — completed jobs linger 2.5s then expire (no abrupt disappearance), thinner progress bar (h-0.5), green fill on complete, truncated error with full title tooltip, border-top separator, distinct section label sizing
- `UrlBar.tsx` — inline spinner in input field on loading, cancel X button with SVG icon, disabled state prevents double-submit, transition-colors on all interactive elements
- `ResizableSplit.tsx` — `role="separator"` + `aria-orientation` + `aria-label` for accessibility, `isDragging` ref prevents stale closure, min/max clamping in drag handler
- `SearchPanel.tsx` — distinguishes error state from empty results (different messages + red color), improved filter tab contrast (stone-600), SVG close button with proper hover state

Styling:
- `src/styles/main.css` — `mark` highlight style for FTS snippets (amber bg)

**Tests:** All 194 Python + 14 TypeScript tests passing. Zero TS errors.

**Next:** Phase 10 — Cloud Sync (or skip to Phase 11 packaging)

---

## 2026-04-14 — [Phase 8.0] Full-Text Search UI

**What changed:**
- `src/components/layout/SearchPanel.tsx` — NEW: sidebar-integrated FTS search panel; debounced input (180ms), vault filter tabs (All / Vault / Wiki), ranked result cards with title + snippet, amber wiki badge vs. stone vault badge, auto-focus on open, ✕ to return to file tree
- `src/components/layout/Logo.tsx` — Redesigned: vanilla flower/plant SVG icon (5-petal orchid with amber centre, stem + leaves + vanilla bean pod) replacing the abstract network icon
- `src/App.tsx` — Sidebar now has a Search toggle button at the top; file tree swaps to SearchPanel when active; `Ctrl+Shift+F` keyboard shortcut added
- `src/styles/main.css` — `<mark>` highlight style for FTS snippet matches (amber background)

**Decisions:**
- Search lives in the sidebar (not a modal/overlay) — keeps the graph + editor fully visible while reading results
- File tree swaps out for search results rather than stacking — sidebar stays a fixed 224px; no layout shift
- Snippets rendered via `dangerouslySetInnerHTML` for `<mark>` highlights — safe because the backend generates them from FTS5's `snippet()` function, no user HTML
- Filter re-fires the search immediately on tab change so results stay fresh
- Backend `/search` + `repo.search_fts` were already implemented in Phase 5; Phase 8 is purely frontend

**Tests:** All 194 Python + 14 TypeScript tests passing. Zero TS errors. No new tests (search endpoint was already covered by Phase 5 integration tests).

**Next:** Phase 9 — LLM Configuration UI

---

## 2026-04-14 — [Phase 7.0] Rich UI: Editor, Graph, Command Palette

**What changed:**

Backend:
- `sidecar/main.py` — 3 new endpoints: `GET /vault/files` (combined directory tree), `GET /vault/file?path=` (read file content with traversal guard), `POST /vault/file` (write file, clean-vault only)
- `sidecar/models/responses.py` — 3 new Pydantic models: `FileTreeNode` (recursive), `FileContentResponse`, `FileWriteRequest`

Frontend stores & API:
- `src/api/sidecar.ts` — `getVaultFiles()`, `getFileContent()`, `saveFileContent()` + `FileTreeNode` interface
- `src/stores/editorStore.ts` — Zustand store: active file, dirty tracking, auto-save on switch, read-only for wiki files, graph visibility + split position persisted to localStorage
- `src/stores/graphStore.ts` — Zustand store: graph nodes/edges, latest batch detection, 30s polling

UI components (7 new files):
- `src/components/layout/FileTree.tsx` — recursive collapsible file tree with folder/file icons, auto-refresh every 15s, active file highlighting
- `src/components/editor/useCodemirror.ts` — CodeMirror 6 hook: creates/destroys EditorView, syncs external content without re-creating, custom warm-toned theme, markdown language support
- `src/components/editor/EditorPanel.tsx` — React.memo-isolated editor wrapper with breadcrumb bar, dirty indicator, read-only badge, Cmd+S save
- `src/components/graph/GraphPanel.tsx` — React.memo-isolated Reagraph visualization, custom theme matching app palette, highlights nodes from latest batch in amber, click-to-open articles
- `src/components/layout/ResizableSplit.tsx` — custom vertical drag splitter (pointer events, no deps), clamped 20-80%
- `src/components/command/CommandPalette.tsx` — cmdk overlay (Cmd+K): debounced file search, toggle graph, run agent, review proposals
- `src/App.tsx` — full rewire: sidebar with FileTree + IngestStatus, right pane with ResizableSplit (graph top / editor bottom) or ProposalPanel, lazy-loaded GraphPanel, global keyboard shortcuts (Cmd+Shift+G graph toggle, Cmd+Shift+P proposals), command palette overlay, streamlined top bar with graph toggle + palette button + connection dot

Styling:
- `src/styles/main.css` — CodeMirror height fill, subtle scrollbars, cmdk group heading styles

**Decisions:**
- CodeMirror 6 over Milkdown: lighter, more stable, CM manages its own DOM so React.memo isolation is natural
- GraphPanel lazy-loaded via React.lazy (Three.js is ~500KB, shouldn't block initial paint)
- Separate Zustand stores (editor, graph, vault, status) prevent cross-contamination of re-renders between graph and editor
- ResizableSplit is ~60 lines of custom code rather than pulling in react-resizable-panels
- Graph defaults to 50% of right pane, user-adjustable 20-80%, persisted to localStorage
- Command palette has only essential commands: file search, graph toggle, run agent, review proposals
- Sidebar is narrow (224px) to maximize content area
- File tree polls every 15s to pick up new ingested files without manual refresh

**Dependencies added:** `@codemirror/commands`

**Tests:** All 194 Python + 14 TypeScript tests passing. TypeScript compiles with zero errors. No new tests added (UI components are layout/rendering — testing strategy defers UI tests to E2E in Phase 11).

**Next:** Phase 8 — Full-Text Search UI, or continue to Phases 9-11

---

## 2026-04-14 — [Phase 6.0] Proposal Review UI

**What changed:**
- `sidecar/main.py` — new endpoint `GET /proposals/{batch_id}/article/{filename}`: reads staged article markdown for preview; includes path traversal guard (rejects filenames containing `/`, `\`, or starting with `.`)
- `src/api/sidecar.ts` — 3 new functions: `approveProposal()`, `rejectProposal()`, `getProposalArticle()`; added `batch_path` field to proposal type
- `src/components/proposals/ProposalPanel.tsx` — slide-in right panel: fetches all pending batches, shows count, auto-closes when queue empties, refresh on resolve triggers status store update
- `src/components/proposals/ProposalBatch.tsx` — per-batch card: summary, date, article list with action badges (create/update), inline preview load, approve all / reject buttons with busy/error states
- `src/components/proposals/ArticlePreview.tsx` — raw markdown viewer in a scrollable monospace pane, closes via ✕ button
- `src/App.tsx` — wired ProposalPanel into right pane; footer "N proposals pending" badge is now a clickable button that toggles the panel; `useEffect` auto-opens panel when `pendingProposals` transitions from 0 → N
- `src/components/layout/IngestStatus.tsx` — removed unused `useCallback` import (TS error cleanup)
- `src/stores/vaultStore.ts` — removed unused `get` param from zustand creator (TS error cleanup)

**Decisions:**
- Panel replaces the right-pane content viewer placeholder (Phase 7 will have the full viewer); clean toggle UX
- Article content read via dedicated endpoint rather than filesystem access from frontend — keeps all file access server-side
- Path traversal protection in the article endpoint: simple string check catches `..` attacks before `Path.exists()`
- Auto-open on proposal arrival felt natural (agents did work → show it); user can dismiss by closing the panel
- No markdown renderer yet — raw monospace view is readable and avoids pulling in a heavy dependency before Phase 7

**Tests:** 3 new integration tests for `GET /proposals/{batch_id}/article/{filename}` (happy path, 404, path traversal rejection). TypeScript compiles with zero errors.

**Next:** Phase 7 — Content viewer (file tree, markdown renderer, editor)

---

## 2026-04-14 — [Phase 5.0] Main Agent Pipeline

**What changed:**
- `sidecar/agents/pipeline.py` — Full 3-step pipeline orchestrator:
  - `AgentPipelineStatus` singleton tracks running state, current phase, run_id, total tokens
  - `run_pipeline()` chains ingest → analysis → proposal, records agent_run in DB
  - `ingest_step()` reads changed files, sends to LLM for topic extraction (model: `config.llm.models["ingest"]`, 2k token budget)
  - `analysis_step()` compares ingest results against wiki graph nodes, ontology.md, AGENTS.md (always re-read from disk), stale articles; LLM returns create/update actions
  - `proposal_step()` generates draft articles with YAML frontmatter, writes to `wiki-vault/staging/batch_{run_id}/`, creates proposal + proposal_articles DB records
  - Token safety valve aborts if `total_tokens > max_tokens_per_run` (default 20k)
  - Token estimation via `len(text) // 4` approximation
- `sidecar/agents/fileback.py` — File-back agent (approval handler):
  - `execute_fileback()` writes staging articles to `wiki-vault/concepts/`, updates graph.json (nodes, edges from wikilinks, source_map), updates index.md, records sync writes, clears stale flags, updates FTS, cleans up staging
  - Simple frontmatter parser (no PyYAML dependency)
  - Wikilink extraction for graph edge creation
- `sidecar/main.py` — Major updates:
  - `on_file_ready()` now triggers pipeline via `asyncio.create_task()` when not already running
  - `/status` returns dynamic `agent_status` from `pipeline_status`
  - `/agent/run-now` collects pending paths, suppresses individual triggers, runs consolidated pipeline
  - `POST /proposals/{batch_id}/approve` triggers fileback agent
  - `POST /proposals/{batch_id}/reject` marks batch as rejected
  - `_suppress_pipeline_trigger` flag prevents race during force dispatch
- `sidecar/models/responses.py` — 4 new models: ProposalApproveRequest, ProposalRejectRequest, ProposalActionResponse, RunPipelineResponse

**Decisions:**
- Pipeline runs as async task in the same process (no subprocess/worker) — simple, no IPC overhead
- Staging lives in `wiki-vault/staging/` (consistent with vault_manager's directory structure)
- Token counting is approximate (chars/4) — will upgrade to real litellm callback tracking when litellm is a hard dependency
- Force dispatch uses a suppress flag to avoid N pipeline runs for N pending files — instead runs one consolidated pipeline

**Tests:** 23 new tests:
- `tests/python/test_pipeline.py` — 16 tests: JSON parsing, slugify, token estimation, status state machine, frontmatter extraction, wikilink extraction, index.md updates
- `tests/python/integration/test_api.py` — 4 new: status reflects pipeline, approve/reject endpoint contracts
- All 191 Python + 14 TypeScript tests passing

**Next:** Phase 6 — Proposal review UI (diff viewer, approve/reject buttons, article preview)

---

## 2026-04-14 — [Phase 4.0] Onboarding Flow

**What changed:**
- `sidecar/services/llm_service.py` — provider-agnostic LLM service: `validate_connection()` tests reachability (Ollama via /api/tags, cloud providers via tiny chat completion), `chat_completion()` for actual LLM calls. Uses litellm when installed, falls back to raw httpx against OpenAI-compatible endpoints. Supports OpenAI, Anthropic, OpenRouter, Ollama with correct URL/header routing.
- `sidecar/agents/setup_crew.py` — generates ontology.md + AGENTS.md from user's vault description via a structured system prompt. Robust JSON parsing handles code fences, surrounding text, and missing fields. Ready to upgrade to full CrewAI crew later.
- `sidecar/main.py` — 2 new endpoints: `POST /llm/validate` (tests connection + saves config on success), `POST /onboarding/generate-ontology` (calls setup crew, returns ontology/agents/categories)
- `sidecar/models/responses.py` — added `model` field to LLMValidateRequest, new OnboardingGenerateRequest/Response models
- `src/api/onboarding.ts` — typed API client: `validateLLM()`, `generateOntology()`
- `src/components/onboarding/OnboardingFlow.tsx` — 5-step wizard with step indicator dots, shared state flow between steps
- `src/components/onboarding/ApiKeyStep.tsx` — provider dropdown, API key input, model selector with per-provider defaults, Ollama base_url, test connection with feedback
- `src/components/onboarding/DescriptionStep.tsx` — free-text area with 20-char minimum and character counter
- `src/components/onboarding/GeneratingStep.tsx` — auto-calls LLM on mount, spinner, error/retry handling
- `src/components/onboarding/ReviewStep.tsx` — editable ontology textarea, removable/editable category chips
- `src/components/onboarding/FolderSelectStep.tsx` — Tauri native folder dialog, vault creation with ontology/agents content
- `src/App.tsx` — replaced placeholder onboarding div with `<OnboardingFlow>` component

**Decisions:**
- Setup crew uses direct LLM call (not CrewAI) for simplicity — single prompt returns structured JSON. Can upgrade to multi-agent crew later if needed.
- LLM service has litellm as optional dependency — httpx fallback ensures the app works without it installed
- Anthropic httpx fallback routes through OpenAI-compatible endpoint (litellm handles native Anthropic API when available)
- Config saved on successful LLM validation so it persists across restarts

**Tests:** 11 new tests:
- `tests/python/test_setup_crew.py` — 8 tests: JSON parsing (clean, code-fenced, surrounding text), missing field validation, error cases
- `tests/python/integration/test_api.py` — 3 new: LLM validate endpoint contract (missing key, response shape), onboarding endpoint validation
- All 168 Python + 14 TypeScript tests passing

**Next:** Phase 5 — Main agent pipeline (CrewAI flows, 4-agent chain, proposal generation)

---

## 2026-04-13 — [Phase 3.0] Ingestion Pipeline

**What changed:**
- `sidecar/services/ingestion/normalizer.py` — routing logic for MD passthrough, PDF via Marker, URL via Firecrawl; `detect_source_type()`, `slugify()`, `extract_title_from_markdown()` (with proper YAML frontmatter skipping), `ingest_markdown()`, `ingest_pdf()`, `ingest_url()`
- `sidecar/services/ingestion/marker_service.py` — async wrapper around Marker PDF→MD conversion running in executor thread
- `sidecar/services/ingestion/firecrawl_service.py` — Firecrawl API client with `_fetch_simple()` HTTP fallback for basic HTML→markdown when Firecrawl unavailable
- `sidecar/services/ingestion/job_queue.py` — in-memory async job queue with `IngestJobQueue` singleton, status tracking, cleanup of old completed jobs
- `sidecar/services/gpu_detect.py` — CUDA/MPS detection via torch with caching, graceful fallback when torch not installed
- `sidecar/main.py` — 5 new endpoints: `GET /system/capabilities`, `POST /ingest/file`, `POST /ingest/url`, `GET /ingest/status/{job_id}`, `GET /ingest/active`; background task `_run_ingest_job()` runs ingestion and updates FTS5 index
- `sidecar/models/responses.py` — added `IngestUrlRequest` Pydantic model
- `src/api/ingest.ts` — typed API client: `ingestFile()`, `ingestUrl()`, `getIngestStatus()`, `getActiveIngests()`, `getCapabilities()`
- `src/components/layout/DropZone.tsx` — Tauri drag-drop event listener with visual overlay ("Drop files to ingest")
- `src/components/layout/UrlBar.tsx` — inline URL paste input with validation, loading state, Escape to close
- `src/components/layout/IngestStatus.tsx` — sidebar job progress display with 2s polling, progress bars, error display
- `src/App.tsx` — wired DropZone (wraps entire app), UrlBar (in top bar when initialized), IngestStatus (in sidebar), ingest job state tracking with callbacks

**Decisions:**
- PDF routing: always use Marker first (works on CPU); MinerU integration deferred to when GPU routing logic is needed at scale
- Firecrawl service includes a simple HTTP fallback (`_fetch_simple`) that does basic HTML→markdown with BeautifulSoup, so URL ingestion works without a Firecrawl API key for simple pages
- `extract_title_from_markdown()` properly skips YAML frontmatter blocks (--- delimited) before looking for headings
- IngestStatus completed-job filter was buggy (`Date.now() - Date.now()` is always 0) — simplified to just hide completed jobs immediately
- Job queue is in-memory only (not persisted to SQLite) — acceptable since ingest jobs are short-lived and the queue resets on sidecar restart

**Tests:** 48 new tests added across 4 test files:
- `tests/python/test_normalizer.py` — 30 tests: source type detection (9), slugify (7), title extraction (6), markdown ingestion (4), PDF ingestion (3), URL ingestion (1)
- `tests/python/test_job_queue.py` — 16 tests: job lifecycle, status updates, active filtering, cleanup, unique IDs, enum values
- `tests/python/test_gpu_detect.py` — 6 tests: no-torch, CUDA, MPS, no-GPU-with-torch, caching, dataclass
- `tests/python/integration/test_api.py` — expanded with 10 new integration tests for /system/capabilities and all /ingest/* endpoints
- All 157 Python tests passing, 14 TypeScript tests passing, cargo check clean

**Next:** Phase 4 — Onboarding flow (API key setup, vault description, CrewAI setup crew for ontology/AGENTS.md generation)

---

## 2026-04-13 — [Phase 2.0] Vault infrastructure, file watching, graph service

**What changed:**

Backend (Python sidecar):
- `services/graph_service.py` — graph.json CRUD: add/remove nodes, add edges, source_map management, stale article lookup via `get_articles_citing()`. Dual-purpose: Reagraph visualization + stale tracking.
- `services/watcher_bridge.py` — Full debounce system: per-path 300s debounce, SHA-256 content hash verification at debounce end, timer reset on re-write, sync-write skip via `is_recent_sync_write()`, force-dispatch for "Run agent now" command.
- `main.py` expanded with 11 endpoints total: `/health`, `/status` (now live from DB), `/vault/structure` (with warnings), `/vault/create`, `/internal/file-event`, `/agent/run-now`, `/wiki/graph`, `/wiki/stale`, `/proposals`, `/runs` (paginated), `/search`
- `on_file_ready()` callback wired: when a debounced file passes, flags stale articles via graph.json source_map

Frontend (React + TypeScript):
- `src/api/sidecar.ts` — Full typed API client matching all 11 sidecar endpoints
- `src/api/fileWatcher.ts` — Bridges Tauri fs watch plugin to sidecar's `/internal/file-event` endpoint. Watches clean-vault (recursive) and wiki-vault/staging.
- `src/stores/statusStore.ts` — Polls `/status` every 5s; surfaces agent status + pending proposal count
- `src/stores/vaultStore.ts` — Updated with sidecarConnected state, vault warnings display
- `src/App.tsx` — Wires file watcher lifecycle, status polling, vault warnings banner

Rust (Tauri):
- `src/lib.rs` — Added `start_watching` and `get_app_data_dir` commands (file watching happens on TS side via `@tauri-apps/plugin-fs`)

**Decisions:**
- File watching lives in TypeScript (using `@tauri-apps/plugin-fs` `watch()`) not Rust — simpler, and the TS layer needs to forward events to the sidecar anyway
- Debounce is per-path with content hash verification — prevents false triggers when user saves a file multiple times quickly, and prevents re-triggering after no-op saves
- `on_file_ready` callback does stale article flagging immediately (Phase 5 will add agent pipeline dispatch)
- Status polling at 5s interval — good balance between responsiveness and overhead

**Tests:**
- `test_graph_service.py` — 24 tests: load/save, node CRUD, edge CRUD, source_map, stale lookup, path normalization (all pass)
- `test_watcher_bridge.py` — 7 async tests: debounce dispatch, timer reset, independent paths, force dispatch, delete events, pending count/paths (all pass)
- `test_api.py` — expanded to 21 integration tests: all 11 endpoints tested including vault creation, file events, search, graph, stale, proposals, runs (all pass)
- **Total: 95 Python + 14 TypeScript = 109 tests, all passing**
- Cargo check passes (0 errors, 0 warnings after fix)

**Next:** Phase 2 complete. Commit and begin Phase 3 (ingestion pipeline) or Phase 4 (onboarding).

---

## Phase 2 Summary — COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| graph_service.py | Done | Nodes, edges, source_map, stale article lookup, save/load with corruption recovery |
| watcher_bridge.py | Done | Per-path debounce (300s), SHA-256 hash verification, sync-write skip, force dispatch |
| FastAPI endpoints (11 total) | Done | All Phase 1+2 endpoints live, tested via TestClient |
| Frontend API client | Done | Typed wrappers for all endpoints in sidecar.ts |
| File watcher bridge | Done | Tauri fs watch -> TypeScript -> sidecar /internal/file-event |
| Status polling store | Done | 5s interval, agent status + pending proposals |
| Rust Tauri commands | Done | start_watching, get_app_data_dir |
| Tests | Done | 109 total (95 Python, 14 TypeScript) — all passing |

---

## 2026-04-13 — [Phase 1.0] Project initialization

**What changed:** Created git repo, BUILDLOG.md, docs/wiki/ development wiki, .gitignore

**Decisions:**
- Monorepo structure: `src-tauri/` (Rust/Tauri), `src/` (React frontend), `sidecar/` (Python FastAPI)
- SQLite owned exclusively by Python sidecar (SQLAlchemy, not Drizzle)
- Platforms: macOS + Windows only
- Distribution: unsigned builds for v1 (defer code signing)
- Python 3.10 available on machine; sidecar will target >=3.10
- Rust being installed via rustup

**Tests:** None yet — scaffolding phase

**Next:** Install Rust, scaffold Tauri v2 project, create Python sidecar skeleton with FastAPI

---

## 2026-04-13 — [Phase 1.1] Python sidecar scaffold + SQLite + path normalization

**What changed:**
- Created `sidecar/` directory structure: `main.py`, `config.py`, `db/database.py`, `db/repository.py`, `models/responses.py`, `services/paths.py`, `services/vault_manager.py`
- `pyproject.toml` with all dependency groups (core, dev, agents, ingestion, build)
- FastAPI app with `/health`, `/status`, `/vault/structure` endpoints
- SQLite schema with 6 tables: `fts_content`, `fts_index` (FTS5), `proposals`, `proposal_articles`, `agent_runs`, `stale_articles`, `sync_writes`
- WAL mode enabled by default; all writes serialized through `threading.Lock` in repository
- Path normalization utilities: `sidecar/services/paths.py` (Python) and `src/api/paths.ts` (TypeScript)
- Vault manager: creates full two-vault directory structure with default AGENTS.md, ontology.md, index.md, graph.json

**Decisions:**
- Using raw `sqlite3` module (not SQLAlchemy) for simplicity — the repository pattern gives us the same safety
- Global `_connection` with `check_same_thread=False` + WAL mode for async FastAPI
- FTS5 triggers auto-sync the virtual table with content table (no manual sync needed)
- Sidecar uses ephemeral port (printed to stdout as `VANILLA_PORT:{port}` for Tauri to read)

**Tests:**
- `tests/python/test_paths.py` — 13 tests: normalize, relative, absolute, vault detection (all pass)
- `tests/python/test_vault_manager.py` — 13 tests: creation, validation, idempotency, no-overwrite (all pass)
- `tests/python/test_repository.py` — 17 tests: FTS CRUD+search, proposals, agent runs, stale articles, sync writes (all pass)
- `tests/python/integration/test_api.py` — 3 tests: /health, /status, /vault/structure via TestClient (all pass)
- **Total: 46 Python tests, all passing**

**Next:** Tauri v2 project scaffold, React frontend shell, TypeScript tests

---

## 2026-04-13 — [Phase 1.2] Tauri v2 + React frontend scaffold

**What changed:**
- Created `src-tauri/`: `Cargo.toml`, `tauri.conf.json`, `capabilities/default.json`, `src/main.rs`, `src/lib.rs`, `build.rs`
- Tauri plugins registered: `tauri-plugin-shell` (sidecar), `tauri-plugin-fs` (file ops), `tauri-plugin-dialog` (folder picker)
- Capabilities configured: shell:spawn, fs:read/write/watch, dialog:open/save
- React frontend: `App.tsx` with two-pane layout skeleton, sidecar health check, onboarding detection
- Zustand store: `vaultStore.ts` — manages vault paths, initialization state, sidecar port
- TypeScript path normalization: `src/api/paths.ts` — matches Python behavior exactly
- Tailwind CSS v4 configured via `@tailwindcss/vite` plugin
- `package.json`, `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`
- `index.html` entry point

**Decisions:**
- Manual Tauri setup (not `npm create tauri-app`) since we have an existing directory structure
- Vite dev server on port 1420 (standard Tauri convention)
- Path aliases: `@/` maps to `src/` in both Vite and TypeScript
- React 19 + Zustand 5 (latest stable)

**Tests:**
- `tests/ts/paths.test.ts` — 14 tests: normalizePath, toRelative, isCleanVaultPath, isWikiVaultPath (all pass)
- **Total: 14 TypeScript tests, all passing**
- Cargo check running in background (Rust compilation)

**Next:** Verify cargo check passes, then initial git commit for Phase 1

---

## 2026-04-13 — [Phase 1.3] Cargo check passes, icons generated

**What changed:**
- Fixed `tauri.conf.json`: removed invalid `app.title` field (Tauri v2 uses `productName` at root level)
- Generated all Tauri icons from SVG placeholder via `npx tauri icon`
- Cargo check succeeds: all Rust dependencies compile, Tauri plugins load correctly

**Decisions:**
- Placeholder icon is a simple gray square with "V" — will be replaced with real branding later
- Removed Android/iOS icon dirs from git (not targeting mobile)

**Tests:**
- `cargo check` — passes (Tauri v2.10.3, tauri-plugin-shell v2.3.5, tauri-plugin-fs v2.5.0, tauri-plugin-dialog v2.7.0)
- Full test suite: 46 Python + 14 TypeScript = **60 tests, all passing**

**Next:** Phase 1 complete. Initial git commit. Begin Phase 2 (vault infrastructure)

---

## Phase 1 Summary — COMPLETE

| Component | Status | Notes |
|-----------|--------|-------|
| Git repo + BUILDLOG + docs/wiki | Done | 5 wiki docs covering architecture, API, vault schema, agent pipeline, testing |
| Rust 1.94.1 + Cargo | Done | Installed via rustup |
| Tauri v2 scaffold | Done | Compiles, plugins registered, capabilities set |
| React + Vite + TypeScript | Done | npm installed, Vite config, App.tsx with two-pane layout shell |
| Tailwind CSS v4 | Done | Via @tailwindcss/vite plugin |
| Python sidecar (FastAPI) | Done | main.py, config.py, ephemeral port, /health + /status + /vault/structure |
| SQLite schema | Done | 6 tables + FTS5, WAL mode, repository pattern |
| Path normalization | Done | Python + TypeScript, matching behavior verified by tests |
| Vault manager | Done | Creates/validates two-vault structure with defaults |
| Tests | Done | 60 total (46 Python, 14 TypeScript) — all passing |
