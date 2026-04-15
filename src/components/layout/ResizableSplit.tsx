/**
 * ResizableSplit — vertical drag-resizable splitter.
 *
 * Top child gets `splitPercent`% of height; bottom child gets the rest.
 * Drag the handle to resize. No external deps — pure pointer events.
 */

import { useRef, useCallback, memo, type ReactNode } from "react";

interface ResizableSplitProps {
  splitPercent: number;
  onSplitChange: (pct: number) => void;
  top: ReactNode;
  bottom: ReactNode;
}

export const ResizableSplit = memo(function ResizableSplit({
  splitPercent,
  onSplitChange,
  top,
  bottom,
}: ResizableSplitProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const container = containerRef.current;
      if (!container) return;

      const el = e.currentTarget as HTMLElement;
      el.setPointerCapture(e.pointerId);

      const onMove = (me: PointerEvent) => {
        const rect = container.getBoundingClientRect();
        const y = me.clientY - rect.top;
        const pct = (y / rect.height) * 100;
        onSplitChange(pct);
      };

      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [onSplitChange],
  );

  return (
    <div ref={containerRef} className="flex h-full flex-col overflow-hidden">
      {/* Top pane */}
      <div style={{ height: `${splitPercent}%` }} className="overflow-hidden">
        {top}
      </div>

      {/* Drag handle */}
      <div
        onPointerDown={handlePointerDown}
        className="group flex h-1.5 shrink-0 cursor-row-resize items-center justify-center bg-stone-100 hover:bg-stone-200 transition-colors"
      >
        <div className="h-0.5 w-8 rounded-full bg-stone-300 group-hover:bg-stone-400 transition-colors" />
      </div>

      {/* Bottom pane */}
      <div className="flex-1 overflow-hidden">{bottom}</div>
    </div>
  );
});
