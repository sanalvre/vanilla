"""
Pydantic response models for the FastAPI sidecar.

These define the API contract between the React frontend and the Python backend.
"""

from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str  # "ok"


class LastRun(BaseModel):
    id: str
    completed_at: int  # unix timestamp
    tokens_used: int


class StatusResponse(BaseModel):
    agent_status: str  # "idle" | "running" | "error"
    current_phase: Optional[str] = None  # "ingest" | "analysis" | "proposal" | "fileback"
    last_run: Optional[LastRun] = None
    pending_proposals: int = 0


class VaultStructureResponse(BaseModel):
    initialized: bool
    clean_vault_path: Optional[str] = None
    wiki_vault_path: Optional[str] = None


class VaultCreateRequest(BaseModel):
    base_path: str
    ontology_content: Optional[str] = None
    agents_content: Optional[str] = None


class VaultCreateResponse(BaseModel):
    success: bool
    clean_vault_path: str
    wiki_vault_path: str


class FileEventRequest(BaseModel):
    path: str
    event_type: str  # "create" | "modify" | "delete"
    timestamp: int


class IngestUrlRequest(BaseModel):
    url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending" | "processing" | "complete" | "error"
    progress: float = 0.0
    output_path: Optional[str] = None
    error: Optional[str] = None


class LLMValidateRequest(BaseModel):
    provider: str  # "openai" | "anthropic" | "openrouter" | "ollama"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # for Ollama


class LLMValidateResponse(BaseModel):
    valid: bool
    error: Optional[str] = None
