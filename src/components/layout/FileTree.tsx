/**
 * FileTree — recursive file browser for the left sidebar.
 */

import { useEffect, useRef, useState, useCallback, memo } from "react";
import { getVaultFiles, type FileTreeNode } from "@/api/sidecar";
import { useEditorStore } from "@/stores/editorStore";

/* ── Icons ────────────────────────────────────────────────────── */

function FolderIcon({ open }: { open: boolean }) {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="shrink-0 text-stone-400 dark:text-zinc-600">
      <path
        d={open
          ? "M1.5 3.5h5l1 1.5H14.5v8h-13z"
          : "M1.5 3h5l1 1.5H14.5v8.5h-13z"}
        stroke="currentColor"
        strokeWidth="1.2"
        fill={open ? "currentColor" : "none"}
        fillOpacity={open ? "0.12" : "0"}
      />
    </svg>
  );
}

function FileIcon({ active }: { active: boolean }) {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="shrink-0">
      <path
        d="M4 1.5h5.5L13 5v9.5H4z"
        stroke={active ? "#78716c" : "#d6d3d1"}
        strokeWidth="1.2"
        fill="none"
      />
      <path d="M9.5 1.5V5H13" stroke={active ? "#78716c" : "#d6d3d1"} strokeWidth="1.2" />
    </svg>
  );
}

/* ── Loading skeleton ──────────────────────────────────────────── */
function TreeSkeleton() {
  return (
    <div className="space-y-1 px-2 py-1 animate-pulse">
      {[80, 60, 90, 50, 70].map((w, i) => (
        <div
          key={i}
          className="h-5 rounded bg-stone-100 dark:bg-zinc-800"
          style={{ width: `${w}%`, marginLeft: i > 1 ? "12px" : "0" }}
        />
      ))}
    </div>
  );
}

/* ── Single tree node ─────────────────────────────────────────── */

const TreeNode = memo(function TreeNode({
  node,
  depth,
  activePath,
  onSelect,
}: {
  node: FileTreeNode;
  depth: number;
  activePath: string | null;
  onSelect: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const isDir = node.type === "directory";
  const isActive = node.path === activePath;
  const indent = depth * 12 + 4;

  if (isDir) {
    return (
      <div>
        <button
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          className="flex w-full items-center gap-1.5 rounded px-1 py-[3px] text-left text-xs
                     text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-700
                     dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200
                     focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-400"
          style={{ paddingLeft: `${indent}px` }}
        >
          <FolderIcon open={expanded} />
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {expanded && node.children.map((child) => (
          <TreeNode
            key={child.path}
            node={child}
            depth={depth + 1}
            activePath={activePath}
            onSelect={onSelect}
          />
        ))}
      </div>
    );
  }

  return (
    <button
      onClick={() => onSelect(node.path)}
      aria-current={isActive ? "page" : undefined}
      title={node.path}
      className={`flex w-full items-center gap-1.5 rounded px-1 py-[3px] text-left text-xs
                  transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-amber-400
                  ${isActive
                    ? "bg-stone-200 text-stone-900 font-medium dark:bg-zinc-700 dark:text-zinc-100"
                    : "text-stone-500 hover:bg-stone-50 hover:text-stone-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                  }`}
      style={{ paddingLeft: `${indent}px` }}
    >
      <FileIcon active={isActive} />
      <span className="truncate">{node.name}</span>
    </button>
  );
});

/* ── FileTree container ───────────────────────────────────────── */

export const FileTree = memo(function FileTree() {
  const [tree, setTree] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const activePath = useEditorStore((s) => s.activeFilePath);
  const openFile = useEditorStore((s) => s.openFile);

  const lastTreeHash = useRef<string | null>(null);
  const failCount = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getVaultFiles();
      failCount.current = 0;
      if (data.tree_hash !== lastTreeHash.current) {
        lastTreeHash.current = data.tree_hash ?? null;
        setTree(data.tree);
      }
    } catch {
      failCount.current++;
      // sidecar unavailable — keep existing tree; backoff handled below
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    function schedule() {
      // Exponential backoff on failures: 30s * 2^failCount, capped at 120s
      const delay = failCount.current > 0
        ? Math.min(120_000, 30_000 * Math.pow(2, failCount.current - 1))
        : 30_000;
      intervalRef.current = setTimeout(() => {
        refresh().then(schedule);
      }, delay);
    }

    schedule();
    return () => {
      if (intervalRef.current) clearTimeout(intervalRef.current);
    };
  }, [refresh]);

  if (loading) return <TreeSkeleton />;

  if (tree.length === 0) {
    return (
      <div className="px-3 py-4 text-center">
        <p className="text-xs text-stone-400 dark:text-zinc-600">No files yet</p>
        <p className="mt-1 text-[11px] text-stone-300 dark:text-zinc-700">Drop files to get started</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-px py-1">
      {tree.map((node) => (
        <TreeNode
          key={node.path}
          node={node}
          depth={0}
          activePath={activePath}
          onSelect={openFile}
        />
      ))}
    </div>
  );
});
