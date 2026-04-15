/**
 * Graph store — manages knowledge graph data independently from the editor.
 *
 * Isolated to prevent cross-renders between editor and graph components.
 * Polls every 30 seconds while active.
 */

import { create } from "zustand";
import { getGraph } from "@/api/sidecar";

interface GraphNode {
  id: string;
  label: string;
  path: string;
  category: string;
  lastBatch: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  latestBatchId: string | null;
  isLoading: boolean;
  polling: boolean;
  fetchGraph: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

let pollInterval: ReturnType<typeof setInterval> | null = null;

export const useGraphStore = create<GraphState>((set) => ({
  nodes: [],
  edges: [],
  latestBatchId: null,
  isLoading: false,
  polling: false,

  fetchGraph: async () => {
    set({ isLoading: true });

    try {
      const data = await getGraph();

      const nodes: GraphNode[] = data.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        path: n.path,
        category: n.category,
        lastBatch: n.lastBatch,
      }));

      const edges: GraphEdge[] = data.edges.map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
      }));

      // Extract latest batch id from the max lastBatch value across all nodes
      let latestBatchId: string | null = null;
      for (const node of nodes) {
        if (node.lastBatch && (!latestBatchId || node.lastBatch > latestBatchId)) {
          latestBatchId = node.lastBatch;
        }
      }

      set({ nodes, edges, latestBatchId, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  startPolling: () => {
    if (pollInterval) return; // Already polling
    set({ polling: true });

    // Initial fetch
    useGraphStore.getState().fetchGraph();

    // Poll every 30 seconds
    pollInterval = setInterval(() => {
      useGraphStore.getState().fetchGraph();
    }, 30_000);
  },

  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    set({ polling: false });
  },
}));
