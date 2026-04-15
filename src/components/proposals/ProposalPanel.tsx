/**
 * ProposalPanel — slide-in right panel for reviewing agent proposals.
 *
 * Shown when the user clicks the "N proposals pending" footer badge.
 * Fetches all pending batches, renders each as a ProposalBatch card.
 * Calls refresh() on the status store after any approve/reject so the
 * badge count updates immediately without waiting for the next poll.
 */

import { useEffect, useState, useCallback } from "react";
import { getProposals } from "@/api/sidecar";
import { useStatusStore } from "@/stores/statusStore";
import { ProposalBatch } from "./ProposalBatch";

interface ProposalPanelProps {
  onClose: () => void;
}

type Batch = {
  batch_id: string;
  summary: string;
  status: string;
  batch_path: string;
  articles: Array<{
    filename: string;
    title: string;
    action: string;
    status: string;
  }>;
  created_at: number;
};

export function ProposalPanel({ onClose }: ProposalPanelProps) {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useStatusStore((s) => s.refresh);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProposals();
      setBatches(data.batches);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load proposals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleResolved() {
    // Re-fetch proposals and update status badge
    await load();
    await refresh();
    // If no more proposals, close the panel
    if (batches.length <= 1) {
      onClose();
    }
  }

  return (
    <div className="flex h-full flex-col border-l border-stone-200 bg-stone-50">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-stone-800">
            Pending Proposals
          </h2>
          {!loading && (
            <p className="text-xs text-stone-400">
              {batches.length === 0
                ? "All caught up"
                : `${batches.length} batch${batches.length !== 1 ? "es" : ""} awaiting review`}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600"
          aria-label="Close proposal panel"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <p className="text-sm text-stone-400">Loading proposals…</p>
          </div>
        ) : error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
            <button
              onClick={load}
              className="ml-2 underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        ) : batches.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-stone-400">
            <span className="text-2xl">✓</span>
            <p className="text-sm">No pending proposals</p>
          </div>
        ) : (
          <div className="space-y-4">
            {batches.map((batch) => (
              <ProposalBatch
                key={batch.batch_id}
                batch={batch}
                onResolved={handleResolved}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer hint */}
      {batches.length > 0 && (
        <div className="border-t border-stone-200 bg-white px-4 py-2">
          <p className="text-xs text-stone-400">
            Approving writes articles to wiki-vault and updates the knowledge
            graph. Rejecting discards the staged drafts.
          </p>
        </div>
      )}
    </div>
  );
}
