/**
 * FileTree — recursive file browser for the left sidebar.
 *
 * Fetches the vault directory tree from the sidecar and renders
 * collapsible folders with clickable file entries.
 */

import { useEffect, useState, useCallback, memo } from "react";
import { getVaultFiles, type FileTreeNode } from "@/api/sidecar";
import { useEditorStore } from "@/stores/editorStore";

/* ── Icons (inline SVG to avoid deps) ────────────────────────── */

function FolderIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      className="shrink-0"
    >
      {open ? (
        <path
          d="M1.5 3.5h5l1 1.5H14.5v8h-13z"
          stroke="currentColor"
          strokeWidth="1.2"
          fill="none"
        />
      ) : (
        <path
          d="M1.5 3h5l1 1.5H14.5v8.5h-13z"
          stroke="currentColor"
          strokeWidth="1.2"
          fill="none"
        />
      )}
    </svg>
  );
}

function FileIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      className="shrink-0"
    >
      <path
        d="M4 1.5h5.5L13 5v9.5H4z"
        stroke="currentColor"
        strokeWidth="1.2"
        fill="none"
      />
      <path d="M9.5 1.5V5H13" stroke="currentColor" strokeWidth="1.2" />
    </svg>
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

  if (isDir) {
    return (
      <div>
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm hover:bg-stone-100"
          style={{ paddingLeft: `${depth * 12 + 4}px` }}
        >
          <FolderIcon open={expanded} />
          <span className="truncate font-medium text-stone-600">
            {node.name}
          </span>
        </button>
        {expanded &&
          node.children.map((child) => (
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
      className={`flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left text-sm ${
        isActive
          ? "bg-stone-200 text-stone-900"
          : "text-stone-500 hover:bg-stone-50 hover:text-stone-700"
      }`}
      style={{ paddingLeft: `${depth * 12 + 4}px` }}
    >
      <FileIcon />
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

  const refresh = useCallback(async () => {
    try {
      const data = await getVaultFiles();
      setTree(data.tree);
    } catch {
      // sidecar unavailable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Refresh tree every 15 seconds to pick up new files
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [refresh]);

  if (loading) {
    return (
      <div className="px-3 py-2 text-xs text-stone-400">Loading files...</div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="px-3 py-2 text-xs text-stone-400">No files yet</div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 py-1">
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
