"""
Vanilla Sidecar — FastAPI application entry point.

This is the Python backend for Vanilla, spawned by Tauri as a sidecar process.
It handles: agent orchestration (CrewAI), SQLite database, ingestion pipeline,
and vault management.

On startup, it binds to an ephemeral port and prints the port number to stdout
so Tauri can read it and configure the frontend's base URL.

All file paths are normalized to forward slashes via services.paths.
"""

import asyncio
import logging
import sys
import socket
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import VanillaConfig
from db.database import init_db, get_db_path
from db import repository as repo
from models.responses import (
    HealthResponse,
    StatusResponse,
    VaultCreateRequest,
    VaultCreateResponse,
    FileEventRequest,
    IngestUrlRequest,
    LastRun,
)
from services.vault_manager import create_vault_structure, validate_vault_structure
from services.graph_service import load_graph, get_articles_citing
from services.watcher_bridge import WatcherBridge, FileEvent
from services.paths import normalize_path
from services.gpu_detect import detect_gpu
from services.ingestion.job_queue import ingest_queue, JobStatus
from services.ingestion.normalizer import (
    ingest_markdown, ingest_pdf, ingest_url, detect_source_type,
)

logger = logging.getLogger("vanilla")


def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Global config — loaded once at startup, updated via endpoints
config = VanillaConfig.load()

# Watcher bridge — initialized in lifespan
watcher_bridge: Optional[WatcherBridge] = None


async def on_file_ready(event: FileEvent) -> None:
    """
    Callback fired when a file passes the debounce check.
    This is where the agent pipeline will be triggered (Phase 5).
    For now, we log it and flag stale articles.
    """
    logger.info("File ready for processing: %s (%s)", event.path, event.event_type)

    # Stale article detection: if a clean-vault file changed,
    # find all wiki articles that cite it and flag them
    if event.path.startswith("clean-vault/") and config.wiki_vault_path:
        graph = load_graph(config.wiki_vault_path)
        stale_articles = get_articles_citing(graph, event.path)
        for article_path in stale_articles:
            repo.flag_stale_article(article_path, event.path)
            logger.info("Flagged stale article: %s (source changed: %s)", article_path, event.path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global watcher_bridge

    # Initialize SQLite database with WAL mode
    init_db(get_db_path(config))

    # Initialize watcher bridge with debounce
    vault_root = ""
    if config.clean_vault_path:
        # Vault root is the parent of clean-vault
        from pathlib import Path
        vault_root = str(Path(config.clean_vault_path).parent)

    watcher_bridge = WatcherBridge(
        debounce_seconds=300,
        on_ready=on_file_ready,
        vault_root=vault_root,
    )
    await watcher_bridge.start()

    yield

    # Shutdown
    if watcher_bridge:
        await watcher_bridge.stop()


app = FastAPI(
    title="Vanilla Sidecar",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow requests from Tauri webview (localhost with any port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── System Endpoints ───────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """Basic health check."""
    return HealthResponse(status="ok")


@app.get("/status", response_model=StatusResponse)
async def status():
    """Agent pipeline status and pending proposal count."""
    pending = repo.count_pending_proposals()
    last = repo.get_last_run()

    last_run = None
    if last:
        last_run = LastRun(
            id=last["run_id"],
            completed_at=last.get("completed_at", 0) or 0,
            tokens_used=last.get("tokens_used", 0) or 0,
        )

    return StatusResponse(
        agent_status="idle",  # Will be dynamic in Phase 5
        current_phase=None,
        last_run=last_run,
        pending_proposals=pending,
    )


# ─── Vault Endpoints ────────────────────────────────────────────────

@app.get("/vault/structure")
async def vault_structure():
    """Return current vault paths and initialization state."""
    warnings = []
    if config.initialized and config.clean_vault_path:
        from pathlib import Path
        base = str(Path(config.clean_vault_path).parent)
        warnings = validate_vault_structure(base)

    return {
        "initialized": config.initialized,
        "clean_vault_path": config.clean_vault_path,
        "wiki_vault_path": config.wiki_vault_path,
        "warnings": warnings,
    }


@app.post("/vault/create", response_model=VaultCreateResponse)
async def vault_create(request: VaultCreateRequest):
    """Create the two-vault directory structure."""
    global watcher_bridge

    try:
        result = create_vault_structure(
            base_path=request.base_path,
            ontology_content=request.ontology_content,
            agents_content=request.agents_content,
        )

        # Update config
        config.clean_vault_path = result["clean_vault_path"]
        config.wiki_vault_path = result["wiki_vault_path"]
        config.initialized = True
        config.save()

        # Restart watcher bridge with the new vault root
        if watcher_bridge:
            await watcher_bridge.stop()
        watcher_bridge = WatcherBridge(
            debounce_seconds=300,
            on_ready=on_file_ready,
            vault_root=request.base_path,
        )
        await watcher_bridge.start()

        return VaultCreateResponse(
            success=True,
            clean_vault_path=result["clean_vault_path"],
            wiki_vault_path=result["wiki_vault_path"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── System Capabilities ────────────────────────────────────────────

@app.get("/system/capabilities")
async def system_capabilities():
    """Return hardware detection results (GPU, Python version)."""
    import sys as _sys
    gpu = detect_gpu()
    return {
        "gpu": gpu.gpu,
        "gpu_type": gpu.gpu_type,
        "python_version": _sys.version.split()[0],
    }


# ─── Ingestion Endpoints ────────────────────────────────────────────

@app.post("/ingest/file")
async def ingest_file_upload(
    file_path: str,  # Absolute path to the file on disk
):
    """
    Start ingestion of a local file (dropped onto the app or selected via dialog).
    Returns a job ID for status polling.
    """
    if not config.clean_vault_path:
        raise HTTPException(status_code=400, detail="Vault not initialized")

    source_type = detect_source_type(file_path)
    if source_type == "unknown":
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_path}")

    job = ingest_queue.create_job(
        source_type=source_type,
        source_path=file_path,
    )

    # Run ingestion in background
    asyncio.create_task(_run_ingest_job(job.job_id))

    return {"job_id": job.job_id}


@app.post("/ingest/url")
async def ingest_url_endpoint(request: IngestUrlRequest):
    """
    Start ingestion of a URL. Requires internet access.
    Returns a job ID for status polling.
    """
    if not config.clean_vault_path:
        raise HTTPException(status_code=400, detail="Vault not initialized")

    job = ingest_queue.create_job(
        source_type="url",
        source_url=request.url,
    )

    asyncio.create_task(_run_ingest_job(job.job_id))

    return {"job_id": job.job_id}


@app.get("/ingest/status/{job_id}")
async def ingest_status(job_id: str):
    """Poll ingestion job status."""
    job = ingest_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job.to_dict()


@app.get("/ingest/active")
async def ingest_active():
    """List all active (pending/processing) ingest jobs."""
    return {"jobs": ingest_queue.get_active_jobs()}


async def _run_ingest_job(job_id: str) -> None:
    """Background task that runs an ingestion job."""
    job = ingest_queue.get_job(job_id)
    if not job:
        return

    ingest_queue.update_job(job_id, status=JobStatus.PROCESSING, progress=0.1)

    try:
        if job.source_type == "md" and job.source_path:
            result = await ingest_markdown(job.source_path, config.clean_vault_path)
        elif job.source_type == "pdf" and job.source_path:
            gpu = detect_gpu()
            result = await ingest_pdf(job.source_path, config.clean_vault_path, gpu_available=gpu.gpu)
        elif job.source_type == "url" and job.source_url:
            result = await ingest_url(job.source_url, config.clean_vault_path, firecrawl_api_key=config.llm.api_key)
        else:
            ingest_queue.update_job(job_id, status=JobStatus.ERROR, error="Invalid job configuration")
            return

        if result.success:
            # Update FTS index
            repo.upsert_fts(result.output_path, "clean", result.title, result.body)
            ingest_queue.update_job(
                job_id,
                status=JobStatus.COMPLETE,
                progress=1.0,
                output_path=result.output_path,
            )
            logger.info("Ingest complete: %s -> %s", job.source_path or job.source_url, result.output_path)
        else:
            ingest_queue.update_job(job_id, status=JobStatus.ERROR, error=result.error)
            logger.error("Ingest failed: %s", result.error)

    except Exception as e:
        logger.error("Ingest job error: %s", e)
        ingest_queue.update_job(job_id, status=JobStatus.ERROR, error=str(e))


# ─── File Event Endpoints ───────────────────────────────────────────

@app.post("/internal/file-event")
async def file_event(request: FileEventRequest):
    """
    Receive file system events from Tauri's watcher via the frontend.
    Events are queued and debounced before triggering the agent pipeline.
    """
    if not watcher_bridge:
        raise HTTPException(status_code=503, detail="Watcher bridge not initialized")

    event = FileEvent(
        path=request.path,
        event_type=request.event_type,
        timestamp=request.timestamp,
    )
    queued = await watcher_bridge.push_event(event)

    return {"queued": queued, "pending_count": watcher_bridge.get_pending_count()}


@app.post("/agent/run-now")
async def agent_run_now():
    """
    Force-trigger the agent pipeline, bypassing debounce.
    Processes all files currently in the debounce queue.
    """
    if not watcher_bridge:
        raise HTTPException(status_code=503, detail="Watcher bridge not initialized")

    count = await watcher_bridge.force_dispatch_all()
    return {"dispatched": count}


# ─── Graph Endpoints ────────────────────────────────────────────────

@app.get("/wiki/graph")
async def wiki_graph():
    """Return the current knowledge graph for Reagraph visualization."""
    if not config.wiki_vault_path:
        return {"nodes": [], "edges": [], "source_map": {}}

    graph = load_graph(config.wiki_vault_path)
    return graph


@app.get("/wiki/stale")
async def wiki_stale():
    """Return all articles currently flagged as stale."""
    stale = repo.get_stale_articles()
    return {"stale_articles": stale}


# ─── Proposal Endpoints (read-only for now, write in Phase 5) ──────

@app.get("/proposals")
async def list_proposals():
    """List all pending proposal batches."""
    batches = repo.get_pending_proposals()
    return {"batches": batches}


# ─── Run History ────────────────────────────────────────────────────

@app.get("/runs")
async def list_runs(limit: int = 20, offset: int = 0):
    """Paginated agent run history."""
    runs = repo.get_runs(limit=limit, offset=offset)
    return {"runs": runs}


# ─── Search Endpoint ────────────────────────────────────────────────

@app.get("/search")
async def search(q: str, vault: str = "all", limit: int = 20):
    """Full-text search across indexed vault documents."""
    if not q.strip():
        return {"results": []}

    results = repo.search_fts(q, vault=vault if vault != "all" else None, limit=limit)
    return {"results": results}


# ─── Entry Point ────────────────────────────────────────────────────

def main():
    port = find_free_port()
    # CRITICAL: Print port to stdout for Tauri to read
    print(f"VANILLA_PORT:{port}", flush=True)
    sys.stdout.flush()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
