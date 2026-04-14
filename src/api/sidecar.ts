/**
 * Sidecar API client — all HTTP calls to the Python FastAPI backend.
 *
 * Every function here maps to an endpoint defined in docs/wiki/api-reference.md.
 * The base URL is dynamically set from the sidecar port.
 */

import { useVaultStore } from "@/stores/vaultStore";
import { normalizePath } from "./paths";

function baseUrl(): string {
  const port = useVaultStore.getState().sidecarPort;
  return `http://127.0.0.1:${port}`;
}

// ─── System ────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${baseUrl()}/health`);
  return res.json();
}

export async function getStatus(): Promise<{
  agent_status: string;
  current_phase: string | null;
  last_run: { id: string; completed_at: number; tokens_used: number } | null;
  pending_proposals: number;
}> {
  const res = await fetch(`${baseUrl()}/status`);
  return res.json();
}

// ─── Vault ─────────────────────────────────────────────────────────

export async function getVaultStructure(): Promise<{
  initialized: boolean;
  clean_vault_path: string | null;
  wiki_vault_path: string | null;
  warnings: string[];
}> {
  const res = await fetch(`${baseUrl()}/vault/structure`);
  return res.json();
}

export async function createVault(
  basePath: string,
  ontologyContent?: string,
  agentsContent?: string,
): Promise<{
  success: boolean;
  clean_vault_path: string;
  wiki_vault_path: string;
}> {
  const res = await fetch(`${baseUrl()}/vault/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      base_path: basePath,
      ontology_content: ontologyContent,
      agents_content: agentsContent,
    }),
  });
  if (!res.ok) throw new Error(`Vault creation failed: ${res.statusText}`);
  return res.json();
}

// ─── File Events ───────────────────────────────────────────────────

export async function sendFileEvent(
  path: string,
  eventType: "create" | "modify" | "delete",
): Promise<{ queued: boolean; pending_count: number }> {
  const res = await fetch(`${baseUrl()}/internal/file-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path: normalizePath(path),
      event_type: eventType,
      timestamp: Math.floor(Date.now() / 1000),
    }),
  });
  return res.json();
}

export async function runAgentNow(): Promise<{ dispatched: number }> {
  const res = await fetch(`${baseUrl()}/agent/run-now`, { method: "POST" });
  return res.json();
}

// ─── Graph ─────────────────────────────────────────────────────────

export async function getGraph(): Promise<{
  nodes: Array<{
    id: string;
    label: string;
    path: string;
    category: string;
    lastBatch: string;
  }>;
  edges: Array<{ source: string; target: string; type: string }>;
  source_map: Record<string, string[]>;
}> {
  const res = await fetch(`${baseUrl()}/wiki/graph`);
  return res.json();
}

export async function getStaleArticles(): Promise<{
  stale_articles: Array<{
    article_path: string;
    source_path: string;
    flagged_at: number;
  }>;
}> {
  const res = await fetch(`${baseUrl()}/wiki/stale`);
  return res.json();
}

// ─── Proposals ─────────────────────────────────────────────────────

export async function getProposals(): Promise<{
  batches: Array<{
    batch_id: string;
    summary: string;
    status: string;
    articles: Array<{
      filename: string;
      title: string;
      action: string;
      status: string;
    }>;
    created_at: number;
  }>;
}> {
  const res = await fetch(`${baseUrl()}/proposals`);
  return res.json();
}

// ─── Search ────────────────────────────────────────────────────────

export async function search(
  query: string,
  vault: "all" | "clean" | "wiki" = "all",
  limit: number = 20,
): Promise<{
  results: Array<{
    path: string;
    vault: string;
    title: string;
    snippet: string;
    score: number;
  }>;
}> {
  const params = new URLSearchParams({ q: query, vault, limit: String(limit) });
  const res = await fetch(`${baseUrl()}/search?${params}`);
  return res.json();
}

// ─── Runs ──────────────────────────────────────────────────────────

export async function getRuns(
  limit: number = 20,
  offset: number = 0,
): Promise<{
  runs: Array<{
    run_id: string;
    trigger_path: string | null;
    status: string;
    started_at: number;
    completed_at: number | null;
    tokens_used: number;
  }>;
}> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(`${baseUrl()}/runs?${params}`);
  return res.json();
}
