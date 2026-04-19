/**
 * GraphPanel — react-force-graph-2d knowledge graph visualization.
 *
 * Uses Canvas2D + d3-force for an Obsidian-style force-directed graph.
 * Node color encodes category; node size encodes in-degree (hub nodes are larger).
 * Typed relationship edges (uses, is-a, derived-from, …) show directional arrows.
 * Click a node to open its article in the editor.
 *
 * Rendering:
 *   - Custom nodeCanvasObject draws a soft radial glow behind each node, a filled
 *     disc in the category colour, and a label below (only rendered once zoomed
 *     in enough to be legible — keeps the overview view clean).
 *   - Recently-added nodes (lastBatch === latestBatchId) pulse with an amber halo.
 *   - Typed relationship edges carry directional particles so information flow is
 *     visible even when the graph is static.
 *
 * Physics:
 *   - Link distance, charge strength, and velocity decay are tuned via d3Force()
 *     after the ref is attached. Hub nodes (higher in-degree) get stronger
 *     repulsion so they don't bunch up; leaf nodes stay close to their parents.
 */

import { memo, useMemo, useEffect, useRef, useState, useCallback } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import { useGraphStore } from "@/stores/graphStore";
import { useEditorStore } from "@/stores/editorStore";
import { useThemeStore } from "@/stores/themeStore";

// ─── Constants ───────────────────────────────────────────────────────────────

const HIGHLIGHT     = "#f59e0b";
const NODE_REL_SIZE = 5;   // base px radius per sqrt(val) unit

/**
 * Accept a #rgb / #rrggbb colour and return an rgba() string with the given
 * alpha. Falls back to the input unchanged if it isn't a hex colour we can
 * parse (rgba gradients ignore non-rgba stops cleanly).
 */
function withAlpha(hex: string, alpha: number): string {
  if (!hex.startsWith("#")) return hex;
  let h = hex.slice(1);
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (h.length !== 6) return hex;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// ─── Category colours ────────────────────────────────────────────────────────

const CAT_LIGHT: Record<string, string> = {
  concept:      "#6366f1",
  model:        "#10b981",
  method:       "#f59e0b",
  algorithm:    "#f59e0b",
  event:        "#ec4899",
  person:       "#8b5cf6",
  organization: "#3b82f6",
  tool:         "#14b8a6",
  general:      "#a8a29e",
};
const CAT_DARK: Record<string, string> = {
  concept:      "#818cf8",
  model:        "#34d399",
  method:       "#fbbf24",
  algorithm:    "#fbbf24",
  event:        "#f472b6",
  person:       "#a78bfa",
  organization: "#60a5fa",
  tool:         "#2dd4bf",
  general:      "#71717a",
};

function catColor(category: string, isDark: boolean): string {
  const map = isDark ? CAT_DARK : CAT_LIGHT;
  return map[category] ?? (isDark ? "#71717a" : "#a8a29e");
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyGraph() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-stone-50 to-stone-100 dark:from-zinc-900 dark:to-zinc-800">
      <div className="text-center">
        <div className="mb-4 flex justify-center">
          <div className="rounded-full bg-white p-6 shadow-sm dark:bg-zinc-800 dark:shadow-zinc-900">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none"
              className="text-stone-400 dark:text-zinc-500">
              <circle cx="24" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
              <circle cx="12" cy="32" r="4" stroke="currentColor" strokeWidth="2" />
              <circle cx="36" cy="32" r="4" stroke="currentColor" strokeWidth="2" />
              <line x1="24" y1="16" x2="12" y2="28" stroke="currentColor" strokeWidth="2" />
              <line x1="24" y1="16" x2="36" y2="28" stroke="currentColor" strokeWidth="2" />
            </svg>
          </div>
        </div>
        <p className="text-lg font-medium text-stone-600 dark:text-zinc-300">No concepts yet</p>
        <p className="mt-2 text-sm text-stone-500 dark:text-zinc-500">
          Approve proposals to build your knowledge graph
        </p>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export const GraphPanel = memo(function GraphPanel() {
  const nodes        = useGraphStore((s) => s.nodes);
  const edges        = useGraphStore((s) => s.edges);
  const latestBatch  = useGraphStore((s) => s.latestBatchId);
  const startPolling = useGraphStore((s) => s.startPolling);
  const stopPolling  = useGraphStore((s) => s.stopPolling);
  const openFile     = useEditorStore((s) => s.openFile);
  const isDark       = useThemeStore((s) => s.isDark);

  // Start/stop polling when the panel mounts/unmounts
  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

  // Measure the container so the canvas fills it exactly
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDims({ width, height });
    });
    ro.observe(el);
    // Seed with initial size in case ResizeObserver fires late
    const rect = el.getBoundingClientRect();
    if (rect.width > 0) setDims({ width: rect.width, height: rect.height });
    return () => ro.disconnect();
  }, []);

  // In-degree map — hub nodes get larger
  const inDegree = useMemo(() => {
    const map: Record<string, number> = {};
    for (const e of edges) {
      map[e.target] = (map[e.target] ?? 0) + 1;
    }
    return map;
  }, [edges]);

  // Build graphData — react-force-graph uses "links" not "edges"
  // We create fresh objects so the force simulation can annotate them (x, y, vx, vy)
  // without mutating the Zustand store.
  const graphData = useMemo(() => ({
    nodes: nodes.map((n) => {
      const isNew  = !!(n.lastBatch === latestBatch && latestBatch);
      const degree = inDegree[n.id] ?? 0;
      return {
        id:       n.id,
        label:    n.label,
        path:     n.path,
        baseColor: catColor(n.category, isDark),
        color:    isNew ? HIGHLIGHT : catColor(n.category, isDark),
        isNew,
        degree,
        // val controls node area: base 1 + in-degree bonus, capped at 8
        val: Math.min(1 + degree, 8),
      };
    }),
    links: edges.map((e, i) => {
      const isTyped = !!(e.type && e.type !== "wikilink" && e.type !== "related-to");
      return {
        id:      `link-${i}`,
        source:  e.source,
        target:  e.target,
        isTyped,
        // Only surface meaningful typed relationships as labels
        label: isTyped ? e.type : undefined,
      };
    }),
  }), [nodes, edges, latestBatch, isDark, inDegree]);

  const handleNodeClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      const match = nodes.find((n) => n.id === node.id);
      if (match?.path) openFile(match.path);
    },
    [nodes, openFile],
  );

  // ─── Physics tuning ─────────────────────────────────────────────────────────
  // Reach into d3-force after mount and whenever data changes. Hub nodes get
  // extra repulsion proportional to their in-degree so dense neighbourhoods
  // spread out instead of collapsing into a tangle.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<ForceGraphMethods<any, any> | undefined>(undefined);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const charge = fg.d3Force("charge") as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const link   = fg.d3Force("link") as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const center = fg.d3Force("center") as any;

    if (charge?.strength) {
      // Base repulsion −120; hubs push harder (up to −320).
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      charge.strength((n: any) => -120 - Math.min(n.degree ?? 0, 10) * 20);
      // theta=0.9 gives a good speed/accuracy tradeoff on mid-size graphs.
      charge.theta?.(0.9);
      // distanceMax caps the reach of repulsion so disconnected clusters
      // don't fly apart.
      charge.distanceMax?.(400);
    }

    if (link?.distance) {
      // Slightly longer ideal edge length → airier layout.
      link.distance(60);
      link.strength?.(0.35);
    }

    if (center?.strength) {
      center.strength(0.05);
    }

    fg.d3ReheatSimulation();
  }, [graphData]);

  // ─── Custom node renderer ───────────────────────────────────────────────────
  // The pulse phase is read from performance.now() inline — force-graph's
  // internal render loop calls this on every tick, so we don't need React
  // state (which would cause whole-tree re-renders every frame).
  const nodeCanvasObject = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (typeof node.x !== "number" || typeof node.y !== "number") return;

      const val    = node.val ?? 1;
      const r      = NODE_REL_SIZE * Math.sqrt(val);
      const color  = node.color ?? (isDark ? "#71717a" : "#a8a29e");
      const base   = node.baseColor ?? color;

      // Soft outer glow — radial gradient. Tighter on hubs so the whole canvas
      // doesn't wash out in dense clusters.
      const glowR  = r * (node.isNew ? 3.2 : 2.6);
      const grad   = ctx.createRadialGradient(node.x, node.y, r * 0.9, node.x, node.y, glowR);
      grad.addColorStop(0, withAlpha(base, isDark ? 0.35 : 0.28));
      grad.addColorStop(1, withAlpha(base, 0));
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(node.x, node.y, glowR, 0, 2 * Math.PI);
      ctx.fill();

      // Pulsing halo for newly-added nodes (breathes at ~0.5 Hz).
      if (node.isNew) {
        const t      = performance.now() / 1000;
        const phase  = 0.5 + 0.5 * Math.sin(t * Math.PI);   // 0..1
        const haloR  = r + 3 + phase * 6;
        ctx.strokeStyle = withAlpha(HIGHLIGHT, 0.25 + 0.35 * phase);
        ctx.lineWidth   = 1.5;
        ctx.beginPath();
        ctx.arc(node.x, node.y, haloR, 0, 2 * Math.PI);
        ctx.stroke();
      }

      // Core disc.
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fill();

      // Thin inner ring for definition.
      ctx.strokeStyle = isDark ? "rgba(0,0,0,0.55)" : "rgba(255,255,255,0.85)";
      ctx.lineWidth   = 1 / globalScale;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.stroke();

      // Label — only render when zoomed in enough to read; hubs get labelled
      // at lower zoom than leaves so the overview stays legible.
      const labelThreshold = node.degree >= 3 ? 0.8 : 1.6;
      if (globalScale >= labelThreshold && node.label) {
        const fontSize = Math.max(10, 12 / globalScale);
        ctx.font         = `500 ${fontSize}px -apple-system, "Segoe UI", sans-serif`;
        ctx.textAlign    = "center";
        ctx.textBaseline = "top";
        const label = String(node.label);
        const ty    = node.y + r + 3;

        // Readable backdrop behind the text.
        const metrics = ctx.measureText(label);
        const padX = 3, padY = 1;
        ctx.fillStyle = isDark ? "rgba(24,24,27,0.78)" : "rgba(250,250,249,0.82)";
        ctx.fillRect(
          node.x - metrics.width / 2 - padX,
          ty - padY,
          metrics.width + padX * 2,
          fontSize + padY * 2,
        );

        ctx.fillStyle = isDark ? "#e4e4e7" : "#27272a";
        ctx.fillText(label, node.x, ty);
      }
    },
    [isDark],
  );

  // Clickable hit area has to match the rendered glyph, otherwise the halo
  // blocks clicks or the node misses them.
  const nodePointerAreaPaint = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      if (typeof node.x !== "number" || typeof node.y !== "number") return;
      const r = NODE_REL_SIZE * Math.sqrt(node.val ?? 1);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 2, 0, 2 * Math.PI);
      ctx.fill();
    },
    [],
  );

  if (nodes.length === 0) return <EmptyGraph />;

  const bg   = isDark ? "#18181b" : "#fafaf9";
  const edge = isDark ? "#3f3f46" : "#d6d3d1";

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden">
      <ForceGraph2D
        ref={fgRef}
        width={dims.width}
        height={dims.height}
        graphData={graphData}
        backgroundColor={bg}
        // Node appearance — delegated to nodeCanvasObject for glow + label.
        nodeVal="val"
        nodeLabel="label"        // native tooltip on hover (HTML overlay)
        nodeRelSize={NODE_REL_SIZE}
        nodeCanvasObjectMode={() => "replace"}
        nodeCanvasObject={nodeCanvasObject}
        nodePointerAreaPaint={nodePointerAreaPaint}
        // Edge appearance
        linkColor={() => edge}
        linkWidth={(l: { isTyped?: boolean }) => (l.isTyped ? 1.4 : 1)}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkLabel="label"
        // Particles flow along typed edges to convey direction at a glance.
        // Plain [[wikilinks]] stay quiet to avoid visual noise.
        linkDirectionalParticles={(l: { isTyped?: boolean }) => (l.isTyped ? 2 : 0)}
        linkDirectionalParticleWidth={1.8}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleColor={() => (isDark ? "#fbbf24" : "#f59e0b")}
        // Interaction
        onNodeClick={handleNodeClick}
        // Force tuning — the real work happens in the d3Force() useEffect above;
        // these knobs just shape the overall convergence.
        d3AlphaDecay={0.0228}
        d3VelocityDecay={0.32}
        cooldownTime={4000}
        warmupTicks={30}
        // Cursor
        onNodeHover={(node) => {
          if (containerRef.current) {
            containerRef.current.style.cursor = node ? "pointer" : "default";
          }
        }}
      />
    </div>
  );
});
