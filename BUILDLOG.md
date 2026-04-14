# Vanilla Build Log

Reverse-chronological log of all development activity. This is the primary context source for any agent or developer picking up work on this project.

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
