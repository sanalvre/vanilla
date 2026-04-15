/**
 * GraphPanel — Reagraph knowledge graph visualization.
 *
 * Rendered with React.memo to isolate from editor re-renders.
 * Highlights nodes from the latest approved batch.
 * Click a node to open its article in the editor.
 */

import { memo, useMemo, useEffect } from "react";
import { GraphCanvas, type GraphNode, type GraphEdge } from "reagraph";
import { useGraphStore } from "@/stores/graphStore";
import { useEditorStore } from "@/stores/editorStore";

const NODE_COLOR = "#a8a29e";
const HIGHLIGHT_COLOR = "#f59e0b";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const graphTheme: any = {
  canvas: { background: "#fafaf9" },
  node: {
    fill: NODE_COLOR,
    activeFill: HIGHLIGHT_COLOR,
    label: { color: "#44403c", stroke: "#fafaf9" },
  },
  edge: {
    fill: "#d6d3d1",
    activeFill: HIGHLIGHT_COLOR,
    label: { color: "#78716c", stroke: "#fafaf9", fontSize: 6 },
  },
  arrow: { fill: "#d6d3d1", activeFill: HIGHLIGHT_COLOR },
  ring: { fill: "#e7e5e4", activeFill: HIGHLIGHT_COLOR },
  lasso: { border: "1px solid #78716c", background: "rgba(120,113,108,0.1)" },
};

export const GraphPanel = memo(function GraphPanel() {
  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const latestBatchId = useGraphStore((s) => s.latestBatchId);
  const startPolling = useGraphStore((s) => s.startPolling);
  const stopPolling = useGraphStore((s) => s.stopPolling);
  const openFile = useEditorStore((s) => s.openFile);

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

  const graphNodes: GraphNode[] = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        label: n.label,
        fill: n.lastBatch === latestBatchId && latestBatchId ? HIGHLIGHT_COLOR : NODE_COLOR,
      })),
    [nodes, latestBatchId],
  );

  const graphEdges: GraphEdge[] = useMemo(
    () =>
      edges.map((e, i) => ({
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        label: e.type !== "wikilink" ? e.type : undefined,
      })),
    [edges],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-stone-50 to-stone-100">
        <div className="text-center">
          <div className="mb-4 flex justify-center">
            <div className="rounded-full bg-white p-6 shadow-sm">
              <svg
                width="48"
                height="48"
                viewBox="0 0 48 48"
                fill="none"
                className="text-stone-400"
              >
                <circle cx="24" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                <circle cx="12" cy="32" r="4" stroke="currentColor" strokeWidth="2" />
                <circle cx="36" cy="32" r="4" stroke="currentColor" strokeWidth="2" />
                <line x1="24" y1="16" x2="12" y2="28" stroke="currentColor" strokeWidth="2" />
                <line x1="24" y1="16" x2="36" y2="28" stroke="currentColor" strokeWidth="2" />
              </svg>
            </div>
          </div>
          <p className="text-lg font-medium text-stone-600">No concepts yet</p>
          <p className="mt-2 text-sm text-stone-500">
            Approve proposals to build your knowledge graph
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <GraphCanvas
        nodes={graphNodes}
        edges={graphEdges}
        theme={graphTheme}
        labelType="auto"
        draggable
        onNodeClick={(node) => {
          const match = nodes.find((n) => n.id === node.id);
          if (match?.path) {
            openFile(match.path);
          }
        }}
      />
    </div>
  );
});
