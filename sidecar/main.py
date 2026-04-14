"""
Vanilla Sidecar — FastAPI application entry point.

This is the Python backend for Vanilla, spawned by Tauri as a sidecar process.
It handles: agent orchestration (CrewAI), SQLite database, ingestion pipeline,
and vault management.

On startup, it binds to an ephemeral port and prints the port number to stdout
so Tauri can read it and configure the frontend's base URL.

All file paths are normalized to forward slashes via services.paths.
"""

import sys
import socket
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import VanillaConfig
from db.database import init_db, get_db_path
from models.responses import HealthResponse, StatusResponse


def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Global config — loaded once at startup, updated via endpoints
config = VanillaConfig.load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Initialize SQLite database with WAL mode
    init_db(get_db_path(config))
    yield
    # Shutdown: nothing to clean up (SQLite closes automatically)


app = FastAPI(
    title="Vanilla Sidecar",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow requests from Tauri webview (localhost with any port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tauri webview uses tauri:// or https://localhost
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
    return StatusResponse(
        agent_status="idle",
        current_phase=None,
        last_run=None,
        pending_proposals=0,
    )


@app.get("/vault/structure")
async def vault_structure():
    """Return current vault paths and initialization state."""
    return {
        "initialized": config.initialized,
        "clean_vault_path": config.clean_vault_path,
        "wiki_vault_path": config.wiki_vault_path,
    }


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
